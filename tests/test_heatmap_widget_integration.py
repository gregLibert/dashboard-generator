import os
import sys

import pytest
from playwright.sync_api import Page, expect

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dashboard_engine.generator import DashboardGenerator

_HEATMAP_WIDGET_CONFIG = {
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

_HEATMAP_DOM_SCENARIOS = [
    {
        "id": "nominal_2025_six_cells",
        "csv": """mois_annee,x_cat,y_cat,value
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
""",
        "select_year": "2025",
        "min_rects": 6,
        "expect_first_rect_visible": True,
    },
    {
        "id": "nominal_2024_six_cells",
        "csv": """mois_annee,x_cat,y_cat,value
2024-01,Mon,AM,10
2024-01,Mon,PM,20
2024-02,Tue,AM,15
2024-02,Tue,PM,25
2024-03,Wed,AM,12
2024-03,Wed,PM,22
2025-01,Mon,AM,15
""",
        "select_year": "2024",
        "min_rects": 6,
        "expect_first_rect_visible": True,
    },
    {
        "id": "edge_single_cell",
        "csv": """mois_annee,x_cat,y_cat,value
2025-01,Mon,AM,42
""",
        "select_year": "2025",
        "min_rects": 1,
        "expect_first_rect_visible": True,
    },
    {
        "id": "edge_yoy_n_minus_1_panel_empty",
        "csv": """mois_annee,x_cat,y_cat,value
2025-01,Mon,AM,15
2025-01,Mon,PM,25
2025-02,Tue,AM,18
2025-02,Tue,PM,28
2025-03,Wed,AM,20
2025-03,Wed,PM,30
""",
        "select_year": "2025",
        "ensure_yoy_on": True,
        "expect_first_subchart_panel_hint": True,
        "expect_second_subchart_min_rects": 6,
    },
    {
        "id": "edge_rows_but_non_numeric_value",
        "csv": """mois_annee,x_cat,y_cat,value
2025-01,Mon,AM,not_a_number
""",
        "select_year": "2025",
        "expect_unusable_hint_in_panel": True,
    },
]


def _write_heatmap_report(scenario_id: str, csv_content: str) -> str:
    output_dir = os.path.join(PROJECT_ROOT, "output")
    output_report = os.path.join(output_dir, f"_test_heatmap_{scenario_id}.html")
    config = {"title": "QA Heatmap", "widgets": [_HEATMAP_WIDGET_CONFIG]}
    generator = DashboardGenerator()
    html_content = generator.generate(config, [csv_content], js_bundle_mode="full")
    os.makedirs(output_dir, exist_ok=True)
    with open(output_report, "w", encoding="utf-8") as f:
        f.write(html_content)
    return "file:///{path}".format(path=output_report.replace(os.sep, "/"))


@pytest.fixture(scope="module")
def heatmap_case_bundle(request):
    case = request.param
    url = _write_heatmap_report(case["id"], case["csv"])
    return {**case, "file_url": url}


@pytest.mark.parametrize(
    "heatmap_case_bundle",
    _HEATMAP_DOM_SCENARIOS,
    indirect=True,
    ids=[c["id"] for c in _HEATMAP_DOM_SCENARIOS],
)
def test_heatmap_widget_dom_matches_data_scenario(page: Page, heatmap_case_bundle):
    """Heatmap DOM reflects the dataset: rects in .heatmap-layer or documented empty states."""
    page.goto(heatmap_case_bundle["file_url"])

    year_select = page.locator('select[data-testid="widget-year-select"]').first
    year_select.select_option(heatmap_case_bundle["select_year"])

    if heatmap_case_bundle.get("ensure_yoy_on"):
        page.locator(".ctrl-yoy input").check()

    if heatmap_case_bundle.get("expect_first_subchart_panel_hint"):
        subs = page.locator(".sub-chart")
        expect(subs).to_have_count(2)
        hint_n1 = subs.nth(0).locator(".heatmap-chart .hint")
        expect(hint_n1).to_be_visible()
        expect(hint_n1).to_contain_text("Aucune donnée pour cette année")
        rects_n = subs.nth(1).locator("g.heatmap-layer rect")
        expect(rects_n.first).to_be_visible()
        assert rects_n.count() >= heatmap_case_bundle["expect_second_subchart_min_rects"]
        return

    if heatmap_case_bundle.get("expect_unusable_hint_in_panel"):
        exploitable = page.get_by_text("Aucune donnée exploitable", exact=False)
        expect(exploitable.first).to_be_visible()
        return

    rects = page.locator("g.heatmap-layer rect")
    if heatmap_case_bundle.get("expect_first_rect_visible"):
        expect(rects.first).to_be_visible()
    assert rects.count() >= heatmap_case_bundle["min_rects"]
