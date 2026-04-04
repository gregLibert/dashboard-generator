import os
import sys

import pytest
from playwright.sync_api import Page, expect

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dashboard_engine.generator import DashboardGenerator


@pytest.fixture(scope="module")
def csv_data_file(tmp_path_factory):
    """Dataset for stacked area with 2 categories over full years 2024 and 2025."""
    csv_content = """mois_annee,category,amount
2024-01,A,10
2024-01,B,20
2024-02,A,30
2024-02,B,40
2024-03,A,20
2024-03,B,10
2024-04,A,15
2024-04,B,25
2024-05,A,10
2024-05,B,30
2024-06,A,5
2024-06,B,35
2024-07,A,20
2024-07,B,20
2024-08,A,25
2024-08,B,15
2024-09,A,30
2024-09,B,10
2024-10,A,35
2024-10,B,5
2024-11,A,40
2024-11,B,10
2024-12,A,45
2024-12,B,15
2025-01,A,50
2025-01,B,60
2025-02,A,55
2025-02,B,65
2025-03,A,45
2025-03,B,55
2025-04,A,40
2025-04,B,50
2025-05,A,35
2025-05,B,45
2025-06,A,30
2025-06,B,40
2025-07,A,25
2025-07,B,35
2025-08,A,20
2025-08,B,30
2025-09,A,15
2025-09,B,25
2025-10,A,10
2025-10,B,20
2025-11,A,5
2025-11,B,15
2025-12,A,10
2025-12,B,10
"""
    fn = tmp_path_factory.mktemp("data") / "stacked_area.csv"
    fn.write_text(csv_content, encoding="utf-8")
    return str(fn)


@pytest.fixture(scope="module")
def stacked_area_report(csv_data_file):
    output_dir = os.path.join(PROJECT_ROOT, "output")
    output_report = os.path.join(output_dir, "_test_stacked_area.html")

    with open(csv_data_file, "r", encoding="utf-8") as f:
        csv_content = f.read()

    config = {
        "title": "QA Stacked Area",
        "widgets": [
            {
                "type": "stacked_area",
                "title": "Stacked Area (Abs vs 100%)",
                "datasetIndex": 0,
                "mapping": {
                    "date": "mois_annee",
                    "value": "amount",
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


def get_chart_container(page: Page, year: int):
    return page.locator(".sub-chart", has=page.locator("h4", has_text=str(year)))


def test_stacked_area_svg_and_paths(page: Page, stacked_area_report):
    """Check that the stacked area widget renders SVG areas for the latest year."""
    page.goto(stacked_area_report)

    # Select latest year (2025).
    year_select = page.locator('select[data-testid="widget-year-select"]').first
    year_select.select_option("2025")

    svg_2025 = get_chart_container(page, 2025).locator("svg")

    expect(svg_2025).to_be_visible()

    # There should be at least one area path (stacked layer) for 2025.
    area_paths = svg_2025.locator("path")
    assert area_paths.count() >= 1



def test_stacked_area_toggle_normalized(page: Page, stacked_area_report):
    """Verify that toggling 100% stacked mode switches the widget to normalized state."""
    page.goto(stacked_area_report)

    # Use 2025.
    year_select = page.locator('select[data-testid="widget-year-select"]').first
    year_select.select_option("2025")

    # Toggle 100% stacked.
    toggle = page.locator(".ctrl-normalized-toggle input")
    toggle.check()

    # The widget rerenders the SVG after toggling, so we must re-query it.
    svg_2025 = get_chart_container(page, 2025).locator("svg")
    expect(svg_2025).to_be_visible()

    # After toggle: the SVG should be marked as normalized via data attribute.
    is_normalized = svg_2025.get_attribute("data-normalized")
    assert is_normalized == "true"


def test_stacked_area_same_dimensions_n_and_n1(page: Page, stacked_area_report):
    """Ensure that N and N-1 charts share the exact same SVG dimensions."""
    page.goto(stacked_area_report)

    # Ensure YoY comparison is enabled.
    yoy_toggle = page.locator(".ctrl-yoy input")
    yoy_toggle.check()

    # Fix on 2025 so that N=2025 and N-1=2024.
    year_select = page.locator('select[data-testid="widget-year-select"]').first
    year_select.select_option("2025")

    svg_2024 = get_chart_container(page, 2024).locator("svg")
    svg_2025 = get_chart_container(page, 2025).locator("svg")

    expect(svg_2024).to_be_visible()
    expect(svg_2025).to_be_visible()

    box_2024 = svg_2024.bounding_box()
    box_2025 = svg_2025.bounding_box()

    assert box_2024 is not None and box_2025 is not None

    # Allow 1px tolerance as in other widgets.
    assert abs(box_2024["width"] - box_2025["width"]) <= 1, "Widths for N and N-1 should be identical"
    assert abs(box_2024["height"] - box_2025["height"]) <= 1, "Heights for N and N-1 should be identical"


def test_stacked_area_layers_stay_inside_svg(page: Page, stacked_area_report):
    """Ensure stacked area layers do not overflow the SVG box (no visible truncation)."""
    page.goto(stacked_area_report)

    # Single year mode (YoY disabled) is where overflow regressions happened.
    yoy_toggle = page.locator(".ctrl-yoy input")
    yoy_toggle.uncheck()

    year_select = page.locator('select[data-testid="widget-year-select"]').first
    year_select.select_option("2025")

    svg_2025 = get_chart_container(page, 2025).locator("svg")
    expect(svg_2025).to_be_visible()

    svg_box = svg_2025.bounding_box()
    assert svg_box is not None

    layers = svg_2025.locator("path.stacked-area-layer")
    assert layers.count() >= 1

    # All layer bounding boxes should be fully contained within the SVG box.
    for i in range(layers.count()):
        layer = layers.nth(i)
        box = layer.bounding_box()
        assert box is not None

        # Allow a small tolerance for strokes and subpixel rendering.
        tol = 2
        assert box["x"] >= svg_box["x"] - tol
        assert box["y"] >= svg_box["y"] - tol
        assert (box["x"] + box["width"]) <= (svg_box["x"] + svg_box["width"] + tol)
        assert (box["y"] + box["height"]) <= (svg_box["y"] + svg_box["height"] + tol)
