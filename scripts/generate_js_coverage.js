const MCR = require('monocart-coverage-reports');
const fs = require('fs');
const path = require('path');
const { fileURLToPath } = require('url');

const coverageOptions = {
    name: 'Dashboard Engine Coverage',
    outputDir: 'output/coverage-js',
    reports: ['v8', 'console-summary'],
    
    // On ne veut voir que notre fichier JS virtuel propre
    entryFilter: (entry) => {
        return entry.url.includes('dashboard_engine_logic.js');
    },
    
    onEnd: (results) => {
        const summary = results.summary;
        const coveragePct = (summary && summary.bytes) ? summary.bytes.pct : 0;
        
        const summaryPath = path.resolve('output/js-coverage-summary.json');
        fs.writeFileSync(summaryPath, JSON.stringify({ pct: coveragePct }));
        console.log(`[JS Generation] Score Final : ${coveragePct}%`);
    }
};

const rawDataPath = process.argv[2];
if (!rawDataPath || !fs.existsSync(rawDataPath)) {
    console.error(`[JS Generation] Erreur: Fichier brut introuvable.`);
    process.exit(1);
}

console.log(`[JS Generation] Lecture des données brutes...`);
let reportData = JSON.parse(fs.readFileSync(rawDataPath));

const VIRTUAL_FILENAME = "src/dashboard_engine_logic.js";
let sharedSourceCode = null;
const mergedFunctions = [];

reportData.forEach(entry => {
    // On ne traite que les fichiers HTML locaux
    if (entry.url && entry.url.startsWith('file:') && entry.url.endsWith('.html')) {
        try {
            const filePath = fileURLToPath(entry.url);
            
            // 1. Lecture du fichier
            let fileContent = fs.readFileSync(filePath, 'utf-8');

            // 2. Extraction du contenu JS (Regex capture le groupe 1)
            const scriptTagRegex = /<script[^>]*type="module"[^>]*>([\s\S]*?)<\/script>/;
            const match = scriptTagRegex.exec(fileContent);

            if (match) {
                // match[1] est le contenu EXACT entre les balises
                let jsContent = match[1];

                // 3. NORMALISATION CRITIQUE (Windows \r\n -> Unix \n)
                // C'est ce qui corrige le delta de 12 caractères que tu as observé !
                jsContent = jsContent.replace(/\r\n/g, '\n');

                // On sauvegarde ce code comme référence pour le rapport
                if (!sharedSourceCode) {
                    sharedSourceCode = jsContent;
                }

                // 4. Pas de calcul savant d'offset !
                // V8 renvoie des coordonnées relatives au début de ce bloc.
                // Comme 'jsContent' commence aussi au début de ce bloc, ça matche direct.
                // On ajoute les fonctions telles quelles.
                
                entry.functions.forEach(func => {
                    // On ne garde que les fonctions qui semblent valides (nommées ou blocs)
                    // et qui rentrent dans la taille du script (sécurité)
                    const validRanges = func.ranges.filter(r => r.endOffset <= jsContent.length);
                    
                    if (validRanges.length > 0) {
                        mergedFunctions.push({
                            functionName: func.functionName,
                            isBlockCoverage: func.isBlockCoverage,
                            ranges: validRanges 
                        });
                    }
                });
            }
        } catch (err) {
            console.error(`[Warn] Erreur traitement fichier ${entry.url}:`, err.message);
        }
    }
});

// Création de l'entrée unique fusionnée
const finalEntries = [];
if (mergedFunctions.length > 0 && sharedSourceCode) {
    console.log(`[JS Generation] Fusion de ${mergedFunctions.length} traces sur le fichier virtuel.`);
    finalEntries.push({
        url: VIRTUAL_FILENAME,
        source: sharedSourceCode,
        functions: mergedFunctions
    });
} else {
    console.error("❌ Aucune donnée JS extraite. Vérifiez les balises <script type='module'>.");
}

const mcr = MCR(coverageOptions);
mcr.add(finalEntries).then(() => mcr.generate());