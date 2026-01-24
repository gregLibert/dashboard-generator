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
    """
    Conteneur global (liste) pour accumuler les données de couverture brute 
    de tous les tests exécutés durant la session.
    """
    return []

@pytest.fixture(scope="function", autouse=True)
def capture_js_coverage(page: Page, js_coverage_global):
    """
    Fixture automatique qui s'exécute autour de chaque test UI.
    Elle active la couverture JS (V8) si le navigateur est compatible (Chromium).
    """
    # --- 1. Vérifications de compatibilité ---
    
    # La couverture V8 ne fonctionne que sur Chromium (Chrome/Edge).
    # Firefox et WebKit n'ont pas cette API exposée via Playwright.
    try:
        browser_name = page.context.browser.browser_type.name
        if browser_name != "chromium":
            # Si ce n'est pas Chromium, on exécute le test sans couverture
            yield
            return
    except Exception:
        # Si on n'arrive pas à déterminer le navigateur, on skip la couverture par sécurité
        yield
        return

    # Vérification que l'objet page possède bien l'attribut coverage
    if not hasattr(page, "coverage"):
        print(f"⚠️ Attention: L'API 'page.coverage' n'est pas disponible.")
        yield
        return

    # --- 2. Démarrage de la couverture ---
    coverage_started = False
    try:
        # reset_on_navigation=False est vital pour les SPA ou si le JS s'exécute au chargement
        page.coverage.start_js_coverage(reset_on_navigation=False)
        coverage_started = True
    except Exception as e:
        print(f"⚠️ Impossible de démarrer la couverture JS : {e}")

    # --- 3. Exécution du Test ---
    yield

    # --- 4. Arrêt et Collecte ---
    if coverage_started:
        try:
            coverage_data = page.coverage.stop_js_coverage()
            js_coverage_global.extend(coverage_data)
        except Exception as e:
            print(f"⚠️ Erreur lors de l'arrêt de la couverture JS : {e}")

@pytest.fixture(scope="session", autouse=True)
def generate_js_report(js_coverage_global):
    """
    S'exécute une seule fois à la fin de TOUTE la session de test.
    Sauvegarde les données, appelle le script Node.js pour le HTML, et génère le badge SVG.
    """
    yield # Attend la fin de tous les tests
    
    # Si aucune donnée n'a été collectée (ex: tests lancés sur Firefox), on arrête là.
    if not js_coverage_global:
        print("\nℹ️ Aucune donnée de couverture JS collectée (Navigateur non-Chromium ?)")
        return

    # 1. Sauvegarder les données brutes dans un fichier temporaire
    os.makedirs("output", exist_ok=True)
    raw_file = "output/raw_v8_coverage.json"
    
    try:
        with open(raw_file, "w") as f:
            json.dump(js_coverage_global, f)
    except IOError as e:
        print(f"❌ Erreur d'écriture du fichier raw coverage : {e}")
        return
    
    # 2. Appeler le script Node pour générer le rapport HTML
    # On suppose que le script est dans 'scripts/generate_js_coverage.js' à la racine
    print("\n📊 Génération du rapport de couverture JS (via Node.js)...")
    node_script = os.path.join("scripts", "generate_js_coverage.js")
    
    if not os.path.exists(node_script):
        print(f"⚠️ Script de génération introuvable : {node_script}")
        return

    try:
        # On appelle node en passant le chemin du fichier brut
        subprocess.run(["node", node_script, raw_file], check=True, shell=True if os.name == 'nt' else False)
    except subprocess.CalledProcessError:
        print("❌ Erreur lors de l'exécution du script Node.js (vérifiez 'npm install').")
        return
    except FileNotFoundError:
        print("⚠️ Node.js n'est pas installé dans l'environnement.")
        return

    # 3. Générer le Badge SVG via Python (anybadge)
    # On lit le résumé JSON généré par le script Node.js
    summary_file = "output/js-coverage-summary.json"
    if os.path.exists(summary_file):
        try:
            with open(summary_file, "r") as f:
                summary = json.load(f)
                pct = summary.get("pct", 0)
                
                # Import dynamique pour ne pas planter si anybadge manque
                import anybadge
                badge = anybadge.Badge(
                    label='JS Coverage', 
                    value=f'{pct:.1f}%', 
                    default_color='gray',
                    thresholds={50: 'red', 70: 'yellow', 90: 'green'}
                )
                badge.write_badge('js-coverage.svg', overwrite=True)
                print(f"✅ Badge JS généré : {pct:.1f}% -> js-coverage.svg")
                
        except (ImportError, Exception) as e:
            print(f"⚠️ Impossible de générer le badge JS : {e}")
    else:
        print(f"⚠️ Fichier résumé introuvable ({summary_file}), pas de badge généré.")