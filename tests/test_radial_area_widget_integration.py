import os
import sys

import pytest
from playwright.sync_api import Page, expect

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dashboard_engine.generator import DashboardGenerator


@pytest.fixture(scope="module")
def csv_radial_data(tmp_path_factory):
    csv_content = """mois_annee,value
2024-01,10
2024-01,14
2024-02,15
2024-02,18
2024-03,18
2024-03,12
2024-04,20
2024-04,23
2024-05,22
2024-05,19
2024-06,19
2024-06,16
2024-07,15
2024-07,18
2024-08,17
2024-08,21
2024-09,21
2024-09,24
2024-10,25
2024-10,28
2024-11,23
2024-11,26
2024-12,18
2024-12,20
2025-01,12
2025-01,16
2025-02,16
2025-02,20
2025-03,20
2025-03,24
2025-04,24
2025-04,28
2025-05,26
2025-05,22
2025-06,22
2025-06,18
2025-07,18
2025-07,20
2025-08,20
2025-08,24
2025-09,24
2025-09,28
2025-10,28
2025-10,30
2025-11,26
2025-11,27
2025-12,21
2025-12,23
"""
    fn = tmp_path_factory.mktemp("data") / "radial_data.csv"
    fn.write_text(csv_content, encoding="utf-8")
    return str(fn)


@pytest.fixture(scope="module")
def radial_report(csv_radial_data):
    output_dir = os.path.join(PROJECT_ROOT, "output")
    output_report = os.path.join(output_dir, "_test_radial.html")

    with open(csv_radial_data, "r", encoding="utf-8") as f:
        csv_content = f.read()

    config = {
        "title": "QA Radial Area",
        "widgets": [
            {
                "type": "radial_area",
                "title": "Radial Cyclic Series",
                "datasetIndex": 0,
                "mapping": {
                    "date": "mois_annee",
                    "value": "value",
                },
                "options": {
                    "timeUnit": "month",
                    "valueUnit": "°C"
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


def test_radial_area_renders_paths(page: Page, radial_report):
    page.goto(radial_report)

    year_select = page.locator('select[data-testid="widget-year-select"]').first
    year_select.select_option("2025")

    svg = page.locator(".sub-chart svg")
    expect(svg).to_be_visible()

    paths = svg.locator("g.radial-area-layer path")
    assert paths.count() >= 1

