"""
Playwright integration tests for the ribbon chart widget.
"""
import os
import sys

import pytest
from playwright.sync_api import Page, expect

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dashboard_engine.generator import DashboardGenerator

CATEGORIES = ("Alpha", "Beta", "Gamma", "Delta")


def _amounts_for_month(month):
    """Month 4 inverts the leader so stack ranking swaps (Alpha → Delta on top)."""
    if month == 4:
        return {"Alpha": 8, "Beta": 18, "Gamma": 28, "Delta": 48}
    amounts_by_cat = {
        "Alpha": [23, 25, 24, 22, 26, 28, 27, 29, 30, 28, 26, 24],
        "Beta": [18, 17, 19, 20, 21, 20, 22, 21, 19, 18, 20, 21],
        "Gamma": [12, 14, 13, 15, 14, 16, 15, 14, 13, 12, 14, 15],
        "Delta": [8, 9, 7, 10, 9, 11, 10, 9, 8, 10, 9, 8],
    }
    return {cat: amounts_by_cat[cat][month - 1] for cat in CATEGORIES}


def _build_full_year_csv():
    """Four categories, 12 months for 2024 and 2025."""
    lines = ["mois_annee,category,amount"]
    for year in (2024, 2025):
        for month in range(1, 13):
            key = f"{year}-{month:02d}"
            amounts = _amounts_for_month(month)
            for cat in CATEGORIES:
                bump = (year - 2024) * 5
                lines.append(f"{key},{cat},{amounts[cat] + bump}")
    return "\n".join(lines) + "\n"


@pytest.fixture(scope="module")
def csv_ribbon_data(tmp_path_factory):
    fn = tmp_path_factory.mktemp("data") / "ribbon_chart.csv"
    fn.write_text(_build_full_year_csv(), encoding="utf-8")
    return str(fn)


