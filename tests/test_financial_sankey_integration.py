import os
import re
import sys
import pytest
from playwright.sync_api import Page, expect

# --- 1. Imports ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from dashboard_engine.generator import DashboardGenerator
except ImportError:
    class DashboardGenerator:
        pass

# --- 2. Data Setup ---

@pytest.fixture(scope="module")
def csv_data_file(tmp_path_factory):
    """
    Jeu de données financier.
    Structure : Source -> Target (Type)
    Exemple: 
    - Sales -> Revenue (Input)
    - Revenue -> Profit (Profit - Vert)
    - Revenue -> Tax (Cost - Rouge)
    """
    csv_content = """mois_annee,source,target,amount,type
2025-01,Sales,Revenue,5000,input
2025-01,Revenue,Operating Profit,3000,profit
2025-01,Revenue,Cost of Goods,1500,cost
2025-01,Revenue,Tax,500,cost
2024-01,Sales,Revenue,4000,input
"""
    fn = tmp_path_factory.mktemp("data") / "financial_dataset.csv"
    fn.write_text(csv_content, encoding="utf-8")
    return str(fn)

@pytest.fixture(scope="module")
def generated_report(csv_data_file):
    output_dir = os.path.join(PROJECT_ROOT, "output")
    output_report = os.path.join(output_dir, "_test_financial_sankey.html")

    with open(csv_data_file, "r", encoding="utf-8") as f:
        csv_content = f.read()

    config = {
        "title": "QA Financial Sankey",
        "widgets": [
            {
                "type": "financial_sankey",
                "title": "P&L Flow",
                "datasetIndex": 0,
                "mapping": {
                    "date": "mois_annee",
                    "source": "source",
                    "target": "target",
                    "value": "amount",
                    "type": "type"
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


# --- 3. Tests ---

def test_financial_structure_and_hidden_controls(page: Page, generated_report):
    """
    TC01: Validates that Financial Sankey hides detailed period controls
    and displays yearly aggregation.
    """
    page.goto(generated_report)
    
    # 1. Check Title
    expect(page.locator(".chart-title")).to_have_text("P&L Flow")
    
    # 2. Check Hidden Controls (Like Evolution Widget)
    # The classes .ctrl-period-type and .ctrl-period-value should be hidden
    expect(page.locator(".ctrl-period-type")).to_be_hidden()
    expect(page.locator(".ctrl-period-value")).to_be_hidden()
    
    # 3. Check Chart Headers
    # Should display "Année 2025" and "Année 2024" (YoY is default)
    charts = page.locator(".sub-chart")
    expect(charts).to_have_count(2)
    expect(charts.last.locator("h4")).to_have_text("Année 2025")


def test_financial_semantic_coloring(page: Page, generated_report):
    """
    TC02: CRITICAL - Validates that nodes are colored according to their 'type'.
    - Profit nodes -> Green (#2e7d32)
    - Cost nodes -> Red (#c62828)
    - Input nodes -> Grey/Blue (#546e7a)
    """
    page.goto(generated_report)
    
    chart_n = page.locator(".sub-chart").last # 2025
    
    # 1. Check 'Operating Profit' (Type: profit -> Green)
    # We find the rect associated with the text 'Operating Profit'
    # Since rect and text are siblings in the group, we filter rects by their title content.
    profit_node = chart_n.locator("rect").filter(has_text="Operating Profit").first
    
    # Verify Fill Color
    expect(profit_node).to_have_attribute("fill", "#2e7d32")
    
    # 2. Check 'Tax' (Type: cost -> Red)
    tax_node = chart_n.locator("rect").filter(has_text="Tax").first
    expect(tax_node).to_have_attribute("fill", "#c62828")
    
    # 3. Check 'Sales' (Root/Input -> default/input color)
    sales_node = chart_n.locator("rect").filter(has_text="Sales").first
    # According to logic: if !targetLinks (Root) -> PALETTE['input'].node -> #546e7a
    expect(sales_node).to_have_attribute("fill", "#546e7a")


def test_financial_aggregation_and_labels(page: Page, generated_report):
    """
    TC03: Validates Data Aggregation and Label Formatting.
    Data 2025: Sales -> Revenue = 5000.
    Label Expected: "Revenue 5 000"
    """
    page.goto(generated_report)
    
    chart_n = page.locator(".sub-chart").last
    
    # We look for the TEXT element for Revenue
    # The text element contains the name directly, and a tspan with the value
    label = chart_n.locator("text", has_text="Revenue")
    
    expect(label).to_be_visible()
    
    # Get text content (includes the tspan value)
    text_content = label.text_content()
    
    # Check Name
    assert "Revenue" in text_content
    
    # Check Value (5000 formatted)
    assert re.search(r"5[\s\u202f\u00a0]*000", text_content), \
        f"Value 5000 not found in label: {text_content}"

def test_financial_links_rendering(page: Page, generated_report):
    """
    TC04: Verify links are drawn and colored correctly (inheriting target type).
    Link 'Revenue -> Tax' should be Red (#ef9a9a defined in PALETTE for cost link).
    """
    page.goto(generated_report)
    chart_n = page.locator(".sub-chart").last
    
    # D3 Sankey links are paths. We find the one connecting Revenue to Tax.
    # We use the title tooltip which contains "Revenue -> Tax"
    link_tax = chart_n.locator("path").filter(has_text="Revenue → Tax").first
    
    expect(link_tax).to_be_visible()
    
    # Check Link Color (Cost Link)
    # PALETTE['cost'].link is #ef9a9a
    expect(link_tax).to_have_attribute("stroke", "#ef9a9a")