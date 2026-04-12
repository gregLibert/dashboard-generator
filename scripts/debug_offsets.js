const fs = require('fs');
const path = require('path');
const { fileURLToPath } = require('url');

const CONSTANTS = {
    ENCODING_UTF8: 'utf-8',
    FILE_URL_PREFIX: 'file:',
    HTML_EXTENSION: '.html',
    PREVIEW_SLICE_LEN: 50,
};

const rawDataPath = process.argv[2];

if (!rawDataPath || !fs.existsSync(rawDataPath)) {
    console.error('JSON file not found.');
    process.exit(1);
}

const reportData = JSON.parse(fs.readFileSync(rawDataPath));

const entry = reportData.find(
    (e) => e.url.startsWith(CONSTANTS.FILE_URL_PREFIX) && e.url.endsWith(CONSTANTS.HTML_EXTENSION)
);

if (!entry) {
    console.error('No HTML entry found in the JSON.');
    process.exit(1);
}

const filePath = fileURLToPath(entry.url);
console.log(`\nInspecting file: ${path.basename(filePath)}`);

let contentStr = fs.readFileSync(filePath, CONSTANTS.ENCODING_UTF8);

let contentBuf = fs.readFileSync(filePath);

console.log(`File size (disk / buffer): ${contentBuf.length} bytes`);
console.log(`File size (JS string):     ${contentStr.length} chars`);
console.log(`Difference (encoding / CRLF?): ${contentBuf.length - contentStr.length}`);

let testFunc = null;
for (const func of entry.functions) {
    if (func.functionName && func.functionName !== '' && func.ranges[0]) {
        testFunc = func;
        break;
    }
}

if (testFunc) {
    const start = testFunc.ranges[0].startOffset;
    const end = testFunc.ranges[0].endOffset;

    console.log(`\nTesting function: "${testFunc.functionName}"`);
    console.log(`V8 offsets:       [${start}, ${end}]`);

    const match = /<script[^>]*type="module"[^>]*>([\s\S]*?)<\/script>/.exec(contentStr);
    const jsContent = match[1];

    console.log('\n--- VRAI TEST 1 : V8 Offset sur JS brut (CRLF) ---');
    const extractJS_CRLF = jsContent.substring(start, Math.min(end, start + 50));
    console.log(`[Slice] : "${extractJS_CRLF.replace(/\n/g, '\\n').replace(/\r/g, '\\r')}..."`);

    console.log('\n--- VRAI TEST 2 : V8 Offset sur JS normalisé par le navigateur (LF) ---');
    const jsContentLF = jsContent.replace(/\r\n/g, '\n'); // LA CORRECTION EST ICI
    const extractJS_LF = jsContentLF.substring(start, Math.min(end, start + 50));
    console.log(`[Slice] : "${extractJS_LF.replace(/\n/g, '\\n').replace(/\r/g, '\\r')}..."`);
    
    
    console.log('\n--- Hypothesis 1: V8 uses byte offsets (buffer) ---');
    const extractBuf = contentBuf
        .subarray(start, Math.min(end, start + CONSTANTS.PREVIEW_SLICE_LEN))
        .toString(CONSTANTS.ENCODING_UTF8);
    console.log(`[Slice] : "${extractBuf.replace(/\n/g, '\\n').replace(/\r/g, '\\r')}..."`);

    console.log('\n--- Hypothesis 2: V8 uses string indices ---');
    const extractStr = contentStr.substring(start, Math.min(end, start + CONSTANTS.PREVIEW_SLICE_LEN));
    console.log(`[Slice] : "${extractStr.replace(/\n/g, '\\n').replace(/\r/g, '\\r')}..."`);

    console.log('\n--- Hypothesis 3: string + CRLF -> LF normalization ---');
    const contentLF = contentStr.replace(/\r\n/g, '\n');
    const extractLF = contentLF.substring(start, Math.min(end, start + CONSTANTS.PREVIEW_SLICE_LEN));
    console.log(`[Slice] : "${extractLF.replace(/\n/g, '\\n').replace(/\r/g, '\\r')}..."`);
} else {
    console.log('No named function found for the test.');
}
