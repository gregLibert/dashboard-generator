import os
import re
import sys
import pytest
from playwright.sync_api import Page, expect

# --- 1. Gestion des imports du projet ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from dashboard_engine.generator import DashboardGenerator
except ImportError:
    # Mock pour éviter les erreurs d'import si le fichier n'est pas présent
    class DashboardGenerator:
        pass

# --- 2. Configuration des données ---

@pytest.fixture(scope="module")
def csv_data_file(tmp_path_factory):
    """
    Données conçues pour tester l'aggrégation (Somme).
    Janvier 2025 a 3 entrées pour vérifier que le graph affiche bien le TOTAL.
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


# --- 3. Tests Fonctionnels et Métier ---

def test_evolution_structure_and_hidden_controls(page: Page, generated_report):
    """
    Vérifie la structure et surtout que les contrôles inutiles pour ce widget
    (Type de période, Valeur de période) sont bien masqués par le CSS.
    """
    page.goto(generated_report)
    
    # 1. Titre et Description
    expect(page.locator(".chart-title")).to_have_text("Évolution Mensuelle (N vs N-1)")
    page.click(".info-icon")
    expect(page.locator(".widget-description")).to_contain_text("Validation de l'aggrégation")

    # 2. Vérification des contrôles masqués (Spécificité EvolutionWidget)
    # Les classes .ctrl-period-type et .ctrl-period-value doivent être cachées
    ctrl_type = page.locator(".ctrl-period-type")
    ctrl_value = page.locator(".ctrl-period-value")
    
    # expect(locator).to_be_hidden() vérifie display:none, visibility:hidden, etc.
    expect(ctrl_type).to_be_hidden()
    expect(ctrl_value).to_be_hidden()
    
    # 3. Vérification que le sélecteur d'année, lui, est visible
    expect(page.locator("text=Année:")).to_be_visible()


def test_evolution_graph_yoy_toggling(page: Page, generated_report):
    """
    Vérifie le rendu des lignes (Courbe N et Courbe N-1) et le toggle YoY.
    """
    page.goto(generated_report)
    
    # Sélectionner 2025 pour être sûr d'avoir N (2025) et N-1 (2024)
    page.locator(".control-group", has_text="Année").locator("select").select_option("2025")
    
    container = page.locator(".sub-chart svg")
    
    # 1. Vérifier la présence de la courbe N (Ligne continue)
    # Dans le code JS: stroke-width=3, pas de dasharray
    line_n = container.locator("path[stroke-width='3']")
    expect(line_n).to_be_visible()
    
    # 2. Vérifier la présence de la courbe N-1 (Ligne pointillée)
    # Dans le code JS: stroke-dasharray='5,5'
    line_n1 = container.locator("path[stroke-dasharray='5,5']")
    expect(line_n1).to_be_visible()
    
    # 3. Désactiver le YoY
    page.locator(".ctrl-yoy input").uncheck()
    
    # 4. Vérifier que la courbe N-1 a disparu
    expect(line_n1).not_to_be_visible()
    # La courbe N doit rester
    expect(line_n).to_be_visible()


def test_data_aggregation_accuracy(page: Page, generated_report):
    """
    CRITIQUE : Vérifie que le code JS somme correctement les valeurs mensuelles.
    Données pour Janvier 2025 (N) :
    - Visa: 1500
    - CB: 2300
    - Mastercard: 800
    ----------------
    TOTAL ATTENDU : 4600
    """
    page.goto(generated_report)
    
    # Setup : Année 2025
    page.locator(".control-group", has_text="Année").locator("select").select_option("2025")
    
    # On cible les points (cercles) de la courbe N
    # Le JS dessine des cercles avec la classe 'dotN' (ou implicitement via selectAll)
    # Dans le code fourni: svg.selectAll(".dotN").data(dataLineN).join("circle")
    # Donc on peut cibler les <circle>
    
    dots = page.locator(".sub-chart svg .dot-N")
    
    # Janvier est le premier point (index 0) car les données sont triées
    january_dot = dots.nth(0)
    
    # Récupération du Tooltip (balise title interne)
    # .text_content() lit le contenu invisible du <title> SVG
    tooltip_text = january_dot.text_content()
    
    print(f"Tooltip trouvé pour Janvier : '{tooltip_text}'")
    
    # Assertion 1 : Le mois est correct
    assert "Janvier" in tooltip_text
    
    # Assertion 2 : La somme est correcte (4 600)
    # Regex pour gérer les espaces (4600, 4 600, 4<nbsp>600)
    # On cherche "4" suivi d'espace optionnel et "600"
    match_sum = re.search(r"4[\s\u202f\u00a0]*600", tooltip_text)
    
    assert match_sum, f"Erreur de somme ! Attendu '4 600', trouvé : {tooltip_text}"

def test_evolution_legend_labels(page: Page, generated_report):
    """
    Vérifie la présence des légendes internes au graphique (Titres des séries).
    Le code JS dessine : "Année 2025" (Bleu) et "Année 2024" (Gris/Pointillé).
    """
    page.goto(generated_report)
    
    # On se met en 2025 avec YoY activé
    page.locator(".control-group", has_text="Année").locator("select").select_option("2025")
    page.locator(".ctrl-yoy input").check()
    
    # On cible le SVG
    svg = page.locator(".sub-chart svg")
    
    # Vérification de la légende Année N
    # Note : Le texte est dessiné via SVG <text>, on peut le chercher par contenu
    legend_n = svg.locator("text", has_text="Année 2025")
    expect(legend_n).to_be_visible()
    
    # Vérification de la légende Année N-1
    legend_n1 = svg.locator("text", has_text="Année 2024")
    expect(legend_n1).to_be_visible()


def test_export_csv_functionality(page: Page, generated_report):
    """
    Vérifie que le bouton d'export fonctionne aussi sur cette page.
    Critique : S'assurer que le téléchargement se déclenche et a un nom cohérent.
    """
    page.goto(generated_report)

    # Le bouton est global dans le header
    export_btn = page.locator("#btn-export")
    expect(export_btn).to_be_visible()

    # Interception du téléchargement
    with page.expect_download() as download_info:
        export_btn.click()

    download = download_info.value
    
    # Vérifications de base sur le fichier
    fname = download.suggested_filename
    assert fname.endswith(".csv")
    assert "qa_evolution_integration" in fname.lower() or "dataset" in fname.lower()
    
    # Vérification rapide du contenu (optionnel mais recommandé)
    file_path = download.path()
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        # On vérifie qu'on retrouve nos headers
        assert "mois_annee" in content
        assert "amount" in content


def test_evolution_n_minus_1_interactivity(page: Page, generated_report):
    """
    Vérifie que l'année N-1 possède désormais des 'boutons' (points) interactifs.
    """
    page.goto(generated_report)
    
    # Setup 2025 + YoY
    page.locator(".control-group", has_text="Année").locator("select").select_option("2025")
    page.locator(".ctrl-yoy input").check()

    container = page.locator(".sub-chart svg")
    
    # On cherche les cercles qui correspondent à N-1.
    # Dans le code JS mis à jour : stroke-dasharray (pour la ligne) mais les cercles 
    # héritent de propriétés ou sont dessinés dans une boucle. 
    # Mon code JS utilise title contenant "Année 2024" pour N-1.
    
    # On cherche un cercle dont le titre contient "Année 2024" (ou l'année précédente selon le dataset)
    dot_n1 = container.locator("circle").filter(has_text="Année 2024").first
    
    expect(dot_n1).to_be_visible()
    
    # Vérification Tooltip N-1
    expect(dot_n1).to_contain_text("Année 2024") # Le <title> est interne
    expect(dot_n1).to_contain_text("Val:")


def test_evolution_percentage_labels(page: Page, generated_report, csv_data_file):
    """
    Vérifie l'affichage des pourcentages d'évolution (+X% / -Y%).
    Utilise les données connues du CSV temporaire :
    Jan 2024 = 1000 (Visa) + 2000 (CB) + 500 (Master) = 3500
    Jan 2025 = 1500 (Visa) + 2300 (CB) + 800 (Master) = 4600
    
    Evolution = (4600 - 3500) / 3500 * 100 = +31.42% -> Arrondi +31%
    """
    page.goto(generated_report)
    page.locator(".control-group", has_text="Année").locator("select").select_option("2025")
    
    # On cherche le text label au dessus du point de Janvier
    # Le label est un <text> avec ancre "middle" et une couleur (vert/rouge)
    
    # On va chercher le texte "+31%" spécifiquement
    label_pct = page.locator(".sub-chart svg text", has_text="+31%")
    
    expect(label_pct).to_be_visible()
    
    # Vérification de la couleur (Vert pour positif)
    # #2e7d32 est le vert défini dans le JS
    expect(label_pct).to_have_attribute("fill", "#2e7d32")


def test_legend_background_fix(page: Page, generated_report):
    """
    Vérifie que la légende possède un fond opaque pour éviter le chevauchement avec la courbe.
    """
    page.goto(generated_report)
    
    # Le JS ajoute un <rect> dans le groupe de légende
    # On cible le dernier <g> (généralement la légende est dessinée en dernier) ou par structure
    
    # On cherche un rect avec fill blanc quasi opaque
    legend_bg = page.locator(".sub-chart svg rect[fill='rgba(255, 255, 255, 0.9)']")
    
    expect(legend_bg).to_be_visible()