import os
import sys
import pytest
from playwright.sync_api import Page, expect

# --- Imports ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dashboard_engine.generator import DashboardGenerator

# --- Data Setup pour Sankey ---

@pytest.fixture(scope="module")
def sankey_data_file(tmp_path_factory):
    # Données complexes sur 3 niveaux :
    # Level 1 (Scheme) -> Level 2 (Acquirer) -> Level 3 (Region)
    # On couvre 2024 (N-1) et 2025 (N) pour tester le YoY et la stabilité des couleurs.
    
    csv_content = """mois_annee,scheme,acquirer,region,amount
# --- Année 2024 (N-1) ---
2024-01,Visa,Worldline,France,1000
2024-01,Visa,Nets,Europe,500
2024-01,CB,Worldline,France,2000
2024-01,Mastercard,Adyen,Monde,1500

# --- Année 2025 (N) ---
# Visa augmente, CB stagne, Mastercard change
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
                    # Définition des 3 niveaux
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


# --- Tests Spécifiques Sankey ---

def test_TC01_sankey_render_structural_elements(page: Page, sankey_report):
    """
    TC01: Vérifie que le widget Sankey génère bien les éléments SVG sur 3 niveaux.
    Basé sur les données 2025.
    """
    page.goto(sankey_report)
    
    # On cible le graphique 2025
    chart_2025 = page.locator(".sub-chart", has=page.locator("h4", has_text="2025"))
    svg = chart_2025.locator("svg")
    expect(svg).to_be_visible()

    # 1. Vérification des Noeuds (Rectangles)
    # L1: Visa, CB, Mastercard (3)
    # L2: Worldline, Nets, Adyen (3)
    # L3: France, Europe, Monde (3)
    # Total attendu : 9 noeuds
    nodes = svg.locator("rect")
    expect(nodes).to_have_count(9)

    # 2. Vérification des Liens (Paths)
    # L1->L2 : Visa->WL, Visa->Nets, CB->WL, MC->Adyen, MC->WL (5 liens)
    # L2->L3 : WL->France, Nets->Europe, Adyen->Monde (Note: WL aggrège les flux de Visa, CB, MC vers France)
    # Le nombre exact dépend de l'agrégation D3, mais on doit en avoir au moins 5.
    links = svg.locator("path")
    count = links.count()
    assert count >= 5, f"Pas assez de liens pour 3 niveaux ({count} trouvés)"

def test_TC02_sankey_filtering_interaction(page: Page, sankey_report):
    """
    TC02: Vérifie le filtrage. En cliquant sur 'Visa' (Niveau 1), 
    on doit voir les flux se propager jusqu'au niveau 3.
    """
    page.goto(sankey_report)
    chart_2025 = page.locator(".sub-chart", has=page.locator("h4", has_text="2025"))
    
    # Clic sur Visa
    visa_node = chart_2025.locator("rect").filter(has_text="Visa").first
    visa_node.click()

    # Vérif Titre
    expect(chart_2025.locator("h4")).to_contain_text("Filtre: Visa")

    # Vérif Flux Restants (Visa -> WL/Nets -> France/Europe)
    links = chart_2025.locator("svg path")
    expect(links).to_have_count(4)

    # Reset
    page.locator("h4 span", has_text="✖").first.click()
    
    # On doit retrouver le graphe complet (8 liens au total pour 2025)
    # L1->L2 (5 liens) + L2->L3 (3 liens) = 8
    expect(links).to_have_count(8)

def test_TC03_sankey_overlay_percentage_logic(page: Page, sankey_report):
    """
    TC03: Vérifie le calcul du pourcentage dans le tooltip pour 2025.
    
    Calculs pour 2025 (Niveau 1 - Scheme):
    - Visa: 1200 + 600 = 1800
    - CB: 2000
    - Mastercard: 1600 + 400 = 2000
    --------------------------------
    Total Niveau 1 = 1800 + 2000 + 2000 = 5800
    
    Pourcentage Visa attendu: 1800 / 5800 = 31.03% -> "31.0%"
    Pourcentage CB attendu:   2000 / 5800 = 34.48% -> "34.5%"
    """
    page.goto(sankey_report)
    chart_2025 = page.locator(".sub-chart", has=page.locator("h4", has_text="2025"))

    # 1. Vérification Visa
    visa_tooltip = chart_2025.locator("rect").filter(has_text="Visa").locator("title").first
    txt_visa = visa_tooltip.text_content()
    assert "31.0%" in txt_visa, f"Visa % incorrect. Attendu ~31.0%, Reçu: {txt_visa}"

    # 2. Vérification CB
    cb_tooltip = chart_2025.locator("rect").filter(has_text="CB").locator("title").first
    txt_cb = cb_tooltip.text_content()
    assert "34.5%" in txt_cb, f"CB % incorrect. Attendu ~34.5%, Reçu: {txt_cb}"

    # 3. Vérification Niveau 2 (Acquirer)
    # Worldline reçoit : 1200 (Visa) + 2000 (CB) + 400 (MC) = 3600
    # Nets reçoit : 600 (Visa)
    # Adyen reçoit : 1600 (MC)
    # Total Niveau 2 = 3600 + 600 + 1600 = 5800 (cohérent)
    # Pct Worldline = 3600 / 5800 = 62.06% -> "62.1%"
    
    wl_tooltip = chart_2025.locator("rect").filter(has_text="Worldline").locator("title").first
    txt_wl = wl_tooltip.text_content()
    assert "62.1%" in txt_wl, f"Worldline % incorrect. Attendu ~62.1%, Reçu: {txt_wl}"
    

def test_TC04_sankey_color_consistency(page: Page, sankey_report):
    """
    TC04: Vérifie la stabilité des couleurs entre N-1 (2024) et N (2025).
    "Mastercard" existe dans les deux années, il doit garder la même couleur.
    """
    page.goto(sankey_report)

    # Graph 2024
    chart_2024 = page.locator(".sub-chart", has=page.locator("h4", has_text="2024"))
    color_mc_24 = chart_2024.locator("rect").filter(has_text="Mastercard").first.get_attribute("fill")

    # Graph 2025
    chart_2025 = page.locator(".sub-chart", has=page.locator("h4", has_text="2025"))
    color_mc_25 = chart_2025.locator("rect").filter(has_text="Mastercard").first.get_attribute("fill")

    # Vérification
    assert color_mc_24 == color_mc_25, f"Couleur Mastercard instable: {color_mc_24} vs {color_mc_25}"

    # Vérif qu'il est différent de Visa
    color_visa_25 = chart_2025.locator("rect").filter(has_text="Visa").first.get_attribute("fill")
    assert color_mc_25 != color_visa_25, "Mastercard et Visa ne doivent pas avoir la même couleur"

def test_TC05_sankey_empty_year_message(page: Page, sankey_report):
    """
    TC05: Vérifie le comportement quand une année (N-1) n'a pas de données.
    Scénario :
    - Le dataset contient 2024 et 2025.
    - On sélectionne l'année 2024.
    - Résultat attendu : 
        - 2024 (N) affiche le graphique.
        - 2023 (N-1) affiche le message "Aucune donnée".
    """
    page.goto(sankey_report)

    # 1. On change l'année pour 2024 via le menu déroulant
    # On cherche le sélecteur dans le groupe de contrôle "Année"
    year_select = page.locator(".control-group", has_text="Année").locator("select")
    year_select.select_option("2024")

    # 2. Vérification de l'année N (2024) -> Doit avoir un SVG
    chart_2024 = page.locator(".sub-chart", has=page.locator("h4", has_text="2024"))
    expect(chart_2024.locator("svg")).to_be_visible()

    # 3. Vérification de l'année N-1 (2023) -> Doit avoir le message, pas de SVG
    chart_2023 = page.locator(".sub-chart", has=page.locator("h4", has_text="2023"))
    
    # On vérifie que le SVG est absent
    expect(chart_2023.locator("svg")).not_to_be_visible()
    
    # On vérifie la présence du message défini dans le code JS (Aucune donnée pour ce filtre.)
    expect(chart_2023).to_contain_text("Aucune donnée")