import os
import sys

import pytest
from playwright.sync_api import Page, expect

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dashboard_engine.generator import DashboardGenerator


@pytest.fixture(scope="module")
def csv_bubble_data(tmp_path_factory):
    csv_content = """mois_annee,x_metric,y_metric,r_metric,category
2024-01,1,10,5,A
2024-02,2,20,10,B
2024-03,3,15,7,A
2024-04,4,25,12,B
2024-05,5,18,9,A
2024-06,6,30,15,B
2025-01,3,15,8,A
2025-02,4,25,12,B
2025-03,5,22,10,A
2025-04,6,28,14,B
2025-05,7,35,18,A
2025-06,8,40,20,B
"""
    fn = tmp_path_factory.mktemp("data") / "bubble_data.csv"
    fn.write_text(csv_content, encoding="utf-8")
    return str(fn)


@pytest.fixture(scope="module")
def bubble_report(csv_bubble_data):
    output_dir = os.path.join(PROJECT_ROOT, "output")
    output_report = os.path.join(output_dir, "_test_bubble.html")

    with open(csv_bubble_data, "r", encoding="utf-8") as f:
        csv_content = f.read()

    config = {
        "title": "QA Bubble",
        "widgets": [
            {
                "type": "bubble",
                "title": "Bubble Correlation",
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

    generator = DashboardGenerator()
    html_content = generator.generate(config, [csv_content])

    os.makedirs(output_dir, exist_ok=True)
    with open(output_report, "w", encoding="utf-8") as f:
        f.write(html_content)

    return "file:///{path}".format(path=output_report.replace(os.sep, "/"))


def test_bubble_renders_circles(page: Page, bubble_report):
    page.goto(bubble_report)

    year_select = page.locator('select[data-testid="widget-year-select"]').first
    year_select.select_option("2025")

    circles = page.locator("g.bubble-layer circle")
    expect(circles.first).to_be_visible()
    assert circles.count() >= 6