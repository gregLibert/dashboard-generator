import os
import sys
import pytest
from playwright.sync_api import Page, expect

# --- Imports ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dashboard_engine.generator import DashboardGenerator

# --- Sankey dataset ---

@pytest.fixture(scope="module")
def sankey_data_file(tmp_path_factory):
    # Three levels: scheme -> acquirer -> region; 2024 (N-1) and 2025 (N) for YoY / colors.
    
    csv_content = """mois_annee,scheme,acquirer,region,amount
# --- Year 2024 (N-1) ---
2024-01,Visa,Worldline,France,1000
2024-01,Visa,Nets,Europe,500
2024-01,CB,Worldline,France,2000
2024-01,Mastercard,Adyen,Monde,1500

# --- Year 2025 (N) ---
2025-01,Visa,Worldline,France,1200
2025-01,Visa,Nets,Europe,600
2025-01,CB,Worldline,France,2000
2025-01,Mastercard,Adyen,Monde,1600
2025-01,Mastercard,Worldline,France,400
"""
    fn = tmp_path_factory.mktemp("data") / "sankey_complex.csv"
    fn.write_text(csv_content, encoding="utf-8")
    return str(fn)

@pytest.fixture(scope="module")
def sankey_report(sankey_data_file):
    output_dir = os.path.join(PROJECT_ROOT, "output")
    output_report = os.path.join(output_dir, "_test_sankey.html")

    with open(sankey_data_file, "r", encoding="utf-8") as f:
        csv_content = f.read()

    config = {
        "title": "QA Sankey Complex 3-Levels",
        "widgets": [
            {
                "type": "sankey",
                "title": "Flux Monétique 3 Niveaux",
                "datasetIndex": 0,
                "options": { "yoy": True },
                "mapping": { 
                    "date": "mois_annee", 
                    "value": "amount",
                    # Three hierarchy columns
                    "path": ["scheme", "acquirer", "region"]
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


# --- Sankey tests ---

def test_TC01_sankey_render_structural_elements(page: Page, sankey_report):
    """
    TC01: SVG has nodes and links for a three-level Sankey (2025 data).
    """
    page.goto(sankey_report)
    
    # 2025 sub-chart
    chart_2025 = page.locator(".sub-chart", has=page.locator("h4", has_text="2025"))
    svg = chart_2025.locator("svg")
    expect(svg).to_be_visible()

    # 1. Nodes (rects): 3+3+3 = 9
    nodes = svg.locator("rect")
    expect(nodes).to_have_count(9)

    # 2. Links: at least 5 paths for this layout
    links = svg.locator("path")
    count = links.count()
    assert count >= 5, f"Expected >=5 links for 3-level sankey, got {count}"

def test_TC02_sankey_filtering_interaction(page: Page, sankey_report):
    """
    TC02: Click-filter on level-1 node restricts links through level 3.
    """
    page.goto(sankey_report)
    chart_2025 = page.locator(".sub-chart", has=page.locator("h4", has_text="2025"))
    
    # Click Visa
    visa_node = chart_2025.locator("rect").filter(has_text="Visa").first
    visa_node.click()

    # Title shows active filter
    expect(chart_2025.locator("h4")).to_contain_text("Filtre: Visa")

    # Remaining links after filter
    links = chart_2025.locator("svg path")
    expect(links).to_have_count(4)

    # Reset
    page.locator("h4 span", has_text="✖").first.click()
    
    # Full graph restored: 8 links for 2025
    expect(links).to_have_count(8)

def test_TC03_sankey_overlay_percentage_logic(page: Page, sankey_report):
    """
    TC03: Tooltip share percentages for 2025 level-1 nodes (~31.0% Visa, ~34.5% CB).
    """
    page.goto(sankey_report)
    chart_2025 = page.locator(".sub-chart", has=page.locator("h4", has_text="2025"))

    # 1. Visa
    visa_tooltip = chart_2025.locator("rect").filter(has_text="Visa").locator("title").first
    txt_visa = visa_tooltip.text_content()
    assert "31.0%" in txt_visa, f"Visa share wrong: {txt_visa}"

    # 2. CB
    cb_tooltip = chart_2025.locator("rect").filter(has_text="CB").locator("title").first
    txt_cb = cb_tooltip.text_content()
    assert "34.5%" in txt_cb, f"CB share wrong: {txt_cb}"

    # 3. Level 2: Worldline ~62.1%
    
    wl_tooltip = chart_2025.locator("rect").filter(has_text="Worldline").locator("title").first
    txt_wl = wl_tooltip.text_content()
    assert "62.1%" in txt_wl, f"Worldline share wrong: {txt_wl}"
    

def test_TC04_sankey_color_consistency(page: Page, sankey_report):
    """
    TC04: Same scheme keeps the same fill across 2024 and 2025 (Mastercard).
    """
    page.goto(sankey_report)

    # Graph 2024
    chart_2024 = page.locator(".sub-chart", has=page.locator("h4", has_text="2024"))
    color_mc_24 = chart_2024.locator("rect").filter(has_text="Mastercard").first.get_attribute("fill")

    # Graph 2025
    chart_2025 = page.locator(".sub-chart", has=page.locator("h4", has_text="2025"))
    color_mc_25 = chart_2025.locator("rect").filter(has_text="Mastercard").first.get_attribute("fill")

    assert color_mc_24 == color_mc_25, f"Mastercard color drift: {color_mc_24} vs {color_mc_25}"

    color_visa_25 = chart_2025.locator("rect").filter(has_text="Visa").first.get_attribute("fill")
    assert color_mc_25 != color_visa_25, "Mastercard and Visa must differ"

def test_TC05_sankey_empty_year_message(page: Page, sankey_report):
    """
    TC05: Anchor 2024: N panel shows data; N-1 (2023) shows empty-state message.
    """
    page.goto(sankey_report)

    # 1. Select anchor year 2024
    year_select = page.locator('select[data-testid="widget-year-select"]').first
    year_select.select_option("2024")

    # 2. N (2024) has SVG
    chart_2024 = page.locator(".sub-chart", has=page.locator("h4", has_text="2024"))
    expect(chart_2024.locator("svg")).to_be_visible()

    # 3. N-1 (2023): no SVG, empty hint
    chart_2023 = page.locator(".sub-chart", has=page.locator("h4", has_text="2023"))
    
    # No SVG
    expect(chart_2023.locator("svg")).not_to_be_visible()
    
    # Empty-state copy from JS
    expect(chart_2023).to_contain_text("Aucune donnée")