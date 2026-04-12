import os
import sys
import pytest
from playwright.sync_api import Page, expect

# --- Test module setup ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dashboard_engine.generator import DashboardGenerator

@pytest.fixture(scope="module")
def csv_treemap_data(tmp_path_factory):
    csv_content = """date_col,Level1,Level2,Level3,Level4,amount
# --- 2024 Data (N-1) ---
2024-01,BranchA,SubA,DeepA,LeafA,100
2024-01,BranchB,SubB,DeepB,LeafB,200
2024-01,MultiL1,Child2_A,Child3_A,Child4_A,50

# --- 2025 Data (N) ---
# 1. Standard Path
2025-01,BranchA,SubA,DeepA,LeafA,100

# 2. Color consistency case
2025-01,BranchA,SharedItem,DeepX,LeafX,100
2025-01,BranchB,SharedItem,DeepY,LeafY,100

# 3. Scale case (100 vs 1000)
2025-01,ScaleTest,GiantGroup,GiantSub,GiantLeaf,1000
2025-01,ScaleTest,SmallGroup,SmallSub,SmallLeaf,100

# 4. Stress Test
2025-01,DenseL1,Item2_A,Item3_X,Item4_X,20
2025-01,DenseL1,Item2_B,Item3_X,Item4_X,20
2025-01,DenseL1,Item2_C,Item3_X,Item4_X,20
2025-01,DenseL1,Item2_D,Item3_X,Item4_X,20
2025-01,DenseL1,Item2_E,Item3_X,Item4_X,20
"""
    fn = tmp_path_factory.mktemp("data") / "treemap_data.csv"
    fn.write_text(csv_content, encoding="utf-8")
    return str(fn)

@pytest.fixture(scope="module")
def treemap_report(csv_treemap_data):
    output_dir = os.path.join(PROJECT_ROOT, "output")
    report_path = os.path.join(output_dir, "_test_treemap_final.html")

    with open(csv_treemap_data, "r", encoding="utf-8") as f:
        csv_raw = f.read()

    config = {
        "title": "QA Nested Treemap Final",
        "widgets": [
            {
                "type": "nested_treemap",
                "title": "Treemap Sync Test",
                "datasetIndex": 0,
                "mapping": {
                    "date": "date_col",
                    "value": "amount",
                    "hierarchy": ["Level1", "Level2", "Level3", "Level4"]
                },
                "options": { "yoy": True } 
            }
        ]
    }

    generator = DashboardGenerator()
    html = generator.generate(config, [csv_raw], js_bundle_mode="full")
    
    os.makedirs(output_dir, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)
    return f"file:///{report_path.replace(os.sep, '/')}"

# --- Helpers ---

def get_chart_container(page, year):
    return page.locator(".sub-chart", has=page.locator(f"h4:text('{year}')")).locator(".treemap-container")

def get_rect_by_name(page, name, year=None):
    base = page
    if year:
        base = get_chart_container(page, year)

    xpath = f"xpath=.//*[local-name()='g'][.//*[local-name()='tspan' and text()='{name}']]/*[local-name()='rect']"
    
    return base.locator(xpath).first

def get_text_group_by_name(page, name, year=None):
    base = page
    if year:
        base = get_chart_container(page, year)
    
    # CORRECTION XPATH ICI AUSSI
    xpath = f"xpath=.//*[local-name()='g'][.//*[local-name()='tspan' and text()='{name}']]/*[local-name()='text']"
    return base.locator(xpath).first

def get_breadcrumbs(page):
    return page.locator(".breadcrumbs")

# --- Test Group 1: Layout & Overflow ---

def test_TC01_nested_treemap_layout_and_overflow(page: Page, treemap_report):
    page.goto(treemap_report)
    
    cont_24 = get_chart_container(page, 2024)
    cont_25 = get_chart_container(page, 2025)
    
    box_24 = cont_24.bounding_box()
    box_25 = cont_25.bounding_box()
    
    assert abs(box_24['width'] - box_25['width']) <= 1, "Largeurs N et N-1 incohérentes"
    assert abs(box_24['height'] - box_25['height']) <= 1, "Hauteurs N et N-1 incohérentes"

    overflow_25 = cont_25.evaluate("el => window.getComputedStyle(el).overflow")
    assert overflow_25 == "hidden"


# --- Test Group 2: Labels & Overlay ---

