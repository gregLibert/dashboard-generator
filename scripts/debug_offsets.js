const fs = require('fs');
const path = require('path');
const { fileURLToPath } = require('url');

const rawDataPath = process.argv[2]; // ex: output/raw_v8_coverage.json

if (!rawDataPath || !fs.existsSync(rawDataPath)) {
    console.error("❌ Fichier JSON introuvable.");
    process.exit(1);
}

const reportData = JSON.parse(fs.readFileSync(rawDataPath));

// On cherche une entrée HTML pertinente
const entry = reportData.find(e => e.url.startsWith('file:') && e.url.endsWith('.html'));

if (!entry) {
    console.error("❌ Aucune entrée HTML trouvée dans le JSON.");
    process.exit(1);
}

const filePath = fileURLToPath(entry.url);
console.log(`\n🔍 Analyse du fichier : ${path.basename(filePath)}`);

// LECTURE 1 : Mode TEXTE (String)
// C'est ce que font la plupart des outils
let contentStr = fs.readFileSync(filePath, 'utf-8');

// LECTURE 2 : Mode BUFFER (Bytes)
// C'est ce que voit Chrome (V8) généralement
let contentBuf = fs.readFileSync(filePath);

console.log(`📏 Taille Fichier (Disque/Buffer) : ${contentBuf.length} bytes`);
console.log(`📏 Taille Fichier (String JS)     : ${contentStr.length} chars`);
console.log(`⚠️ Différence (Accents/CRLF ?)    : ${contentBuf.length - contentStr.length}`);

// On cherche une fonction nommée (pas une anonyme/vide) pour tester
// On filtre les fonctions qui ont un nom et une taille > 0
let testFunc = null;
for (const func of entry.functions) {
    if (func.functionName && func.functionName !== '' && func.ranges[0]) {
        testFunc = func;
        break; // On prend la première qu'on trouve (souvent une classe ou une méthode)
    }
}

if (testFunc) {
    const start = testFunc.ranges[0].startOffset;
    const end = testFunc.ranges[0].endOffset;
    
    console.log(`\n🎯 Test sur la fonction : "${testFunc.functionName}"`);
    console.log(`📍 Coordonnées V8       : [${start}, ${end}]`);

    console.log("\n--- HYPOTHÈSE 1 : Chrome parle en BYTES (Buffer) ---");
    // On coupe directement dans les octets
    const extractBuf = contentBuf.subarray(start, Math.min(end, start + 50)).toString('utf-8');
    console.log(`[Extrait] : "${extractBuf.replace(/\n/g, '\\n').replace(/\r/g, '\\r')}..."`);

    console.log("\n--- HYPOTHÈSE 2 : Chrome parle en INDEX (String) ---");
    // On coupe dans la chaine de caractères
    const extractStr = contentStr.substring(start, Math.min(end, start + 50));
    console.log(`[Extrait] : "${extractStr.replace(/\n/g, '\\n').replace(/\r/g, '\\r')}..."`);

    console.log("\n--- HYPOTHÈSE 3 : String + Normalisation CRLF -> LF ---");
    const contentLF = contentStr.replace(/\r\n/g, '\n');
    const extractLF = contentLF.substring(start, Math.min(end, start + 50));
    console.log(`[Extrait] : "${extractLF.replace(/\n/g, '\\n').replace(/\r/g, '\\r')}..."`);

} else {
    console.log("❌ Aucune fonction nommée trouvée pour le test.");
}