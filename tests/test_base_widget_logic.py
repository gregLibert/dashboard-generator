import os
import sys
import pytest
from playwright.sync_api import Page, expect

# --- 1. Imports ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dashboard_engine.generator import DashboardGenerator

# --- 2. Data Setup ---

@pytest.fixture(scope="module")
def csv_data_file(tmp_path_factory):
    # Two years (2024, 2025) and multiple quarters
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
    TC01: Markdown in widget description is rendered as HTML (bold/italic/link).
    """
    page.goto(generated_report)
    
    # 1. Open info popover
    page.click(".info-icon")
    
    desc_box = page.locator(".widget-description")
    expect(desc_box).to_be_visible()
    
    # 2. HTML from Showdown (** -> strong, * -> em/i)
    html_content = desc_box.inner_html()
    
    assert "<strong>Ceci</strong>" in html_content or "<b>Ceci</b>" in html_content
    assert "<em>Markdown</em>" in html_content or "<i>Markdown</i>" in html_content
    assert '<a href="http://google.com"' in html_content

def test_date_parsing_and_years_extraction(page: Page, generated_report):
    """
    TC02: Year select lists years present in the CSV (2024, 2025).
    """
    page.goto(generated_report)
    
    year_select = page.locator('select[data-testid="widget-year-select"]').first
    
    # Option labels
    options = year_select.locator("option").all_inner_texts()
    
    assert "2024" in options
    assert "2025" in options
    
    # Default selection: latest year (2025)
    expect(year_select).to_have_value("2025")

def test_cascade_updates_period_logic(page: Page, generated_report):
    """
    TC03: Period type change cascades to period value options (month -> quarter).
    """
    page.goto(generated_report)
    
    type_select = page.locator(".ctrl-period-type select")
    value_select = page.locator(".ctrl-period-value select")
    
    # 1. Initial: month view
    expect(type_select).to_have_value("mois")
    # First option should be January (or current month in live data)
    expect(value_select.locator("option").first).to_contain_text("Janvier")
    
    # 2. Switch to quarter
    type_select.select_option("trimestre")
    
    # 3. Second select should list T1..T4
    expect(value_select.locator("option").first).to_contain_text("T1")
    expect(value_select.locator("option").last).to_contain_text("T4")

def test_filtering_logic_ui_feedback(page: Page, generated_report):
    """
    TC04: Period filter changes should update the sub-chart title (proves update() ran).
    """
    page.goto(generated_report)
    
    # Semester 2
    page.locator(".ctrl-period-type select").select_option("semestre")
    page.locator(".ctrl-period-value select").select_option("2")  # S2

    # Sub-chart title should mention S2
    chart_title = page.locator(".sub-chart h4").last
    expect(chart_title).to_contain_text("S2")