@pytest.fixture(scope="module")
def ribbon_chart_report(csv_ribbon_data):
    output_dir = os.path.join(PROJECT_ROOT, "output")
    output_report = os.path.join(output_dir, "_test_ribbon_chart.html")

    with open(csv_ribbon_data, "r", encoding="utf-8") as f:
        csv_content = f.read()

    config = {
        "title": "QA Ribbon Chart",
        "widgets": [
            {
                "type": "ribbon_chart",
                "title": "Ribbon Chart",
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
    html_content = generator.generate(config, [csv_content], js_bundle_mode="full")

    os.makedirs(output_dir, exist_ok=True)
    with open(output_report, "w", encoding="utf-8") as f:
        f.write(html_content)

    return "file:///{path}".format(path=output_report.replace(os.sep, "/"))


def _chart(page: Page, ribbon_chart_report):
    page.goto(ribbon_chart_report)
    chart = page.locator(".chart-box", has=page.locator("h2", has_text="Ribbon Chart"))
    chart.locator(".ctrl-yoy input").uncheck()
    return chart


def test_ribbon_chart_renders_alluvial_structure(page: Page, ribbon_chart_report):
    """Ribbon chart: column nodes, flows between steps, value labels; period value hidden."""
    chart = _chart(page, ribbon_chart_report)

    expect(chart.locator(".ctrl-period-value")).to_be_hidden()
    expect(chart.locator(".ctrl-period-type")).to_be_visible()

    svg = chart.locator("svg.ribbon-chart-svg").first
    expect(svg).to_be_visible()
    expect(svg).to_have_attribute("data-period-type", "mois")
    expect(svg).to_have_attribute("data-category-count", "4")

    expect(chart.locator("path.ribbon-chart-flow").first).to_be_visible()
    assert chart.locator("path.ribbon-chart-flow").count() >= 4

    expect(chart.locator("rect.ribbon-chart-node").first).to_be_visible()
    assert chart.locator("rect.ribbon-chart-node").count() >= 12

    expect(chart.locator("text.ribbon-chart-node-label").first).to_be_visible()
    assert chart.locator("text.ribbon-chart-node-label").count() >= 12

    assert chart.locator("line.ribbon-chart-guide").count() == 12

    labels = chart.locator("text.ribbon-chart-category-label")
    expect(labels.first).to_be_visible()
    assert labels.count() == 4
    assert set(labels.all_text_contents()) == set(CATEGORIES)

    swatches = chart.locator("rect.ribbon-chart-category-swatch")
    assert swatches.count() == 4


def test_ribbon_chart_period_type_switches_x_axis(page: Page, ribbon_chart_report):
    """Vue trimestre uses quarter ticks on the X axis."""
    chart = _chart(page, ribbon_chart_report)
    chart.locator(".ctrl-period-type select").select_option("trimestre")

    svg = chart.locator("svg.ribbon-chart-svg").first
    expect(svg).to_have_attribute("data-period-type", "trimestre")
    assert chart.locator("line.ribbon-chart-guide").count() == 4

    axis_text = chart.locator("svg.ribbon-chart-svg").first.locator("text").all_text_contents()
    joined = " ".join(axis_text)
    assert "T1" in joined
    assert "T4" in joined


def test_ribbon_chart_year_select_changes_data(page: Page, ribbon_chart_report):
    """Year selector filters the displayed calendar year."""
    chart = _chart(page, ribbon_chart_report)
    chart.locator('select[data-testid="widget-year-select"]').select_option("2024")
    expect(chart.locator("h4", has_text="Année 2024")).to_be_visible()


def test_build_ribbon_stacked_series_trimestre_aggregation(page: Page, ribbon_chart_report):
    """Pure buildRibbonStackedSeries sums months into quarters."""
    page.goto(ribbon_chart_report)

    result = page.evaluate(
        """() => {
            const rows = [
                { month: 1, Alpha: 10, category: 'Alpha' },
                { month: 2, Alpha: 20, category: 'Alpha' },
                { month: 4, Beta: 5, category: 'Beta' },
            ].map(r => ({ month: r.month, amount: r.category === 'Alpha' ? (r.month === 1 ? 10 : 20) : 5, category: r.category }));
            const mapping = { value: 'amount', category: 'category' };
            const built = buildRibbonStackedSeries(rows, mapping, 'trimestre');
            const seriesA = built.seriesByCategory.find(s => s[0].category === 'Alpha');
            const t1 = seriesA.find(p => p.x === 1).value;
            return { t1, xLen: built.xValues.length, catCount: built.categories.length };
        }"""
    )
    assert result["t1"] == 30
    assert result["xLen"] == 4


def test_build_ribbon_column_stacks_four_categories(page: Page, ribbon_chart_report):
    """Column stacks expose one segment per category with positive values."""
    page.goto(ribbon_chart_report)

    result = page.evaluate(
        """() => {
            const rows = [];
            const cats = ['Alpha', 'Beta', 'Gamma', 'Delta'];
            for (let m = 1; m <= 12; m++) {
                cats.forEach((c, i) => rows.push({ month: m, amount: 10 + i + m, category: c }));
            }
            const mapping = { value: 'amount', category: 'category' };
            const built = buildRibbonStackedSeries(rows, mapping, 'mois');
            const cols = buildRibbonColumnStacks(built.xValues, built.categories, built.seriesByCategory);
            const jan = cols.find(c => c.x === 1);
            const segCount = Object.keys(jan.segments).length;
            return { colCount: cols.length, segCount, categories: built.categories.length };
        }"""
    )
    assert result["colCount"] == 12
    assert result["categories"] == 4
    assert result["segCount"] == 4


def test_ribbon_flow_paths_connect_adjacent_columns(page: Page, ribbon_chart_report):
    """At least one flow ribbon uses a closed path between two X positions."""
    chart = _chart(page, ribbon_chart_report)
    d_attr = chart.locator("path.ribbon-chart-flow").first.get_attribute("d")
    assert d_attr
    assert "M" in d_attr
    assert "C" in d_attr
    assert "Z" in d_attr


def test_ribbon_flow_no_vertical_overshoot(page: Page, ribbon_chart_report):
    """Flow ribbons stay within the vertical span of their source and target segments."""
    chart = _chart(page, ribbon_chart_report)
    overshoot = chart.locator("svg.ribbon-chart-svg").first.evaluate(
        """(svg) => {
            function nodeBounds(month, category) {
                const r = svg.querySelector(
                    `rect.ribbon-chart-node[data-x="${month}"][data-category="${category}"]`
                );
                if (!r) return null;
                const y = Number(r.getAttribute('y'));
                const h = Number(r.getAttribute('height'));
                return { top: y, bottom: y + h };
            }
            const tol = 1.5;
            let violations = 0;
            for (const path of svg.querySelectorAll('path.ribbon-chart-flow')) {
                const cat = path.getAttribute('data-category');
                const x0 = path.getAttribute('data-source-x');
                const x1 = path.getAttribute('data-target-x');
                const b0 = nodeBounds(x0, cat);
                const b1 = nodeBounds(x1, cat);
                if (!b0 || !b1) continue;
                const yMin = Math.min(b0.top, b1.top) - tol;
                const yMax = Math.max(b0.bottom, b1.bottom) + tol;
                const len = path.getTotalLength();
                for (let i = 0; i <= 32; i++) {
                    const py = path.getPointAtLength((len * i) / 32).y;
                    if (py < yMin || py > yMax) violations += 1;
                }
            }
            return violations;
        }"""
    )
    assert overshoot == 0


def test_ribbon_chart_ranking_swaps_between_periods(page: Page, ribbon_chart_report):
    """When values invert across months, the top stack segment changes (bump reorder)."""
    chart = _chart(page, ribbon_chart_report)

    dom_rank = chart.locator("svg.ribbon-chart-svg").first.evaluate(
        """(svg) => {
            function topCategory(month) {
                const nodes = [...svg.querySelectorAll(`rect.ribbon-chart-node[data-x="${month}"]`)];
                nodes.sort((a, b) => Number(a.getAttribute('y')) - Number(b.getAttribute('y')));
                return nodes[0] ? nodes[0].getAttribute('data-category') : null;
            }
            return { month1: topCategory(1), month4: topCategory(4) };
        }"""
    )
    assert dom_rank["month1"] == "Alpha"
    assert dom_rank["month4"] == "Delta"
    assert dom_rank["month1"] != dom_rank["month4"]

    pure_rank = page.evaluate(
        """() => {
            const rows = [
                { month: 1, amount: 40, category: 'Alpha' },
                { month: 1, amount: 30, category: 'Beta' },
                { month: 1, amount: 20, category: 'Gamma' },
                { month: 1, amount: 10, category: 'Delta' },
                { month: 2, amount: 10, category: 'Alpha' },
                { month: 2, amount: 20, category: 'Beta' },
                { month: 2, amount: 30, category: 'Gamma' },
                { month: 2, amount: 50, category: 'Delta' },
            ];
            const mapping = { value: 'amount', category: 'category' };
            const built = buildRibbonStackedSeries(rows, mapping, 'mois');
            const cols = buildRibbonColumnStacks([1, 2], built.categories, built.seriesByCategory);
            const top1 = ribbonColumnRankFromTop(cols.find((c) => c.x === 1))[0];
            const top2 = ribbonColumnRankFromTop(cols.find((c) => c.x === 2))[0];
            return { top1, top2 };
        }"""
    )
    assert pure_rank["top1"] == "Alpha"
    assert pure_rank["top2"] == "Delta"
