import os
import re
import sys
import pytest
from playwright.sync_api import Page, expect

# --- 1. Project imports ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dashboard_engine.generator import DashboardGenerator

# --- 2. Test data ---

@pytest.fixture(scope="module")
def csv_data_file(tmp_path_factory):
    """
    Dataset for aggregation (sum) checks.
    January 2025 has three rows so the chart must show the correct total.
    """
    csv_content = """mois_annee,scheme,tsp,amount,option,tech
2024-01,Visa,Worldline,1000,Token,Credit
2024-01,CB,Worldline,2000,Standard,Debit
2024-01,Mastercard,Nets,500,Token,Credit
2024-02,Visa,Worldline,1100,Standard,Credit
2024-02,CB,Worldline,2100,Token,Debit
2024-02,Mastercard,Nets,550,Standard,Credit
2024-03,Visa,Worldline,1200,Token,Debit
2024-03,CB,Worldline,1900,Standard,Debit
2024-03,Mastercard,Nets,600,Token,Credit
2024-06,Visa,Worldline,1500,Token,Credit
2024-06,CB,Worldline,2500,Standard,Debit
2024-12,Visa,Worldline,1800,Standard,Credit
2024-12,CB,Worldline,3000,Token,Debit
2025-01,Visa,Worldline,1500,Token,Credit
2025-01,CB,Worldline,2300,Standard,Debit
2025-01,Mastercard,Nets,800,Token,Credit
2025-02,Visa,Worldline,1650,Standard,Credit
2025-02,CB,Worldline,2100,Token,Debit
2025-02,Mastercard,Nets,900,Standard,Credit
2025-03,Visa,Worldline,1800,Token,Debit
2025-03,CB,Worldline,2500,Standard,Debit
2025-03,Mastercard,Nets,950,Token,Credit
2025-06,Visa,Worldline,2000,Token,Credit
2025-06,CB,Worldline,2800,Standard,Debit
2025-12,Visa,Worldline,2500,Standard,Credit
2025-12,CB,Worldline,3500,Token,Debit
"""
    fn = tmp_path_factory.mktemp("data") / "evolution_dataset.csv"
    fn.write_text(csv_content, encoding="utf-8")
    return str(fn)

@pytest.fixture(scope="module")
def generated_report(csv_data_file):
    output_dir = os.path.join(PROJECT_ROOT, "output")
    output_report = os.path.join(output_dir, "_test_evolution_integration.html")

    with open(csv_data_file, "r", encoding="utf-8") as f:
        csv_content = f.read()

    config = {
        "title": "QA Evolution Integration",
        "widgets": [
            {
                "type": "evolution",
                "title": "Évolution Mensuelle (N vs N-1)",
                "description": "Validation de l'aggrégation et du YoY.",
                "datasetIndex": 0,
                "mapping": {
                    "date": "mois_annee",
                    "value": "amount"
                }
            }
        ]
    }

    generator = DashboardGenerator()
    html_content = generator.generate(config, [csv_content])

    os.makedirs(output_dir, exist_ok=True)
    with open(output_report, "w", encoding="utf-8") as f:
        f.write(html_content)

    return f"file:///{output_report.replace(os.sep, '/')}"


# --- 3. Functional tests ---

def test_evolution_structure_and_hidden_controls(page: Page, generated_report):
    """
    Checks layout and that period controls unused by this widget are hidden via CSS.
    """
    page.goto(generated_report)
    
    # 1. Title and description
    expect(page.locator(".chart-title")).to_have_text("Évolution Mensuelle (N vs N-1)")
    page.click(".info-icon")
    expect(page.locator(".widget-description")).to_contain_text("Validation de l'aggrégation")

    # 2. Hidden controls (EvolutionWidget-specific)
    # .ctrl-period-type and .ctrl-period-value must be hidden
    ctrl_type = page.locator(".ctrl-period-type")
    ctrl_value = page.locator(".ctrl-period-value")
    
    # to_be_hidden() covers display:none, visibility:hidden, etc.
    expect(ctrl_type).to_be_hidden()
    expect(ctrl_value).to_be_hidden()
    
    # 3. Year selector remains visible
    expect(page.locator("text=Année:")).to_be_visible()


