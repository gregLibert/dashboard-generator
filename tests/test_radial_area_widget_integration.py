import os
import sys

import pytest
from playwright.sync_api import Page, expect

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dashboard_engine.generator import DashboardGenerator

_RADIAL_WIDGET_CONFIG = {
    "type": "radial_area",
    "title": "Radial Cyclic Series",
    "datasetIndex": 0,
    "mapping": {
        "date": "mois_annee",
        "value": "value",
    },
    "options": {
        "timeUnit": "month",
        "valueUnit": "°C",
    },
}

_RADIAL_FULL_CSV = """mois_annee,value
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

_RADIAL_DOM_SCENARIOS = [
    {
        "id": "nominal_2025_paths_and_svg",
        "csv": _RADIAL_FULL_CSV,
        "select_year": "2025",
        "min_paths": 1,
        "expect_svg_visible": True,
    },
    {
        "id": "nominal_2024_paths_and_svg",
        "csv": _RADIAL_FULL_CSV,
        "select_year": "2024",
        "min_paths": 1,
        "expect_svg_visible": True,
    },
    {
        "id": "edge_sparse_two_months_still_draws",
        "csv": """mois_annee,value
2025-01,5
2025-02,9
""",
        "select_year": "2025",
        "min_paths": 1,
        "expect_svg_visible": True,
    },
    {
        "id": "edge_unusable_non_numeric_value",
        "csv": """mois_annee,value
2025-01,not_a_number
""",
        "select_year": "2025",
        "expect_unusable_hint": True,
    },
]


def _write_radial_report(scenario_id: str, csv_content: str) -> str:
    output_dir = os.path.join(PROJECT_ROOT, "output")
    output_report = os.path.join(output_dir, f"_test_radial_{scenario_id}.html")
    config = {"title": "QA Radial Area", "widgets": [_RADIAL_WIDGET_CONFIG]}
    generator = DashboardGenerator()
    html_content = generator.generate(config, [csv_content], js_bundle_mode="full")
    os.makedirs(output_dir, exist_ok=True)
    with open(output_report, "w", encoding="utf-8") as f:
        f.write(html_content)
    return "file:///{path}".format(path=output_report.replace(os.sep, "/"))


@pytest.fixture(scope="module")
def radial_case_bundle(request):
    case = request.param
    url = _write_radial_report(case["id"], case["csv"])
    return {**case, "file_url": url}


@pytest.mark.parametrize(
    "radial_case_bundle",
    _RADIAL_DOM_SCENARIOS,
    indirect=True,
    ids=[c["id"] for c in _RADIAL_DOM_SCENARIOS],
)
def test_radial_area_widget_dom_matches_data_scenario(page: Page, radial_case_bundle):
    """Radial area DOM reflects the dataset: g.radial-area-layer path + visible svg, or unusable hint."""
    page.goto(radial_case_bundle["file_url"])

    year_select = page.locator('select[data-testid="widget-year-select"]').first
    year_select.select_option(radial_case_bundle["select_year"])

    if radial_case_bundle.get("expect_unusable_hint"):
        hint = page.locator(".sub-chart .hint")
        expect(hint).to_be_visible()
        expect(hint).to_contain_text("Aucune donnée exploitable")
        return

    svg = page.locator(".sub-chart svg")
    if radial_case_bundle.get("expect_svg_visible"):
        expect(svg).to_be_visible()

    paths = svg.locator("g.radial-area-layer path")
    assert paths.count() >= radial_case_bundle["min_paths"]
