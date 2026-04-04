const MCR = require('monocart-coverage-reports');
const fs = require('fs');
const path = require('path');
const { fileURLToPath } = require('url');

const CONSTANTS = {
    COVERAGE_REPORT_NAME: 'Dashboard Engine Coverage',
    OUTPUT_DIR_COVERAGE: 'output/coverage-js',
    JS_COVERAGE_SUMMARY_FILENAME: 'js-coverage-summary.json',
    OUTPUT_DIR: 'output',
    VIRTUAL_JS_PATH: 'src/dashboard_engine_logic.js',
    VIRTUAL_SOURCE_FILTER_SUBSTRING: 'dashboard_engine_logic.js',
    ENCODING_UTF8: 'utf-8',
    FILE_URL_PREFIX: 'file:',
    HTML_EXTENSION: '.html',
    SCRIPT_MODULE_REGEX: /<script[^>]*type="module"[^>]*>([\s\S]*?)<\/script>/,
    REPORT_TYPES: ['v8', 'console-summary'],
};

const summaryPath = path.resolve(CONSTANTS.OUTPUT_DIR, CONSTANTS.JS_COVERAGE_SUMMARY_FILENAME);

const coverageOptions = {
    name: CONSTANTS.COVERAGE_REPORT_NAME,
    outputDir: CONSTANTS.OUTPUT_DIR_COVERAGE,
    reports: CONSTANTS.REPORT_TYPES,

    entryFilter: (entry) => entry.url.includes(CONSTANTS.VIRTUAL_SOURCE_FILTER_SUBSTRING),

    onEnd: (results) => {
        const summary = results.summary;
        const coveragePct = summary && summary.bytes ? summary.bytes.pct : 0;

        fs.writeFileSync(summaryPath, JSON.stringify({ pct: coveragePct }));
        console.log(`[JS Generation] Final coverage: ${coveragePct}%`);
    },
};

const rawDataPath = process.argv[2];
if (!rawDataPath || !fs.existsSync(rawDataPath)) {
    console.error('[JS Generation] Error: raw coverage file not found.');
    process.exit(1);
}

let reportData;
try {
    reportData = JSON.parse(fs.readFileSync(rawDataPath, CONSTANTS.ENCODING_UTF8));
} catch (err) {
    console.error('[JS Generation] Error: could not parse raw coverage JSON:', err.message);
    process.exit(1);
}

console.log('[JS Generation] Reading raw coverage data...');

let sharedSourceCode = null;
const mergedFunctions = [];

reportData.forEach((entry) => {
    if (
        entry.url &&
        entry.url.startsWith(CONSTANTS.FILE_URL_PREFIX) &&
        entry.url.endsWith(CONSTANTS.HTML_EXTENSION)
    ) {
        try {
            const filePath = fileURLToPath(entry.url);

            let fileContent = fs.readFileSync(filePath, CONSTANTS.ENCODING_UTF8);

            const match = CONSTANTS.SCRIPT_MODULE_REGEX.exec(fileContent);

            if (match) {
                let jsContent = match[1];

                jsContent = jsContent.replace(/\r\n/g, '\n');

                if (!sharedSourceCode) {
                    sharedSourceCode = jsContent;
                }

                entry.functions.forEach((func) => {
                    const validRanges = func.ranges.filter((r) => r.endOffset <= jsContent.length);

                    if (validRanges.length > 0) {
                        mergedFunctions.push({
                            functionName: func.functionName,
                            isBlockCoverage: func.isBlockCoverage,
                            ranges: validRanges,
                        });
                    }
                });
            }
        } catch (err) {
            console.error(`[JS Generation] Error processing file ${entry.url}:`, err.message);
            process.exit(1);
        }
    }
});

const finalEntries = [];
if (mergedFunctions.length > 0 && sharedSourceCode) {
    console.log(
        `[JS Generation] Merging ${mergedFunctions.length} trace(s) into virtual file.`
    );
    finalEntries.push({
        url: CONSTANTS.VIRTUAL_JS_PATH,
        source: sharedSourceCode,
        functions: mergedFunctions,
    });
} else {
    console.error(
        "[JS Generation] No JS data extracted. Check <script type='module'> tags in the HTML."
    );
    process.exit(1);
}

const mcr = MCR(coverageOptions);
mcr.add(finalEntries).then(() => mcr.generate());
