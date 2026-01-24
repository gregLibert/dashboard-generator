import os
import re
import sys
import pytest
from playwright.sync_api import Page, expect

# --- 1. Project Imports ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from dashboard_engine.generator import DashboardGenerator
except ImportError:
    # Mock for standalone execution safety
    class DashboardGenerator:
        pass

# --- 2. Data Setup ---

@pytest.fixture(scope="module")
def csv_data_file(tmp_path_factory):
    """
    Creates hierarchical data for 2024 and 2025.
    Hierarchy: Scheme -> TSP
    Values allow simple percentage checking (e.g., 50%).
    """
    csv_content = """mois_annee,scheme,tsp,amount,option,tech
2024-01,Visa,Worldline,500,Token,Credit
2024-01,Visa,Nets,500,Token,Credit
2024-01,CB,Worldline,1000,Standard,Debit
2025-01,Visa,Worldline,1000,Token,Credit
2025-01,Visa,Nets,1000,Token,Credit
2025-01,CB,Worldline,2000,Standard,Debit
"""
    fn = tmp_path_factory.mktemp("data") / "sunburst_dataset.csv"
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
                "title": "Répartition des Flux",
                "datasetIndex": 0,
                "mapping": {
                    "date": "mois_annee",
                    "value": "amount",
                    "hierarchy": ["scheme", "tsp"]
                },
                "options": {
                    "useLogScale": False # Ensuring linear scale for % check
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

def test_sunburst_structure_and_breadcrumbs(page: Page, generated_report):
    """
    TC01: Validates the global layout specific to Sunburst.
    Checks: Breadcrumbs existence, Chart rendering (N & N-1).
    """
    page.goto(generated_report)
    
    # 1. Breadcrumbs container (Inserted before vizWrapper)
    breadcrumbs = page.locator(".breadcrumbs")
    expect(breadcrumbs).to_be_visible()
    
    # Initial state: "Total" is active
    expect(breadcrumbs.locator(".crumb.active")).to_have_text("Total")
    
    # 2. Charts Presence (YoY is true by default in BaseWidget)
    # Should see 2025 and 2024
    charts = page.locator(".sub-chart")
    expect(charts).to_have_count(2)
    
    # Ensure SVG is rendered
    expect(charts.first.locator("svg")).to_be_visible()


def test_sunburst_zoom_interaction_and_sync(page: Page, generated_report):
    """
    TC02: Validates Zoom In/Out interaction and Synchronization.
    Scenario: Click "Visa" on Chart N -> Chart N-1 should also zoom -> Breadcrumb updates.
    """
    page.goto(generated_report)
    
    charts = page.locator(".sub-chart")
    chart_n = charts.last      # 2025
    chart_n1 = charts.first    # 2024
    
    # 1. Action: Click "Visa" slice in 2025
    # The slice text is usually hidden for small slices, but existing in DOM
    # We target the path that contains the title "Visa" (D3 binding)
    # Note: We filter by text because your code puts the name in the Tooltip (<title>)
    visa_slice_n = chart_n.locator("path").filter(has_text="Visa").first
    visa_slice_n.dispatch_event("click") #Click doesn't work
    
    # 2. Verify Breadcrumb Update
    breadcrumbs = page.locator(".breadcrumbs")
    # Should show: Total › Visa
    expect(breadcrumbs).to_contain_text("Total")
    expect(breadcrumbs).to_contain_text("Visa")
    expect(breadcrumbs.locator(".crumb.active")).to_have_text("Visa")
    
    # 3. Verify Sync on N-1 (2024)
    # If synced, the central circle of 2024 should now represent "Visa" (or parent of zoom)
    # The easiest check is that the "Worldline" slice (child of Visa) is now big/visible
    # or that the chart has transitioned.
    # We can check that the tooltips for the visible slices are now children of Visa
    worldline_slice_n1 = chart_n1.locator("path").filter(has_text="Worldline").first
    expect(worldline_slice_n1).to_be_visible()
    
    # 4. Action: Zoom Out via Breadcrumb
    page.locator(".breadcrumbs .crumb", has_text="Total").click()
    
    # 5. Verify Reset
    expect(breadcrumbs.locator(".crumb.active")).to_have_text("Total")
    expect(breadcrumbs).not_to_contain_text("Visa")

def test_sunburst_tooltip_accuracy_child_node(page: Page, generated_report):
    """
    TC03: Validates Data Mapping and Percentage Calculation on a CHILD node.
    
    Data Context (2025):
    - Global Total: 4000
    - Visa Total: 2000
    - Visa -> Worldline (Child): 1000
    
    Expected Tooltip for 'Visa > Worldline':
    - Path: "Visa > Worldline"
    - Value: "1 000"
    - Ratio (Global): 1000 / 4000 = 25.0%
    """
    page.goto(generated_report)
    
    # On cible le graphique de 2025
    chart_n = page.locator(".sub-chart").last
    
    # Stratégie de ciblage :
    # Le code JS génère le texte du tooltip sous la forme : "Parent > Enfant Valeur (Ratio)"
    # On va chercher le path qui contient spécifiquement le chemin hiérarchique "Visa > Worldline"
    # Cela garantit qu'on tape sur l'enfant et pas sur le parent "Visa" ni sur le "Worldline" de "CB".
    
    child_slice = chart_n.locator("path").filter(has_text="Visa > Worldline").first
    
    # On vérifie que cet enfant existe bien graphiquement
    expect(child_slice).to_be_visible()
    
    # Récupération du contenu textuel (le <title> caché)
    tooltip_text = child_slice.text_content()
    
    print(f"Tooltip Enfant trouvé : '{tooltip_text}'")
    
    # 1. Vérification du Chemin Hiérarchique
    assert "Visa > Worldline" in tooltip_text, \
        f"Le chemin hiérarchique est incorrect. Attendu 'Visa > Worldline', reçu: {tooltip_text}"
    
    # 2. Vérification de la Valeur (1000)
    # Format attendu : "1 000" ou "1000" selon les espaces
    assert re.search(r"1[\s\u202f\u00a0]*000", tooltip_text), \
        f"La valeur 1000 n'a pas été trouvée correctement formatée dans : {tooltip_text}"
    
    # 3. Vérification du Pourcentage Global (25.0%)
    # Calcul : 1000 (Enfant) / 4000 (Total Global) = 25%
    # Le test doit être strict sur le chiffre mais souple sur les parenthèses
    assert "25.0%" in tooltip_text or "25%" in tooltip_text, \
        f"Le pourcentage calculé est incorrect. Attendu 25.0%, reçu : {tooltip_text}"

def test_log_scale_badge_visibility(page: Page, generated_report):
    """
    TC04: Regression check for the Log Scale badge.
    Since config useLogScale is False by default/in fixture, badge should be HIDDEN.
    """
    page.goto(generated_report)
    
    # The class .log-svg is used for the badge
    badge = page.locator(".log-svg")
    expect(badge).to_have_count(0)