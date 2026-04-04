import os
import re
import sys
import math
import pytest
from playwright.sync_api import Page, expect

# --- 1. Project Imports ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dashboard_engine.generator import DashboardGenerator

# --- 2. Test data ---

@pytest.fixture(scope="module")
def csv_data_file(tmp_path_factory):
    """
    Five-level hierarchy; 2024 for color stability, 2025 for depth and size cases.
    """
    csv_content = """mois_annee,l1,l2,l3,l4,l5,amount
# --- 2024 (N-1): color stability ---
2024-01,DeepGroup,Lvl2,Lvl3,Lvl4,Lvl5_Old,100

# --- 2025 (N): deep branch split ---
2025-01,DeepGroup,Lvl2,Lvl3,Lvl4,Lvl5_A,25
2025-01,DeepGroup,Lvl2,Lvl3,Lvl4,Lvl5_B,25
2025-01,DeepGroup,Lvl2,Lvl3,Lvl4,Lvl5_C,25
2025-01,DeepGroup,Lvl2,Lvl3,Lvl4,Lvl5_D,25

# --- 2025 (N): size contrast (big vs small) ---
2025-01,SizeGroup,BigItem,Big_L3,Big_L4,Big_L5,995
2025-01,SizeGroup,SmallItem,Small_L3,Small_L4,Small_L5,5
"""
    fn = tmp_path_factory.mktemp("data") / "sunburst_5lvl.csv"
    fn.write_text(csv_content, encoding="utf-8")
    return str(fn)

@pytest.fixture(scope="module")
def generated_report(csv_data_file):
    output_dir = os.path.join(PROJECT_ROOT, "output")
    output_report = os.path.join(output_dir, "_test_sunburst_integration.html")

    with open(csv_data_file, "r", encoding="utf-8") as f:
        csv_content = f.read()

    config = {
        "title": "QA Sunburst Integration",
        "widgets": [
            {
                "type": "sunburst",
                "title": "Sunburst LINEAR",
                "datasetIndex": 0,
                "mapping": {
                    "date": "mois_annee",
                    "value": "amount",
                    "hierarchy": ["l1", "l2", "l3", "l4", "l5"]
                },
                "options": { "useLogScale": False, "yoy": True }
            }
        ]
    }

    generator = DashboardGenerator()
    html_content = generator.generate(config, [csv_content])

    os.makedirs(output_dir, exist_ok=True)
    with open(output_report, "w", encoding="utf-8") as f:
        f.write(html_content)

    return f"file:///{output_report.replace(os.sep, '/')}"


# --- 3. HELPER FUNCTIONS ---

def get_sub_chart(page, widget_title, year):
    """Return the sub-chart locator for a given widget title and year."""
    chart_box = page.locator(".chart-box", has=page.locator("h2", has_text=widget_title))
    return chart_box.locator(".sub-chart", has=page.locator("h4", has_text=str(year)))

def get_l1_slice(chart, group_name):
    """
    First path whose title tooltip matches group_name at L1 (excludes ' > ' child titles).
    Uses XPath local-name() for SVG namespaces.
    """
    xpath_selector = (
        f"xpath=.//*[local-name()='path']"
        f"[*[local-name()='title'][contains(text(), '{group_name}') and not(contains(text(), ' > '))]]"
    )
    return chart.locator(xpath_selector).first

def get_arc_area(locator):
    box = locator.bounding_box()
    if not box: return 0
    return box['width'] * box['height']


# --- 4. TESTS ---

def test_TC01_sunburst_depth_visibility(page: Page, generated_report):
    """
    TC01: Progressive visibility on drill-down.
    """
    page.goto(generated_report)
    chart = get_sub_chart(page, "Sunburst LINEAR", 2025)
    
    # 1. DeepGroup (L1) visible
    l1 = get_l1_slice(chart, "DeepGroup")
    expect(l1).to_be_visible()
    
    # 2. L2 child visible
    l2 = chart.locator("path").filter(has=page.locator("title", has_text="DeepGroup > Lvl2")).first
    expect(l2).to_be_visible()
    
    # 3. L3 hidden before zoom
    l3 = chart.locator("path").filter(has=page.locator("title", has_text="Lvl2 > Lvl3")).first
    if l3.count() > 0:
        opacity = l3.evaluate("el => getComputedStyle(el).fillOpacity")
        assert float(opacity) < 0.1, "L3 should be hidden before zoom"

    # 4. Zoom into L2
    l2.click(force=True)
    page.wait_for_timeout(1000)

    # 5. L3 becomes visible
    expect(l3).to_have_css("fill-opacity", re.compile(r"0\.[6-9]|1"))


def test_TC02_sunburst_breadcrumbs_5_levels(page: Page, generated_report):
    """
    TC02: Breadcrumb navigation across levels.
    """
    page.goto(generated_report)
    
    linear_box = page.locator(".chart-box", has=page.locator("h2", has_text="Sunburst LINEAR"))
    crumbs = linear_box.locator(".breadcrumbs")
    
    # 1. Click DeepGroup (text to avoid geometry issues)
    linear_box.locator("text", has_text="DeepGroup").first.click(force=True)
    page.wait_for_timeout(800)
    
    # 2. Click Lvl2
    linear_box.locator("text", has_text="Lvl2").first.click(force=True)
    page.wait_for_timeout(800)

    # --- Assertions ---
    expect(crumbs).to_contain_text("DeepGroup")
    expect(crumbs).to_contain_text("Lvl2")
    
    # --- Back to root ---
    crumbs.locator(".crumb", has_text="Total").click()
    page.wait_for_timeout(800)
    
    expect(crumbs).not_to_contain_text("Lvl2")


def test_TC03_sunburst_arc_sizes_linear_consistency(page: Page, generated_report):
    """
    TC03: Linear scale — BigItem area >> SmallItem area for SizeGroup branch.
    """
    page.goto(generated_report)
    chart = get_sub_chart(page, "Sunburst LINEAR", 2025)
    
    # Child arcs under SizeGroup
    big_slice = chart.locator("path").filter(has=page.locator("title", has_text="BigItem")).first
    small_slice = chart.locator("path").filter(has=page.locator("title", has_text="SmallItem")).first
    
    expect(big_slice).to_be_visible()
    expect(small_slice).to_be_visible()
    
    area_big = get_arc_area(big_slice)
    area_small = get_arc_area(small_slice)
    
    print(f"\n[LINEAR] Big: {area_big:.2f}, Small: {area_small:.2f}")

    assert area_big > (area_small * 50), "Linear mode: size ratio too small."


def test_TC06_sunburst_color_consistency(page: Page, generated_report):
    """
    TC06: YoY color stability — DeepGroup fill matches across 2024 and 2025.
    """
    page.goto(generated_report)
    
    chart_2024 = get_sub_chart(page, "Sunburst LINEAR", 2024)
    chart_2025 = get_sub_chart(page, "Sunburst LINEAR", 2025)
    
    item_name = "DeepGroup"
    
    slice_24 = get_l1_slice(chart_2024, item_name)
    slice_25 = get_l1_slice(chart_2025, item_name)
    
    slice_24.wait_for(state="attached")
    slice_25.wait_for(state="attached")
    
    col_24 = slice_24.get_attribute("fill")
    col_25 = slice_25.get_attribute("fill")
    
    print(f"\n[Checking {item_name}]: 2024={col_24} vs 2025={col_25}")
    
    assert col_24 == col_25, \
        f"Color drift for '{item_name}': {col_24} != {col_25}"