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

# --- 2. Data Setup ---

@pytest.fixture(scope="module")
def csv_data_file(tmp_path_factory):
    """
    Jeu de données hiérarchique complet sur 5 niveaux.
    """
    csv_content = """mois_annee,l1,l2,l3,l4,l5,amount
# --- 2024 (N-1) : Pour vérifier la stabilité des couleurs ---
2024-01,DeepGroup,Lvl2,Lvl3,Lvl4,Lvl5_Old,100

# --- 2025 (N) : Branche Profonde Multipliée ---
2025-01,DeepGroup,Lvl2,Lvl3,Lvl4,Lvl5_A,25
2025-01,DeepGroup,Lvl2,Lvl3,Lvl4,Lvl5_B,25
2025-01,DeepGroup,Lvl2,Lvl3,Lvl4,Lvl5_C,25
2025-01,DeepGroup,Lvl2,Lvl3,Lvl4,Lvl5_D,25

# --- 2025 (N) : Branche Taille (Big vs Small) ---
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
    """Récupère le graphique spécifique (2024 ou 2025) d'un widget"""
    chart_box = page.locator(".chart-box", has=page.locator("h2", has_text=widget_title))
    return chart_box.locator(".sub-chart", has=page.locator("h4", has_text=str(year)))

def get_l1_slice(chart, group_name):
    """ 
    Récupère un Path (arc) par son nom de groupe (Tooltip).
    Utilise XPath 'local-name()' pour traverser le namespace SVG.
    Exclut les enfants (qui contiennent ' > ').
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
    TC01: Vérifie la visibilité progressive (Drill-down).
    """
    page.goto(generated_report)
    chart = get_sub_chart(page, "Sunburst LINEAR", 2025)
    
    # 1. DeepGroup (L1) visible
    l1 = get_l1_slice(chart, "DeepGroup")
    expect(l1).to_be_visible()
    
    # 2. Lvl2 (L2) visible (On utilise le locator simple pour l'enfant)
    l2 = chart.locator("path").filter(has=page.locator("title", has_text="DeepGroup > Lvl2")).first
    expect(l2).to_be_visible()
    
    # 3. Lvl3 (L3) invisible au départ
    l3 = chart.locator("path").filter(has=page.locator("title", has_text="Lvl2 > Lvl3")).first
    if l3.count() > 0:
        opacity = l3.evaluate("el => getComputedStyle(el).fillOpacity")
        assert float(opacity) < 0.1, "L3 devrait être invisible avant zoom"

    # 4. Zoom sur Lvl2
    l2.click(force=True)
    page.wait_for_timeout(1000) # Attente animation
    
    # 5. Lvl3 devient visible
    expect(l3).to_have_css("fill-opacity", re.compile(r"0\.[6-9]|1"))


def test_TC02_sunburst_breadcrumbs_5_levels(page: Page, generated_report):
    """
    TC02: Vérifie que le fil d'ariane gère bien la navigation.
    """
    page.goto(generated_report)
    
    linear_box = page.locator(".chart-box", has=page.locator("h2", has_text="Sunburst LINEAR"))
    crumbs = linear_box.locator(".breadcrumbs")
    
    # 1. Clic sur "DeepGroup" (via texte pour éviter problème géométrique)
    linear_box.locator("text", has_text="DeepGroup").first.click(force=True)
    page.wait_for_timeout(800)
    
    # 2. Clic sur "Lvl2"
    linear_box.locator("text", has_text="Lvl2").first.click(force=True)
    page.wait_for_timeout(800)

    # --- VÉRIFICATIONS ---
    expect(crumbs).to_contain_text("DeepGroup")
    expect(crumbs).to_contain_text("Lvl2")
    
    # --- RETOUR ARRIÈRE ---
    crumbs.locator(".crumb", has_text="Total").click()
    page.wait_for_timeout(800)
    
    expect(crumbs).not_to_contain_text("Lvl2")


def test_TC03_sunburst_arc_sizes_linear_consistency(page: Page, generated_report):
    """
    TC03: Vérifie que la taille graphique correspond aux données (Linéaire).
    SizeGroup (995) doit être beaucoup plus grand que SmallItem (5).
    """
    page.goto(generated_report)
    chart = get_sub_chart(page, "Sunburst LINEAR", 2025)
    
    # Récupération des arcs enfants de SizeGroup
    big_slice = chart.locator("path").filter(has=page.locator("title", has_text="BigItem")).first
    small_slice = chart.locator("path").filter(has=page.locator("title", has_text="SmallItem")).first
    
    expect(big_slice).to_be_visible()
    expect(small_slice).to_be_visible()
    
    area_big = get_arc_area(big_slice)
    area_small = get_arc_area(small_slice)
    
    print(f"\n[LINEAR] Big: {area_big:.2f}, Small: {area_small:.2f}")

    assert area_big > (area_small * 50), "Mode Linéaire incorrect: ratio de taille insuffisant."


def test_TC06_sunburst_color_consistency(page: Page, generated_report):
    """
    TC06: Vérifie la stabilité des couleurs entre 2024 et 2025 (YoY).
    'DeepGroup' doit avoir la même couleur, peu importe l'ordre ou les nouvelles données.
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
        f"[BUG COULEUR] '{item_name}' a changé de couleur ! {col_24} != {col_25}"