def test_evolution_graph_yoy_toggling(page: Page, generated_report):
    """
    Checks N vs N-1 lines and the YoY toggle.
    """
    page.goto(generated_report)
    
    # Select 2025 so N=2025 and N-1=2024
    page.locator('select[data-testid="widget-year-select"]').first.select_option("2025")
    
    container = page.locator(".sub-chart svg")
    
    # 1. N series: solid line (JS stroke-width=3, no dasharray)
    line_n = container.locator("path[stroke-width='3']")
    expect(line_n).to_be_visible()
    
    # 2. N-1 series: dashed (JS stroke-dasharray='5,5')
    line_n1 = container.locator("path[stroke-dasharray='5,5']")
    expect(line_n1).to_be_visible()
    
    # 3. Disable YoY
    page.locator(".ctrl-yoy input").uncheck()
    
    # 4. N-1 line should disappear
    expect(line_n1).not_to_be_visible()
    # N line must remain
    expect(line_n).to_be_visible()


def test_data_aggregation_accuracy(page: Page, generated_report):
    """
    Ensures JS sums monthly rows correctly.
    January 2025 (N): Visa 1500 + CB 2300 + Mastercard 800 => 4600.
    """
    page.goto(generated_report)
    
    # Setup: year 2025
    page.locator('select[data-testid="widget-year-select"]').first.select_option("2025")
    
    # Target N-series dots (JS: .dot-N circles)
    
    dots = page.locator(".sub-chart svg .dot-N")
    
    # January is index 0 (data sorted by month)
    january_dot = dots.nth(0)
    
    # Tooltip from internal SVG <title>; text_content() reads it
    tooltip_text = january_dot.text_content()
    
    print(f"January tooltip: '{tooltip_text}'")
    
    # Month label present
    assert "Janvier" in tooltip_text
    
    # Sum 4600 with optional spacing / nbsp
    match_sum = re.search(r"4[\s\u202f\u00a0]*600", tooltip_text)
    
    assert match_sum, f"Expected total ~4600 in tooltip, got: {tooltip_text}"

def test_evolution_legend_labels(page: Page, generated_report):
    """
    Checks in-chart legend text for N and N-1 series.
    """
    page.goto(generated_report)
    
    # Year 2025 with YoY on
    page.locator('select[data-testid="widget-year-select"]').first.select_option("2025")
    page.locator(".ctrl-yoy input").check()
    
    # SVG root
    svg = page.locator(".sub-chart svg")
    
    # Legend N (SVG <text>)
    legend_n = svg.locator("text", has_text="Année 2025")
    expect(legend_n).to_be_visible()
    
    # Legend N-1
    legend_n1 = svg.locator("text", has_text="Année 2024")
    expect(legend_n1).to_be_visible()


def test_export_csv_functionality(page: Page, generated_report):
    """
    Export button triggers download with a sensible filename.
    """
    page.goto(generated_report)

    # Global header button
    export_btn = page.locator("#btn-export")
    expect(export_btn).to_be_visible()

    # Capture download
    with page.expect_download() as download_info:
        export_btn.click()

    download = download_info.value
    
    # Filename checks
    fname = download.suggested_filename
    assert fname.endswith(".csv")
    assert "qa_evolution_integration" in fname.lower() or "dataset" in fname.lower()
    
    # Quick content smoke check
    file_path = download.path()
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        # Expected CSV headers
        assert "mois_annee" in content
        assert "amount" in content


def test_evolution_n_minus_1_interactivity(page: Page, generated_report):
    """
    N-1 series exposes interactive hit targets (dots).
    """
    page.goto(generated_report)
    
    # Setup: 2025 + YoY
    page.locator('select[data-testid="widget-year-select"]').first.select_option("2025")
    page.locator(".ctrl-yoy input").check()

    container = page.locator(".sub-chart svg")
    
    # N-1 dots: title text includes prior year (2024 for anchor 2025)
    dot_n1 = container.locator("circle").filter(has_text="Année 2024").first
    
    expect(dot_n1).to_be_visible()
    
    # Tooltip N-1
    expect(dot_n1).to_contain_text("Année 2024")  # internal <title>
    expect(dot_n1).to_contain_text("Val:")


def test_evolution_percentage_labels(page: Page, generated_report, csv_data_file):
    """
    YoY percentage labels: Jan 2024 total 3500 vs Jan 2025 4600 => ~+31%.
    """
    page.goto(generated_report)
    page.locator('select[data-testid="widget-year-select"]').first.select_option("2025")
    
    # Label above January point (+31%)
    label_pct = page.locator(".sub-chart svg text", has_text="+31%")
    
    expect(label_pct).to_be_visible()
    
    # Positive delta: green (#2e7d32 in JS)
    expect(label_pct).to_have_attribute("fill", "#2e7d32")


def test_legend_background_fix(page: Page, generated_report):
    """
    Legend group uses an opaque background so text does not clash with the line.
    """
    page.goto(generated_report)

    # JS adds a near-opaque white rect behind legend text
    legend_bg = page.locator(".sub-chart svg rect[fill='rgba(255, 255, 255, 0.9)']")
    
    expect(legend_bg).to_be_visible()