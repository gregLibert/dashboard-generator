import os
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
    # Données couvrant 2 années (2024, 2025) et tous les trimestres
    csv_content = """mois_annee,valeur
2024-01,10
2024-04,20
2024-07,30
2024-10,40
2025-01,50
2025-02,60
"""
    fn = tmp_path_factory.mktemp("data") / "base_dataset.csv"
    fn.write_text(csv_content, encoding="utf-8")
    return str(fn)

@pytest.fixture(scope="module")
def generated_report(csv_data_file):
    output_dir = os.path.join(PROJECT_ROOT, "output")
    output_report = os.path.join(output_dir, "_test_base_widget.html")

    with open(csv_data_file, "r", encoding="utf-8") as f:
        csv_content = f.read()

    # On configure un widget "Dummy" (on utilise 'evolution' car il hérite de BaseWidget
    # et on veut tester la logique de base, peu importe le rendu final).
    # L'important est que BaseWidget soit instancié.
    config = {
        "title": "QA Base Widget Logic",
        "widgets": [
            {
                "type": "sankey", # On utilise un type existant pour que la factory fonctionne
                "title": "Test Widget",
                "description": "**Ceci** est du *Markdown* avec [lien](http://google.com).",
                "datasetIndex": 0,
                "mapping": { "date": "mois_annee", "value": "valeur" }
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

def test_markdown_rendering(page: Page, generated_report):
    """
    TC01: Vérifie que la description en Markdown est bien convertie en HTML.
    Entrée: "**Ceci** est du *Markdown*"
    Sortie attendue: "<strong>Ceci</strong> est du <em>Markdown</em>"
    """
    page.goto(generated_report)
    
    # 1. Ouvrir l'info box
    page.click(".info-icon")
    
    desc_box = page.locator(".widget-description")
    expect(desc_box).to_be_visible()
    
    # 2. Vérifier le rendu HTML
    # Note: Showdown convertit ** en <strong> et * en <em> ou <i>
    # On vérifie la présence des balises HTML
    html_content = desc_box.inner_html()
    
    assert "<strong>Ceci</strong>" in html_content or "<b>Ceci</b>" in html_content
    assert "<em>Markdown</em>" in html_content or "<i>Markdown</i>" in html_content
    assert '<a href="http://google.com"' in html_content

def test_date_parsing_and_years_extraction(page: Page, generated_report):
    """
    TC02: Vérifie que le sélecteur d'année contient bien les années extraites du CSV.
    CSV: 2024 et 2025.
    """
    page.goto(generated_report)
    
    year_select = page.locator(".control-group", has_text="Année").locator("select")
    
    # On vérifie les options disponibles
    options = year_select.locator("option").all_inner_texts()
    
    assert "2024" in options
    assert "2025" in options
    
    # Vérifie que la dernière année (2025) est sélectionnée par défaut
    expect(year_select).to_have_value("2025")

def test_cascade_updates_period_logic(page: Page, generated_report):
    """
    TC03: Vérifie la logique de cascade des contrôles (Vue -> Valeur).
    Scénario: Passer de 'Mois' à 'Trimestre'.
    """
    page.goto(generated_report)
    
    type_select = page.locator(".ctrl-period-type select")
    value_select = page.locator(".ctrl-period-value select")
    
    # 1. État initial (Mois)
    expect(type_select).to_have_value("mois")
    # Le premier mois (Janvier) ou le mois courant doit être là
    expect(value_select.locator("option").first).to_contain_text("Janvier")
    
    # 2. Changement -> Trimestre
    type_select.select_option("trimestre")
    
    # 3. Vérification de la mise à jour du 2ème select
    # Il doit contenir T1, T2, T3, T4
    expect(value_select.locator("option").first).to_contain_text("T1")
    expect(value_select.locator("option").last).to_contain_text("T4")

def test_filtering_logic_ui_feedback(page: Page, generated_report):
    """
    TC04: Vérifie que le changement de filtre met à jour le TITRE du graphique.
    C'est la preuve visuelle que update() a été appelé avec les bons paramètres.
    """
    page.goto(generated_report)
    
    # On passe en Semestre 2
    page.locator(".ctrl-period-type select").select_option("semestre")
    page.locator(".ctrl-period-value select").select_option("2") # S2
    
    # Le titre du sous-graphique doit afficher "S2"
    chart_title = page.locator(".sub-chart h4").last
    expect(chart_title).to_contain_text("S2")