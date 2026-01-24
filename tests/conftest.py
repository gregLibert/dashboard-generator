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
    # 1. Vérification du navigateur
    try:
        browser_name = page.context.browser.browser_type.name
        if browser_name != "chromium":
            yield
            return
    except Exception:
        yield
        return

    # 2. TENTATIVE D'ACCÈS DIRECT (Bypass hasattr)
    try:
        # On essaie d'accéder à la propriété. Si elle n'existe pas, ça lèvera une erreur ici.
        cov_obj = page.coverage 
        
        # Si on arrive ici, c'est que l'objet existe ! On lance la couverture.
        print(f"\n[DEBUG] ✅ API Coverage détectée. Démarrage...")
        cov_obj.start_js_coverage(reset_on_navigation=False)
        
        yield # Exécution du test
        
        # Arrêt
        print(f"[DEBUG] 🛑 Arrêt couverture...")
        data = cov_obj.stop_js_coverage()
        print(f"[DEBUG] 📥 Données reçues : {len(data)} entrées.")
        js_coverage_global.extend(data)

    except AttributeError:
        # C'est ici qu'on va comprendre ce qui se passe
        print(f"\n[DEBUG] ❌ ERREUR FATALE : L'objet Page n'a pas d'attribut 'coverage'.")
        print(f"[DEBUG] Type de l'objet page : {type(page)}")
        print(f"[DEBUG] Liste des attributs disponibles sur 'page' :")
        # On affiche les 20 premiers attributs pour voir à quoi on a affaire
        print([attr for attr in dir(page) if not attr.startswith('_')][:20])
        yield
        
    except Exception as e:
        print(f"[DEBUG] ❌ Autre erreur imprévue : {e}")
        yield

@pytest.fixture(scope="session", autouse=True)
def generate_js_report(js_coverage_global):
    yield # Attend la fin des tests
    
    total_entries = len(js_coverage_global)
    print(f"\n[DEBUG] === FIN DE SESSION === Total entrées JS collectées : {total_entries}")

    if total_entries == 0:
        print("[DEBUG] 🛑 Arrêt : Aucune donnée à traiter.")
        return

    # Sauvegarde JSON
    os.makedirs("output", exist_ok=True)
    raw_file = os.path.abspath("output/raw_v8_coverage.json")
    print(f"[DEBUG] Écriture du fichier brut : {raw_file}")
    
    with open(raw_file, "w") as f:
        json.dump(js_coverage_global, f)
    
    # Appel Node.js
    node_script = os.path.abspath(os.path.join("scripts", "generate_js_coverage.js"))
    print(f"[DEBUG] Lancement du script Node : {node_script}")
    
    if not os.path.exists(node_script):
        print(f"[DEBUG] ❌ Script introuvable !")
        return

    try:
        # shell=True est souvent requis sous Windows pour trouver 'node' dans le PATH
        result = subprocess.run(
            ["node", node_script, raw_file], 
            capture_output=True, 
            text=True, 
            shell=True if os.name == 'nt' else False
        )
        print("[DEBUG] Sortie Node.js (STDOUT) :\n", result.stdout)
        if result.stderr:
            print("[DEBUG] Erreur Node.js (STDERR) :\n", result.stderr)
            
    except Exception as e:
        print(f"[DEBUG] ❌ Erreur appel subprocess : {e}")

    # Badge Python
    summary_file = "output/js-coverage-summary.json"
    if os.path.exists(summary_file):
        print("[DEBUG] Génération du badge SVG...")
        try:
            with open(summary_file, "r") as f:
                summary = json.load(f)
                pct = summary.get("pct", 0)
                import anybadge
                badge = anybadge.Badge(label='JS Coverage', value=f'{pct:.1f}%', default_color='gray', thresholds={50: 'red', 70: 'yellow', 90: 'green'})
                badge.write_badge('js-coverage.svg', overwrite=True)
                print(f"[DEBUG] ✅ Badge créé avec succès ({pct:.1f}%)")
        except Exception as e:
            print(f"[DEBUG] ❌ Erreur badge : {e}")
    else:
        print(f"[DEBUG] ❌ Fichier résumé introuvable : {summary_file}")