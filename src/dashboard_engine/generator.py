# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import base64
import gzip
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

# Always inlined: shared helpers, base class, bootstrap (widget implementations appended between base and main).
JS_MANDATORY_PATHS = (
    "js/utils.js",
    "js/base_widget.js",
)
JS_MAIN_PATH = "js/main.js"

# One widget implementation file per dashboard widget type (kept in sync with main.js WidgetRegistry).
WIDGET_TYPE_TO_JS_FILE = {
    "sankey": "js/sankey_widget.js",
    "financial_sankey": "js/financial_sankey_widget.js",
    "evolution": "js/evolution_widget.js",
    "sunburst": "js/sunburst_widget.js",
    "horizon": "js/horizon_widget.js",
    "nested_treemap": "js/treemap_widget.js",
    "stacked_area": "js/stacked_area_widget.js",
    "bubble": "js/bubble_widget.js",
    "heatmap": "js/heatmap_widget.js",
    "radial_area": "js/radial_area_widget.js",
}

WIDGET_TYPES_USING_D3_SANKEY = frozenset({"sankey", "financial_sankey"})

D3_CDN_IMPORT = 'import * as d3 from "https://cdn.jsdelivr.net/npm/d3@7/+esm";\n'
D3_SANKEY_CDN_IMPORT = (
    'import { sankey, sankeyLinkHorizontal, sankeyJustify, sankeyLeft } '
    'from "https://cdn.jsdelivr.net/npm/d3-sankey@0.12/+esm";\n'
)

# Encoding marker stored on <script> and read by main.js (dataset API uses data-csv-encoding).
CSV_ENCODING_GZIP_BASE64 = "gzip-base64"


def _gzip_compress_bytes(data_bytes):
    """Compress bytes with gzip (stdlib only); supports Python 2.7 (no gzip.compress)."""
    if hasattr(gzip, "compress"):
        return gzip.compress(data_bytes, compresslevel=9)
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=9) as gz:
        gz.write(data_bytes)
    return buf.getvalue()


def _dataset_csv_to_bytes(csv_string):
    """Encode a CSV text string as UTF-8 bytes (Python 2/3)."""
    if isinstance(csv_string, bytes):
        return csv_string
    return csv_string.encode("utf-8")


def normalize_dataset_for_template(csv_string, compress_data):
    """Return a template-ready dataset dict: {encoding, payload} (pure, for tests)."""
    if compress_data:
        raw = _dataset_csv_to_bytes(csv_string)
        compressed = _gzip_compress_bytes(raw)
        b64 = base64.b64encode(compressed)
        if isinstance(b64, bytes):
            b64 = b64.decode("ascii")
        return {"encoding": CSV_ENCODING_GZIP_BASE64, "payload": b64}
    return {"encoding": None, "payload": csv_string}


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
    def _build_context(config, full_config, datasets_normalized, css_content, js_content):
        """Build the Jinja2 template context (pure, for tests)."""
        title = config.get("title", "Dashboard")
        subtitle = config.get("subtitle", "")
        include_dev_markup = config.get("dev_mode", False)

        return {
            "title": title,
            "subtitle": subtitle,
            "config_json": json.dumps(full_config),
            "datasets": datasets_normalized,
            "css_content": css_content,
            "js_content": js_content,
            "include_dev_markup": include_dev_markup,
        }

    @staticmethod
    def _widgets_list(config):
        widgets = config.get("widgets")
        if widgets is None:
            return []
        if not isinstance(widgets, list):
            raise TypeError("config['widgets'] must be a list when provided")
        return widgets

    @classmethod
    def collect_js_asset_paths(cls, config):
        """Return ordered JS asset paths: mandatory + widget-specific (no duplicates), then main.

        Also returns whether the d3-sankey ESM import must be prepended.
        """
        seen = set()
        widget_paths = []
        need_sankey = False

        for w in cls._widgets_list(config):
            if not isinstance(w, dict):
                continue
            wtype = w.get("type")
            if not isinstance(wtype, basestring):
                continue
            if wtype not in WIDGET_TYPE_TO_JS_FILE:
                valid = ", ".join(sorted(WIDGET_TYPE_TO_JS_FILE.keys()))
                raise ValueError(
                    "Unknown widget type: {0!r}. Valid types: {1}".format(wtype, valid)
                )
            if wtype in WIDGET_TYPES_USING_D3_SANKEY:
                need_sankey = True
            rel = WIDGET_TYPE_TO_JS_FILE[wtype]
            if rel not in seen:
                seen.add(rel)
                widget_paths.append(rel)

        ordered = list(JS_MANDATORY_PATHS) + widget_paths + [JS_MAIN_PATH]
        return ordered, need_sankey

    def _build_js_content(self, js_files, include_d3_sankey):
        """Concatenate JS assets and prepend D3 (+ optional d3-sankey) imports."""
        js_content_parts = [D3_CDN_IMPORT]
        if include_d3_sankey:
            js_content_parts.append(D3_SANKEY_CDN_IMPORT)

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

    def _normalize_datasets(self, datasets_list, compress_data):
        return [
            normalize_dataset_for_template(ds, compress_data) for ds in datasets_list
        ]

    def generate(self, config, datasets_list, compress_data=False):
        """Generate a standalone HTML dashboard.

        :param config: dashboard configuration dictionary.
        :param datasets_list: list of CSV strings used by the widgets.
        :param compress_data: if True, gzip-compress each CSV (stdlib) and embed as base64;
            the client decompresses with DecompressionStream('gzip') before d3.csvParse.
        :return: rendered HTML string.
        """
        self._validate_inputs(config, datasets_list)

        js_files, include_d3_sankey = self.collect_js_asset_paths(config)
        css_content = self._read_asset("style.css")
        js_content = self._build_js_content(js_files, include_d3_sankey)

        full_config = self._build_full_config(config)
        datasets_normalized = self._normalize_datasets(datasets_list, compress_data)
        context = self._build_context(
            config=config,
            full_config=full_config,
            datasets_normalized=datasets_normalized,
            css_content=css_content,
            js_content=js_content,
        )

        template = self.env.get_template("skeleton.html")
        return template.render(context)
