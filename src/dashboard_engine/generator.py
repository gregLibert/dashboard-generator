# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import io
import json
import os
from datetime import datetime

import jinja2

# Cross-version string base type (Python 2.7 / 3.x)
try:  # pragma: no cover - trivial compatibility shim
    basestring  # type: ignore[name-defined]
except NameError:  # Python 3
    basestring = str  # type: ignore[assignment]

JS_ASSET_FILES = [
    "js/utils.js",
    "js/base_widget.js",
    "js/sankey_widget.js",
    "js/financial_sankey_widget.js",
    "js/evolution_widget.js",
    "js/sunburst_widget.js",
    "js/horizon_widget.js",
    "js/treemap_widget.js",
    "js/stacked_area_widget.js",
    "js/bubble_widget.js",
    "js/heatmap_widget.js",
    "js/radial_area_widget.js",
    "js/main.js",
]

D3_CDN_IMPORT = 'import * as d3 from "https://cdn.jsdelivr.net/npm/d3@7/+esm";\n'
D3_SANKEY_CDN_IMPORT = (
    'import { sankey, sankeyLinkHorizontal, sankeyJustify, sankeyLeft } '
    'from "https://cdn.jsdelivr.net/npm/d3-sankey@0.12/+esm";\n'
)


class DashboardGenerator(object):
    """Main entrypoint used to generate a standalone HTML dashboard."""

    def __init__(self):
        self.root_path = os.path.dirname(os.path.abspath(__file__))
        self.assets_path = os.path.join(self.root_path, "assets")

        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(self.assets_path),
            autoescape=jinja2.select_autoescape(["html", "xml"]),
        )

    def _read_asset(self, filename):
        """Read a text asset from the bundled assets directory."""
        asset_path = os.path.join(self.assets_path, filename)
        with io.open(asset_path, "r", encoding="utf-8") as f:
            return f.read()

    @staticmethod
    def _build_full_config(config):
        """Return a copy of the user config enriched with metadata (pure, for tests)."""
        if not isinstance(config, dict):
            raise TypeError("config must be a dict")

        full_config = config.copy()
        full_config["generation_date"] = datetime.now().strftime("%Y%m%d")
        return full_config

    @staticmethod
    def _build_context(config, full_config, datasets_list, css_content, js_content):
        """Build the Jinja2 template context (pure, for tests)."""
        title = config.get("title", "Dashboard")
        subtitle = config.get("subtitle", "")
        include_dev_markup = config.get("dev_mode", False)

        return {
            "title": title,
            "subtitle": subtitle,
            "config_json": json.dumps(full_config),
            "datasets": datasets_list,
            "css_content": css_content,
            "js_content": js_content,
            "include_dev_markup": include_dev_markup,
        }

    def _build_js_content(self, js_files):
        """Concatenate JS assets and prepend D3 imports.

        The result is a single ES module string that can be inlined in the
        generated HTML file.
        """
        js_content_parts = [D3_CDN_IMPORT, D3_SANKEY_CDN_IMPORT]

        for js_file in js_files:
            content = self._read_asset(js_file)
            js_content_parts.append("\n// --- {} ---\n{}\n".format(js_file, content))

        return "".join(js_content_parts)

    @staticmethod
    def _validate_inputs(config, datasets_list):
        """Validate public API inputs early to surface clear errors."""
        if not isinstance(config, dict):
            raise TypeError("config must be a dict")

        if not isinstance(datasets_list, (list, tuple)):
            raise TypeError("datasets_list must be a list or tuple of CSV strings")

        for idx, dataset in enumerate(datasets_list):
            if not isinstance(dataset, basestring):
                raise TypeError(
                    "datasets_list[{}] must be a string containing CSV data".format(idx)
                )

    def generate(self, config, datasets_list):
        """Generate a standalone HTML dashboard.

        :param config: dashboard configuration dictionary.
        :param datasets_list: list of CSV strings used by the widgets.
        :return: rendered HTML string.
        """
        self._validate_inputs(config, datasets_list)

        css_content = self._read_asset("style.css")
        js_content = self._build_js_content(JS_ASSET_FILES)

        full_config = self._build_full_config(config)
        context = self._build_context(
            config=config,
            full_config=full_config,
            datasets_list=datasets_list,
            css_content=css_content,
            js_content=js_content,
        )

        template = self.env.get_template("skeleton.html")
        return template.render(context)