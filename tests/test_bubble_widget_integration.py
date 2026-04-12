import os
import sys

import pytest
from playwright.sync_api import Page, expect

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dashboard_engine.generator import DashboardGenerator

_BUBBLE_WIDGET_CONFIG = {
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

# Same component, different CSV shapes: nominal coverage + edge cases (empty year, unusable metrics).
_BUBBLE_DOM_SCENARIOS = [
    {
        "id": "nominal_2025_six_months",
        "csv": """mois_annee,x_metric,y_metric,r_metric,category
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
""",
        "select_year": "2025",
        "min_circles": 6,
        "expect_first_circle_visible": True,
    },
    {
        "id": "nominal_2024_six_months",
        "csv": """mois_annee,x_metric,y_metric,r_metric,category
2024-01,1,10,5,A
2024-02,2,20,10,B
2024-03,3,15,7,A
2024-04,4,25,12,B
2024-05,5,18,9,A
2024-06,6,30,15,B
2025-01,3,15,8,A
""",
        "select_year": "2024",
        "min_circles": 6,
        "expect_first_circle_visible": True,
    },
    {
        "id": "edge_single_month_one_circle",
        "csv": """mois_annee,x_metric,y_metric,r_metric,category
2025-01,1,1,1,A
""",
        "select_year": "2025",
        "min_circles": 1,
        "expect_first_circle_visible": True,
    },
    {
        "id": "edge_yoy_n_minus_1_panel_empty",
        "csv": """mois_annee,x_metric,y_metric,r_metric,category
2025-01,3,15,8,A
2025-02,4,25,12,B
2025-03,5,22,10,A
2025-04,6,28,14,B
2025-05,7,35,18,A
2025-06,8,40,20,B
""",
        "select_year": "2025",
        "ensure_yoy_on": True,
        "expect_first_subchart_panel_hint": True,
        "expect_second_subchart_min_circles": 6,
    },
    {
        "id": "edge_rows_but_non_numeric_metrics",
        "csv": """mois_annee,x_metric,y_metric,r_metric,category
2025-01,x,y,z,A
""",
        "select_year": "2025",
        "expect_unusable_hint_in_panel": True,
    },
]


def _write_bubble_report(scenario_id: str, csv_content: str) -> str:
    output_dir = os.path.join(PROJECT_ROOT, "output")
    output_report = os.path.join(output_dir, f"_test_bubble_{scenario_id}.html")
    config = {
        "title": "QA Bubble",
        "widgets": [_BUBBLE_WIDGET_CONFIG],
    }
    generator = DashboardGenerator()
    html_content = generator.generate(config, [csv_content], js_bundle_mode="full")
    os.makedirs(output_dir, exist_ok=True)
    with open(output_report, "w", encoding="utf-8") as f:
        f.write(html_content)
    return "file:///{path}".format(path=output_report.replace(os.sep, "/"))


@pytest.fixture(scope="module")
def bubble_case_bundle(request):
    case = request.param
    url = _write_bubble_report(case["id"], case["csv"])
    return {**case, "file_url": url}


@pytest.mark.parametrize(
    "bubble_case_bundle",
    _BUBBLE_DOM_SCENARIOS,
    indirect=True,
    ids=[c["id"] for c in _BUBBLE_DOM_SCENARIOS],
)
def test_bubble_widget_dom_matches_data_scenario(page: Page, bubble_case_bundle):
    """Bubble chart DOM reflects the dataset: circles in .bubble-layer or documented empty states."""
    page.goto(bubble_case_bundle["file_url"])

    year_select = page.locator('select[data-testid="widget-year-select"]').first
    year_select.select_option(bubble_case_bundle["select_year"])

    if bubble_case_bundle.get("ensure_yoy_on"):
        yoy = page.locator(".ctrl-yoy input")
        yoy.check()

    if bubble_case_bundle.get("expect_first_subchart_panel_hint"):
        subs = page.locator(".sub-chart")
        expect(subs).to_have_count(2)
        hint_n1 = subs.nth(0).locator(".bubble-chart .hint")
        expect(hint_n1).to_be_visible()
        expect(hint_n1).to_contain_text("Aucune donnée pour cette année")
        circles_n = subs.nth(1).locator("g.bubble-layer circle")
        expect(circles_n.first).to_be_visible()
        assert circles_n.count() >= bubble_case_bundle["expect_second_subchart_min_circles"]
        return

    if bubble_case_bundle.get("expect_unusable_hint_in_panel"):
        # With YoY on by default, N-1 may show the empty-year hint while N shows unusable metrics.
        exploitable = page.get_by_text("Aucune donnée exploitable", exact=False)
        expect(exploitable.first).to_be_visible()
        return

    circles = page.locator("g.bubble-layer circle")
    if bubble_case_bundle.get("expect_first_circle_visible"):
        expect(circles.first).to_be_visible()
    assert circles.count() >= bubble_case_bundle["min_circles"]
