import pytest
import json
import os
import subprocess
from playwright.sync_api import Page

@pytest.fixture(scope="session")
def js_coverage_global():
    """Conteneur pour accumuler la couverture de tous les tests."""
    return []

@pytest.fixture(scope="function", autouse=True)
def capture_js_coverage(page: Page, js_coverage_global):
    # 1. Démarrer la couverture JS (V8)
    page.coverage.start_js_coverage(reset_on_navigation=False)
    
    yield
    
    # 2. Récupérer les données brutes
    coverage_data = page.coverage.stop_js_coverage()
    js_coverage_global.extend(coverage_data)

@pytest.fixture(scope="session", autouse=True)
def generate_js_report(js_coverage_global):
    """
    À la fin de TOUS les tests, on génère le rapport et le badge.
    """
    yield # Attend la fin des tests
    
    if not js_coverage_global:
        return

    # 1. Sauvegarder les données brutes dans un fichier temporaire
    os.makedirs("output", exist_ok=True)
    raw_file = "output/raw_v8_coverage.json"
    with open(raw_file, "w") as f:
        json.dump(js_coverage_global, f)
    
    # 2. Appeler le script Node pour générer le HTML
    print("\n📊 Génération du rapport de couverture JS...")
    try:
        subprocess.run(["node", "scripts/generate_js_coverage.js", raw_file], check=True)
    except FileNotFoundError:
        print("⚠️ Node.js n'est pas installé ou le script est introuvable.")
        return

    # 3. Générer le Badge SVG via Python (anybadge)
    # On lit le résumé généré par le script JS
    try:
        with open("output/js-coverage-summary.json", "r") as f:
            summary = json.load(f)
            pct = summary.get("pct", 0)
            
            import anybadge
            badge = anybadge.Badge(
                label='JS Coverage', 
                value=f'{pct:.1f}%', 
                default_color='gray',
                thresholds={50: 'red', 70: 'yellow', 90: 'green'}
            )
            badge.write_badge('js-coverage.svg', overwrite=True)
            print(f"✅ Badge JS généré : {pct:.1f}% -> js-coverage.svg")
            
    except (FileNotFoundError, ImportError):
        print("⚠️ Impossible de générer le badge JS (fichier manquant ou anybadge absent).")