def test_TC02_nested_treemap_labels_and_overlay(page: Page, treemap_report):
    page.set_viewport_size({"width": 1600, "height": 1200})
    page.goto(treemap_report)
    
    # 1. Overlay
    leaf_a = get_rect_by_name(page, "LeafA", year=2025)
    leaf_a.wait_for(state="attached")
    
    xpath_title = f"xpath=.//*[local-name()='g'][.//*[local-name()='tspan' and text()='LeafA']]/*[local-name()='title']"
    tooltip = get_chart_container(page, 2025).locator(xpath_title).text_content()
    
    assert "BranchA > SubA > DeepA > LeafA" in tooltip
    assert "100" in tooltip
    
    # 2. Logique "Sacrifice de Titre" (Adaptive Layout)
    small_leaf_text = get_text_group_by_name(page, "SmallLeaf", year=2025)
    small_leaf_text.wait_for(state="attached")
    
    # Initially SmallLeaf visible; SmallSub label sacrificed for space
    op = small_leaf_text.evaluate("el => window.getComputedStyle(el).opacity")
    assert float(op) == 1, "SmallLeaf should be visible while SmallSub label is dropped"
    
    # Sacrifice: no SmallSub tspan
    small_sub_tspan = get_chart_container(page, 2025).locator("xpath=.//*[local-name()='tspan' and text()='SmallSub']")
    assert small_sub_tspan.count() == 0, "SmallSub title should be hidden when compact"
    
    # 3. Zoom in to free space
    get_rect_by_name(page, "ScaleTest", year=2025).dispatch_event("click")
    page.wait_for_timeout(500)
    get_rect_by_name(page, "SmallGroup", year=2025).dispatch_event("click")
    page.wait_for_timeout(800)
    
    # After zoom: SmallSub is no longer compact — label should reappear

    # Re-query after relayout
    small_sub_tspan_after = get_chart_container(page, 2025).locator("xpath=.//*[local-name()='tspan' and text()='SmallSub']")
    
    # Wait for label
    expect(small_sub_tspan_after).to_be_visible()
    assert small_sub_tspan_after.count() > 0, "Le titre SmallSub devrait réapparaître après zoom"

# --- Test Group 3: Interaction & Breadcrumbs ---

def test_TC03_nested_treemap_interaction_zoom_unzoom(page: Page, treemap_report):
    page.set_viewport_size({"width": 1600, "height": 1200})
    page.goto(treemap_report)
    crumbs = get_breadcrumbs(page)
    
    # 1. Zoom avec dispatchEvent (plus fiable pour SVG)
    rect = get_rect_by_name(page, "BranchB", year=2025)
    rect.wait_for(state="attached")
    
    # On utilise dispatch_event 'click' pour contourner les problèmes de géométrie SVG
    rect.dispatch_event("click")
    page.wait_for_timeout(800)
    
    expect(crumbs).to_contain_text("BranchB")
    
    # 2. Dézoom (Breadcrumb)
    crumbs.locator(".crumb", has_text="Total").click()
    page.wait_for_timeout(800)
    expect(crumbs).not_to_contain_text("BranchB")
    
    # 3. Re-Zoom
    rect.dispatch_event("click")
    page.wait_for_timeout(800)
    expect(crumbs).to_contain_text("BranchB")
    
    # 4. Dézoom (Titre Background)
    page.locator("h4", has_text="2025").first.click()
    page.wait_for_timeout(800)
    expect(crumbs).not_to_contain_text("BranchB")


# --- Test Group 4: Synchronization N / N-1 ---

def test_TC04_nested_treemap_synchronization(page: Page, treemap_report):
    page.set_viewport_size({"width": 1600, "height": 1200})
    page.goto(treemap_report)
    
    # --- Cas 1 : Valeur Commune (BranchA) ---
    # On clique sur BranchA en 2025
    get_rect_by_name(page, "BranchA", year=2025).click(force=True)
    page.wait_for_timeout(1000)
    
    # VÉRIFICATION 1 : Le titre "BranchA" doit avoir disparu de 2024
    # car c'est maintenant la racine du zoom.
    branch_a_text_24 = get_chart_container(page, 2024).locator("xpath=.//*[local-name()='tspan' and text()='BranchA']")
    expect(branch_a_text_24).to_have_count(0)

    # VÉRIFICATION 2 : Zoom effectif
    cont_24_width = get_chart_container(page, 2024).bounding_box()['width']
    
    # On cherche l'enfant LeafA dans 2024
    leaf_a_24 = get_rect_by_name(page, "LeafA", year=2024)
    leaf_a_24.wait_for(state="attached")
    rect_leaf_box = leaf_a_24.bounding_box()
    
    # Ratio ajusté à 0.9 pour être tolérant au padding/aspect ratio
    ratio = rect_leaf_box['width'] / cont_24_width
    assert ratio > 0.9, f"2024 aurait dû zoomer (LeafA est petit: {ratio})"
    
    # Reset
    page.locator("h4", has_text="2025").first.click()
    page.wait_for_timeout(800)
    
    # --- Cas 2 : Valeur Unique à N (ScaleTest) ---
    # ScaleTest n'existe pas en 2024
    get_rect_by_name(page, "ScaleTest", year=2025).dispatch_event("click")
    page.wait_for_timeout(1000)
    
    # VÉRIFICATION 1 : Le titre "ScaleTest" doit avoir disparu de 2025
    scale_test_text_25 = get_chart_container(page, 2025).locator("xpath=.//*[local-name()='tspan' and text()='ScaleTest']")
    expect(scale_test_text_25).to_have_count(0)

    # VÉRIFICATION 2 : Zoom effectif sur 2025
    giant_leaf = get_rect_by_name(page, "GiantLeaf", year=2025)
    
    # On compare la surface ou la largeur. Ici largeur avec ratio prudent.
    ratio_25 = giant_leaf.bounding_box()['width'] / get_chart_container(page, 2025).bounding_box()['width']
    assert ratio_25 > 0.87, f"2025 should zoom ScaleTest (ratio: {ratio_25})"
    
    # 2024 has no ScaleTest row -> empty state
    container_24 = get_chart_container(page, 2024)
    expect(container_24).to_contain_text("No data available")
    
    # No treemap rects for empty year
    expect(container_24.locator("rect")).to_have_count(0)
    
    # Breadcrumb OK
    expect(get_breadcrumbs(page)).to_contain_text("ScaleTest")