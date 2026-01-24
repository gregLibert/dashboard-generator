import os
import re
import sys
import pytest
from playwright.sync_api import Page, expect

# --- 1. Gestion des imports du projet ---
# On remonte à la racine pour trouver 'dashboard_engine'
from dashboard_engine.generator import DashboardGenerator

# Import du vrai moteur (il faut que ce module existe dans ton projet)
try:
    from dashboard_engine.generator import DashboardGenerator
except ImportError:
    # Fallback pour l'exemple si le fichier n'est pas dans la structure exacte
    print("⚠️ Module dashboard_engine non trouvé. Assurez-vous d'être à la racine du projet.")
    # Pour que le code ci-dessous ne plante pas à l'import, on simule (A RETIRER EN PROD)
    class DashboardGenerator:
        def generate(self, config, datasets):
            # Simulation : Retourne le HTML brut fourni dans ton premier prompt
            # En situation réelle, cette classe est importée et non redéfinie
            return "<html>... (Le vrai contenu HTML généré par ta classe) ...</html>"
            pass

# --- 2. Configuration des données de test ---

@pytest.fixture(scope="module")
def csv_data_file(tmp_path_factory):
    """
    Crée un fichier CSV temporaire avec des données couvrant 2024 et 2025.
    Cela permet de tester le cas 'Année N sans N-1'.
    """
    csv_content = """mois_annee,scheme,tsp,amount,option,tech
mois_annee,scheme,tsp,amount,option,tech
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
    fn = tmp_path_factory.mktemp("data") / "sankey_dataset.csv"
    fn.write_text(csv_content, encoding="utf-8")
    return str(fn)

@pytest.fixture(scope="module")
def generated_report(csv_data_file):
    """
    Génère le rapport HTML réel via DashboardGenerator.
    C'est ici qu'on vérifie l'intégration : Config -> Generator -> HTML.
    """
    output_dir = os.path.join(PROJECT_ROOT, "output")
    output_report = os.path.join(output_dir, "_test_sankey_integration.html")

    # Lecture des données (simulées via fichier temporaire ou chemin réel)
    with open(csv_data_file, "r", encoding="utf-8") as f:
        csv_content = f.read()

    # Configuration de test enrichie (avec description pour tester l'info-icon)
    config = {
        "title": "QA Sankey Integration",
        "widgets": [
            {
                "type": "sankey",
                "title": "Flux Test Regression",
                "description": "Validation automatique du rendu graph.", # Ajout pour test
                "datasetIndex": 0,
                "mapping": {
                    "date": "mois_annee",
                    "value": "amount",
                    "path": ["scheme", "tsp", "tech"]
                }
            }
        ]
    }

    # APPEL DU MOTEUR RÉEL
    generator = DashboardGenerator()
    html_content = generator.generate(config, [csv_content])

    # Écriture du fichier
    os.makedirs(output_dir, exist_ok=True)
    with open(output_report, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"\n✅ Rapport généré : {output_report}")
    return f"file:///{output_report.replace(os.sep, '/')}"


# --- 3. Tests Playwright ---

def test_page_structure_and_metadata(page: Page, generated_report):
    """
    Vérifie que le générateur a bien produit la structure HTML de base
    et injecté les métadonnées (Titres, Info box).
    """
    page.goto(generated_report)
    
    # Vérification du titre global injecté par le template
    expect(page.locator("h1")).to_have_text("QA Sankey Integration")
    
    # Vérification du titre du widget (généré par JS via la config)
    expect(page.locator(".chart-title")).to_have_text("Flux Test Regression")

    # Vérification de l'icône d'info et de la description (Feature optionnelle)
    info_icon = page.locator(".info-icon")
    desc_box = page.locator(".widget-description")
    
    expect(info_icon).to_be_visible()
    expect(desc_box).to_be_hidden() # Caché par défaut
    
    info_icon.click()
    expect(desc_box).to_be_visible()
    expect(desc_box).to_contain_text("Validation automatique")


def test_sankey_controls_logic(page: Page, generated_report):
    """
    Vérifie la logique JS des contrôles générés dynamiquement.
    Focus: Changement de Vue (Mois -> Trimestre).
    """
    page.goto(generated_report)

    # Sélecteurs (basés sur ton code JS BaseWidget)
    # Note: J'utilise des sélecteurs robustes basés sur le texte ou la hiérarchie
    period_type_select = page.locator(".ctrl-period-type select")
    period_value_select = page.locator(".ctrl-period-value select")

    # 1. État initial (Mois)
    expect(period_type_select).to_have_value("mois")
    # On vérifie que le sélecteur de valeur contient "Janvier" (texte généré par Utils.moisFR)
    expect(period_value_select.locator("option").first).to_contain_text("Janvier")

    # 2. Interaction : Passage en Trimestre
    period_type_select.select_option("trimestre")

    # 3. Vérification régression
    # Le JS doit avoir reconstruit le 2ème select avec T1, T2...
    expect(period_value_select.locator("option").first).to_contain_text("T1")
    
    # Vérification que le titre du graph s'est mis à jour
    expect(page.locator(".sub-chart h4").first).to_contain_text("T1")


def test_sankey_graph_rendering_and_interaction(page: Page, generated_report):
    """
    Vérifie le rendu et le filtrage.
    Correction : On cible spécifiquement le graphique de l'année N (le dernier)
    pour éviter les erreurs de "Strict Mode" dues au N-1.
    """
    page.goto(generated_report)

    # 1. SETUP : On isole le conteneur du graphique "Année N" (le dernier de la liste)
    # Cela permet de travailler sur un seul SVG et d'éviter les confusions N/N-1
    chart_container = page.locator(".sub-chart").last
    
    # On s'assure que le graphique est chargé
    expect(chart_container.locator("svg path").first).to_be_visible()

    # 2. ETAT INITIAL : Vérifier la présence des concurrents
    # On vérifie que "Visa" et "CB" sont présents avant le clic
    # Note: On utilise filter(has_text=...) car le texte est dans une balise <title> enfant du <rect>
    visa_node = chart_container.locator("svg rect").filter(has_text="Visa")
    cb_node = chart_container.locator("svg rect").filter(has_text="CB")
    
    expect(visa_node).to_be_visible()
    expect(cb_node).to_be_visible()

    # 3. ACTION : Filtrer sur Visa
    # On clique sur le premier noeud Visa trouvé dans ce graphique
    visa_node.first.click()

    # 4. VERIFICATION UI (Le Badge)
    # On cherche le badge UNIQUEMENT dans le header de NOTRE container chart_container
    # Cela résout ton erreur "strict mode violation"
    filter_badge = chart_container.locator("h4 span", has_text="Filtre: Visa")
    expect(filter_badge).to_be_visible()

    # 5. VERIFICATION GRAPHIQUE (La disparition)
    # Si on filtre sur Visa, le noeud "CB" doit disparaître du DOM ou être masqué.
    # Dans D3 Sankey, quand on filtre les données, les noeuds exclus ne sont généralement plus générés.
    expect(cb_node).not_to_be_visible()
    
    # Par contre, Visa doit toujours être là
    expect(visa_node).to_be_visible()

    # 6. RESET
    filter_badge.click()
    
    # 7. VERIFICATION RETOUR A LA NORMALE
    # CB doit réapparaître
    expect(cb_node).to_be_visible()


def test_empty_year_handling(page: Page, generated_report):
    """
    Vérifie la robustesse quand une année n'a pas de données (N-1 vide).
    Données CSV : Commence en 2024.
    Action : Sélectionner 2024 avec N-1 activé (donc 2023).
    Attendu : 2023 affiche "Aucune donnée", 2024 affiche le graph.
    """
    page.goto(generated_report)

    # 1. Sélectionner l'année 2024
    # Le selecteur d'année est dans un control-group avec le label "Année:"
    year_select = page.locator(".control-group", has_text="Année").locator("select")
    year_select.select_option("2024")

    # 2. S'assurer que YoY est coché
    yoy_checkbox = page.locator(".ctrl-yoy input[type='checkbox']")
    if not yoy_checkbox.is_checked():
        yoy_checkbox.check()

    # 3. Analyse des résultats
    sub_charts = page.locator(".sub-chart")
    expect(sub_charts).to_have_count(2) # On doit avoir 2 blocs

    # Bloc 1 (2023 - N-1) : Doit être vide
    chart_2023 = sub_charts.nth(0)
    expect(chart_2023).to_contain_text("2023") # Vérif titre
    expect(chart_2023.locator(".hint")).to_be_visible() # Vérif message d'erreur/vide
    expect(chart_2023.locator(".hint")).to_contain_text("Aucune donnée")
    expect(chart_2023.locator("svg")).to_have_count(0) # Pas de graph

    # Bloc 2 (2024 - N) : Doit avoir un graph
    chart_2024 = sub_charts.nth(1)
    expect(chart_2024).to_contain_text("2024")
    expect(chart_2024.locator("svg")).to_be_visible()

def test_sankey_synchronization_n_and_n_minus_1(page: Page, generated_report):
    """
    Vérifie la synchronisation des filtres entre les graphiques (N et N-1).
    Scénario :
    1. L'utilisateur clique sur "Visa" dans le graphique 2025 (N).
    2. Le graphique 2024 (N-1) doit AUTOMATIQUEMENT se filtrer sur "Visa".
    """
    page.goto(generated_report)

    # Sélecteurs pour les deux graphiques
    charts = page.locator(".sub-chart")
    chart_n_minus_1 = charts.nth(0) # 2024
    chart_n = charts.nth(1)         # 2025

    # 1. Action : Clic sur Visa dans le graphique N (2025)
    # On vérifie d'abord que CB est visible en N-1 pour être sûr qu'il disparaitra
    expect(chart_n_minus_1.locator("svg rect").filter(has_text="CB")).to_be_visible()
    
    chart_n.locator("svg rect").filter(has_text="Visa").first.click()

    # 2. Vérification sur le graphique N-1 (2024)
    # Le badge de filtre doit apparaître AUSSI sur le graphique de gauche
    badge_n_minus_1 = chart_n_minus_1.locator("h4 span", has_text="Filtre: Visa")
    expect(badge_n_minus_1).to_be_visible()

    # Le noeud "CB" doit avoir disparu du graphique de gauche
    expect(chart_n_minus_1.locator("svg rect").filter(has_text="CB")).not_to_be_visible()


def test_export_csv_functionality(page: Page, generated_report):
    """
    Vérifie que le bouton d'export déclenche bien le téléchargement d'un fichier CSV.
    C'est un test critique pour les utilisateurs métier.
    """
    page.goto(generated_report)

    # Playwright gère les téléchargements via un context manager "expect_download"
    with page.expect_download() as download_info:
        # On clique sur le bouton d'export défini dans le HTML
        page.click("#btn-export")

    download = download_info.value

    # 1. Vérification du nom du fichier
    # Le JS génère un nom basé sur le titre : "qa_sankey_multi_level_dataset_0..."
    # On vérifie juste la présence de mots clés et l'extension
    filename = download.suggested_filename
    assert "qa_sankey" in filename.lower()
    assert filename.endswith(".csv")

    # 2. (Optionnel) Vérification du contenu du fichier téléchargé
    # On peut lire le fichier temporaire téléchargé
    path = download.path()
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
        # On vérifie que les headers CSV sont présents
        assert "mois_annee,scheme,tsp,amount" in content
        # On vérifie qu'une donnée connue est présente
        assert "Visa" in content

def test_sankey_data_accuracy_tooltip(page: Page, generated_report):
    """
    Vérifie que les données affichées sont correctes (Parsing CSV + Mapping + Formatage).
    Scénario :
    Le CSV contient : 2024-01, Visa, Worldline, 1000
    Le JS formate en fr-FR : "1 000" (ou "1 000" avec espace insécable)
    On vérifie que le tooltip du lien ou du noeud contient bien ce chiffre.
    """
    page.goto(generated_report)
    
    # On cible le graphique 2025 (Année N dans le setup enrichi)
    # Dans le CSV enrichi : 2025-01, Visa -> Worldline : 1500
    chart_container = page.locator(".sub-chart").last
    
    # On cherche le noeud "Visa"
    visa_node = chart_container.locator("svg rect").filter(has_text="Visa").first
    
    # On récupère le texte du tooltip (balise <title> interne au rect)
    # Note: text_content() récupère le texte même s'il n'est pas affiché (comportement SVG title)
    tooltip_text = visa_node.text_content()
    
    # Assertion : On vérifie la présence du nom ET de la valeur formatée
    assert "Visa" in tooltip_text
    
    # Regex pour gérer les espaces insécables (fr-FR) ou espaces simples
    # On cherche "1" suivi de n'importe quel espace ou rien, suivi de "500"
    # Car 1500 formaté peut être "1 500", "1\u202f500", etc.
    assert re.search(r"Total:\s*1[\s\u202f\u00a0]*500", tooltip_text), \
        f"Le montant 1500 n'a pas été trouvé correctement formaté dans : {tooltip_text}"


def test_responsive_layout(page: Page, generated_report):
    """
    Vérifie que le dashboard ne casse pas sur mobile.
    Le CSS a : min-width: 400px sur .sub-chart et flex-wrap.
    """
    page.goto(generated_report)
    
    # 1. Simulation Mobile (iPhone 12/13 Pro approx)
    page.set_viewport_size({"width": 390, "height": 844})
    
    # 2. Vérification que les graphiques s'empilent verticalement
    # (En desktop ils sont côte à côte si la place le permet)
    charts = page.locator(".sub-chart")
    
    # On vérifie juste qu'ils sont toujours visibles et ont une taille décente
    # (Le CSS impose min-width 400px, donc sur un écran de 390px, 
    # il y aura probablement du scroll horizontal ou un ajustement, 
    # mais l'élément ne doit pas être hidden ou height=0)
    chart_n = charts.last
    box = chart_n.bounding_box()
    
    expect(chart_n).to_be_visible()
    assert box['height'] > 300, "Le graphique est écrasé en hauteur sur mobile"
    assert box['width'] >= 300, "Le graphique est trop étroit sur mobile"