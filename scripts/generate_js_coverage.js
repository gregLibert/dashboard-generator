const MCR = require('monocart-coverage-reports');
const fs = require('fs');
const path = require('path');

const coverageOptions = {
    name: 'JS Coverage Report',
    outputDir: 'output/coverage-js',
    reports: ['v8', 'console-summary'], // 'v8' génère le HTML visualisable
    
    // Nettoyage des fichiers externes (CDN, etc.)
    entryFilter: (entry) => entry.url.indexOf('node_modules') === -1 && entry.url.indexOf('cdn.jsdelivr') === -1,
    
    // Pour le badge: on peut extraire le summary ici si besoin, 
    // mais on va le laisser générer un json pour Python.
    onEnd: (results) => {
        // Sauvegarde un résumé simple pour que Python puisse générer le badge
        const summary = results.summary;
        // On prend le % de couverture des Bytes (standard V8) ou Statements
        const coveragePct = summary.bytes ? summary.bytes.pct : 0;
        fs.writeFileSync('output/js-coverage-summary.json', JSON.stringify({ pct: coveragePct }));
        console.log(`JS Coverage generated: ${coveragePct}%`);
    }
};

// On lit les données brutes passées par Python
const rawDataPath = process.argv[2];
if (fs.existsSync(rawDataPath)) {
    const reportData = JSON.parse(fs.readFileSync(rawDataPath));
    MCR(coverageOptions).add(reportData).then(report => report.generate());
}