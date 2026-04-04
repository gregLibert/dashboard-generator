import os
import sys

import pytest
from playwright.sync_api import Page, expect

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dashboard_engine.generator import DashboardGenerator


@pytest.fixture(scope="module")
def csv_heatmap_data(tmp_path_factory):
    csv_content = """mois_annee,x_cat,y_cat,value
2024-01,Mon,AM,10
2024-01,Mon,PM,20
2024-02,Tue,AM,15
2024-02,Tue,PM,25
2024-03,Wed,AM,12
2024-03,Wed,PM,22
2025-01,Mon,AM,15
2025-01,Mon,PM,25
2025-02,Tue,AM,18
2025-02,Tue,PM,28
2025-03,Wed,AM,20
2025-03,Wed,PM,30
"""
    fn = tmp_path_factory.mktemp("data") / "heatmap_data.csv"
    fn.write_text(csv_content, encoding="utf-8")
    return str(fn)


@pytest.fixture(scope="module")
def heatmap_report(csv_heatmap_data):
    output_dir = os.path.join(PROJECT_ROOT, "output")
    output_report = os.path.join(output_dir, "_test_heatmap.html")

    with open(csv_heatmap_data, "r", encoding="utf-8") as f:
        csv_content = f.read()

    config = {
        "title": "QA Heatmap",
        "widgets": [
            {
                "type": "heatmap",
                "title": "Heatmap Matrix",
                "datasetIndex": 0,
                "mapping": {
                    "date": "mois_annee",
                    "x": "x_cat",
                    "y": "y_cat",
                    "value": "value",
                },
            }
        ],
    }

    generator = DashboardGenerator()
    html_content = generator.generate(config, [csv_content])

    os.makedirs(output_dir, exist_ok=True)
    with open(output_report, "w", encoding="utf-8") as f:
        f.write(html_content)

    return "file:///{path}".format(path=output_report.replace(os.sep, "/"))


def test_heatmap_renders_cells(page: Page, heatmap_report):
    page.goto(heatmap_report)

    year_select = page.locator('select[data-testid="widget-year-select"]').first
    year_select.select_option("2025")

    rects = page.locator("g.heatmap-layer rect")
    expect(rects.first).to_be_visible()
    assert rects.count() >= 6

