"""Browser check: gzip+base64 datasets decompress and widgets still mount."""
import os
import sys

import pytest
from playwright.sync_api import Page, expect

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dashboard_engine.generator import DashboardGenerator


@pytest.mark.parametrize("compress_data", [False, True], ids=["plain_csv", "gzip_base64"])
def test_bubble_dashboard_renders_with_compression_toggle(
    page: Page, tmp_path, compress_data
):
    csv_content = """mois_annee,x_metric,y_metric,r_metric,category
2025-01,1,1,1,A
2025-02,2,2,2,B
"""
    config = {
        "title": "QA Compress",
        "widgets": [
            {
                "type": "bubble",
                "title": "B",
                "datasetIndex": 0,
                "mapping": {
                    "date": "mois_annee",
                    "x": "x_metric",
                    "y": "y_metric",
                    "r": "r_metric",
                    "category": "category",
                },
            }
        ],
    }
    gen = DashboardGenerator()
    html = gen.generate(config, [csv_content], compress_data=compress_data)
    out = tmp_path / "dash.html"
    out.write_text(html, encoding="utf-8")
    page.goto(out.as_uri())

    circles = page.locator("g.bubble-layer circle")
    expect(circles.first).to_be_visible()
    assert circles.count() >= 2
