# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import jinja2
import os
import json
import logging
import io  # Nécessaire pour io.open (utf-8) en Python 2
from datetime import datetime

logger = logging.getLogger("DashboardGenerator")

class DashboardGenerator(object):
    def __init__(self):
        self.root_path = os.path.dirname(os.path.abspath(__file__))
        self.assets_path = os.path.join(self.root_path, 'assets')
        
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(self.assets_path),
            autoescape=jinja2.select_autoescape(['html', 'xml'])
        )

    def _read_asset(self, filename):
        try:
            with io.open(os.path.join(self.assets_path, filename), 'r', encoding='utf-8') as f:
                return f.read()
        except IOError: # FileNotFoundError n'existe pas en Python 2
            return "/* Error: {} not found */".format(filename)

    def generate(self, config, datasets_list):
        # 1. Assets
        css_content = self._read_asset('style.css')

        # 2. Assets JS : Lecture et Concaténation
        js_files = [
            'js/utils.js',
            'js/base_widget.js', 
            'js/sankey_widget.js',
            'js/financial_sankey_widget.js',
            'js/evolution_widget.js',
            'js/sunburst_widget.js',
            'js/horizon_widget.js',
            'js/main.js'
        ]
        
        js_content = ""
        # On ajoute les imports D3 une seule fois au tout début
        js_content += 'import * as d3 from "https://cdn.jsdelivr.net/npm/d3@7/+esm";\n'
        js_content += 'import { sankey, sankeyLinkHorizontal, sankeyJustify, sankeyLeft } from "https://cdn.jsdelivr.net/npm/d3-sankey@0.12/+esm";\n'

        for js_file in js_files:
            content = self._read_asset(js_file)
            js_content += "\n// --- {} ---\n{}\n".format(js_file, content)
        
        # 2. Date de génération
        generation_date_str = datetime.now().strftime("%Y%m%d")

        # 3. Préparation de la config JSON
        full_config = config.copy()
        full_config['generation_date'] = generation_date_str

        # 4. Context Jinja
        context = {
            'title': config.get('title', 'Dashboard'),
            'subtitle': config.get('subtitle', ''),
            
            # On passe la config complète au JS (+ la date)
            'config_json': json.dumps(full_config),
            
            'datasets': datasets_list,
            'css_content': css_content,
            'js_content': js_content,
            
            'include_dev_markup': config.get('dev_mode', False)
        }

        template = self.env.get_template('skeleton.html')
        
        return template.render(context)