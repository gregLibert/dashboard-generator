"""
Playwright integration tests for the directed chord diagram widget.
"""
import os
import sys

import pytest
from playwright.sync_api import Page, expect

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dashboard_engine.generator import DashboardGenerator


@pytest.fixture(scope="module")
def csv_chord_data(tmp_path_factory):
    """Flat transitions with mois_annee for BaseWidget.processData."""
    csv_content = """mois_annee,source_family,target_family,volume
2024-01,A,B,10
2024-01,B,A,5
2024-01,A,C,3
2024-02,B,C,8
2024-02,C,A,2
2025-01,A,B,12
2025-01,B,C,7
2025-02,A,C,4
2025-02,C,B,6
"""
    fn = tmp_path_factory.mktemp("data") / "chord_transitions.csv"
    fn.write_text(csv_content, encoding="utf-8")
    return str(fn)


@pytest.fixture(scope="module")
def chord_report_summable(csv_chord_data):
    return _write_chord_report(
        csv_chord_data,
        "_test_directed_chord_summable.html",
        summable=True,
        title="Directed Chord (summable)",
    )


@pytest.fixture(scope="module")
def chord_report_not_summable(csv_chord_data):
    return _write_chord_report(
        csv_chord_data,
        "_test_directed_chord_not_summable.html",
        summable=False,
        title="Directed Chord (instant)",
    )


def _write_chord_report(csv_path, output_name, summable, title):
    output_dir = os.path.join(PROJECT_ROOT, "output")
    output_report = os.path.join(output_dir, output_name)

    with open(csv_path, "r", encoding="utf-8") as f:
        csv_content = f.read()

    config = {
        "title": "QA Directed Chord",
        "widgets": [
            {
                "type": "directed_chord",
                "title": title,
                "datasetIndex": 0,
                "mapping": {
                    "date": "mois_annee",
                    "source": "source_family",
                    "target": "target_family",
                    "value": "volume",
                },
                "options": {"summable": summable},
            }
        ],
    }

    generator = DashboardGenerator()
    html_content = generator.generate(config, [csv_content], js_bundle_mode="full")

    os.makedirs(output_dir, exist_ok=True)
    with open(output_report, "w", encoding="utf-8") as f:
        f.write(html_content)

    return "file:///{path}".format(path=output_report.replace(os.sep, "/"))


def test_directed_chord_svg_contains_arcs_and_ribbons(page: Page, chord_report_summable):
    """Directed chord renders SVG groups with arc and ribbon paths."""
    page.goto(chord_report_summable)

    year_select = page.locator('select[data-testid="widget-year-select"]').first
    year_select.select_option("2025")

    svg = page.locator("svg.directed-chord-svg")
    expect(svg).to_be_visible()

    ribbons = page.locator("path.directed-chord-ribbon")
    arcs = page.locator("path.directed-chord-arc")
    expect(ribbons.first).to_be_visible()
    expect(arcs.first).to_be_visible()
    assert ribbons.count() >= 1
    assert arcs.count() >= 1
    page.pause()


def test_directed_chord_summable_false_hides_period_controls(page: Page, chord_report_not_summable):
    """When options.summable is false, period type/value controls are hidden (CSS)."""
    page.goto(chord_report_not_summable)

    chart = page.locator(".chart-box", has=page.locator("h2", has_text="Directed Chord (instant)"))
    expect(chart.locator(".ctrl-period-type")).to_be_hidden()
    expect(chart.locator(".ctrl-period-value")).to_be_hidden()

    svg = chart.locator("svg.directed-chord-svg")
    expect(svg).to_be_visible()
    page.pause()