import pytest
import json
import os
import subprocess
from playwright.sync_api import Page

# ==========================================
# FIXTURES DE COUVERTURE JS (V8 / Playwright)
# ==========================================

@pytest.fixture(scope="session")
def js_coverage_global():
    print("\n[DEBUG] Initialisation du conteneur global de couverture.")
    return []

@pytest.fixture(scope="function", autouse=True)
def capture_js_coverage(page: Page, js_coverage_global):
    """
    Fixture automatique qui s'exécute autour de chaque test UI.
    """
    # 1. Vérification du navigateur
    try:
        browser_name = page.context.browser.browser_type.name
        if browser_name != "chromium":
            yield
            return
    except Exception:
        yield
        return

    # 2. Vérification de l'API (ou bypass CDP)
    # Si page.coverage n'existe pas, on tente via CDP direct pour contourner le bug
    if not hasattr(page, "coverage"):
        # Tentative CDP direct
        try:
            session = page.context.new_cdp_session(page)
            session.send("Profiler.enable")
            session.send("Profiler.startPreciseCoverage", {"callCount": False, "detailed": True})
            yield
            res = session.send("Profiler.takePreciseCoverage")
            session.send("Profiler.stopPreciseCoverage")
            data = res.get("result", [])
            js_coverage_global.extend(data)
        except Exception:
            yield
        return

    # 3. Démarrage Standard
    coverage_started = False
    try:
        page.coverage.start_js_coverage(reset_on_navigation=False)
        coverage_started = True
    except Exception:
        pass

    yield # Exécution du test

    # 4. Arrêt et Collecte
    if coverage_started:
        try:
            coverage_data = page.coverage.stop_js_coverage()
            js_coverage_global.extend(coverage_data)
        except Exception:
            pass

@pytest.fixture(scope="session", autouse=True)
def generate_js_report(js_coverage_global):
    yield # Attend la fin des tests
    
    total_entries = len(js_coverage_global)
    if total_entries == 0:
        print("[DEBUG] 🛑 Arrêt : Aucune donnée à traiter.")
        return

    # Sauvegarde JSON
    os.makedirs("output", exist_ok=True)
    raw_file = os.path.abspath("output/raw_v8_coverage.json")
    
    with open(raw_file, "w") as f:
        json.dump(js_coverage_global, f)
    
    # Appel Node.js
    node_script = os.path.abspath(os.path.join("scripts", "generate_js_coverage.js"))
    
    if os.path.exists(node_script):
        try:
            # encoding='utf-8' pour éviter le crash cp1252 sur Windows
            result = subprocess.run(
                ["node", node_script, raw_file], 
                capture_output=True, 
                text=True, 
                encoding='utf-8', 
                shell=True if os.name == 'nt' else False
            )
            print("[DEBUG] Sortie Node.js :\n", result.stdout)
            if result.stderr:
                print("[DEBUG] Erreur Node.js :\n", result.stderr)
                
        except Exception as e:
            print(f"[DEBUG] ❌ Erreur appel subprocess : {e}")

    # Badge Python
    summary_file = "output/js-coverage-summary.json"
    if os.path.exists(summary_file):
        try:
            with open(summary_file, "r") as f:
                content = f.read()
                # Debug : Voir ce que contient le fichier
                print(f"[DEBUG] Contenu du résumé JS : '{content}'")
                
                if not content.strip():
                    pct = 0.0
                else:
                    summary = json.loads(content)
                    # Conversion robuste
                    raw_pct = summary.get("pct", 0)
                    pct = float(raw_pct) if raw_pct != "" else 0.0
                
                import anybadge
                badge = anybadge.Badge(
                    label='JS Coverage', 
                    value=f'{pct:.1f}%', 
                    default_color='gray',
                    thresholds={50: 'red', 70: 'yellow', 90: 'green'}
                )
                badge.write_badge('js-coverage.svg', overwrite=True)
                print(f"[DEBUG] ✅ Badge JS généré : {pct:.1f}% -> js-coverage.svg")
                
        except Exception as e:
            print(f"[DEBUG] ❌ Erreur badge : {e}")