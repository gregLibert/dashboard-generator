const UI_THEME = {
    primary: '#1f77b4',
    filterActive: '#b00020',
    positiveDelta: '#2e7d32',
    negativeDelta: '#c62828',
    black: '#000',
    white: '#fff',
    textMuted: '#333',
    emptyStatePanelBg: '#f9f9f9',
    emptyStateMutedText: '#999',
    axisDomain: '#ddd',
    gridMajor: '#eee',
    legendBackdrop: 'rgba(255, 255, 255, 0.9)',
    defaultHorizonBlue: '#08519c',
    financialSankey: {
        input: { node: '#546e7a', link: '#cfd8dc' },
        profit: { node: '#2e7d32', link: '#a5d6a7' },
        cost: { node: '#c62828', link: '#ef9a9a' },
        default: { node: '#90a4ae', link: '#eceff1' },
    },
    schemeTableau10: d3.schemeTableau10,
    schemeCategory10: d3.schemeCategory10,
    schemePaired: d3.schemePaired,
    heatmapInterpolator: d3.interpolateInferno,
    radialSeriesStroke: '#4682b4',
};

const APP_CONSTANTS = {
    CONFIG_ELEMENT_ID: 'dashboard-config',
    DASHBOARD_CONTAINER_ID: 'dashboard-container',
    DEV_ZONE_ID: 'dev-zone',
    EXPORT_BUTTON_ID: 'btn-export',
    DATASET_ID_PREFIX: 'dataset-',
    CSV_MIME: 'text/csv;charset=utf-8;',
    DEFAULT_EXPORT_DATE: 'YYYYMMDD',
    DEFAULT_EXPORT_PREFIX: 'dashboard',
    WIDGET_CRASH_EVENT: 'WidgetCrash',
};

const WidgetRegistry = {
    'sankey': SankeyWidget,
    'evolution': EvolutionWidget,
    'sunburst': SunburstWidget,
    'horizon': HorizonWidget,
    'financial_sankey': FinancialSankeyWidget,
    'nested_treemap': NestedTreemapWidget,
    'stacked_area': StackedAreaWidget,
    'bubble': BubbleWidget,
    'heatmap': HeatmapWidget,
    'radial_area': RadialAreaWidget,
};

function safeParseJSON(text) {
    try {
        return JSON.parse(text);
    } catch (e) {
        console.error("Unable to parse dashboard configuration JSON:", e);
        throw e;
    }
}

function validateWidgetConfig(config) {
    if (!Array.isArray(config.widgets)) {
        console.error("Config must contain a 'widgets' array.");
        return [];
    }
    return config.widgets.filter(wConfig => {
        if (!wConfig || typeof wConfig.type !== 'string') {
            console.error("Invalid widget configuration (missing type):", wConfig);
            return false;
        }
        if (WidgetRegistry[wConfig.type] === undefined) {
            console.error("Widget type unknown:", wConfig.type);
            return false;
        }
        return true;
    });
}

async function init() {
    const configNode = document.getElementById(APP_CONSTANTS.CONFIG_ELEMENT_ID);
    if (!configNode) {
        console.error("Missing #dashboard-config element in DOM.");
        return;
    }
    const config = safeParseJSON(configNode.textContent);

    const urlParams = new URLSearchParams(window.location.search);
    if (config.dev_mode && urlParams.has('dev')) {
        const devZone = document.getElementById(APP_CONSTANTS.DEV_ZONE_ID);
        if (devZone) devZone.style.display = 'flex';
    }

    const datasets = [];
    let i = 0;
    while (document.getElementById(`${APP_CONSTANTS.DATASET_ID_PREFIX}${i}`)) {
        const rawContent = document.getElementById(`${APP_CONSTANTS.DATASET_ID_PREFIX}${i}`).textContent.trim();
        datasets.push(d3.csvParse(rawContent));
        i++;
    }
    window.GLOBAL_DATASETS = datasets;

    const btnExport = document.getElementById(APP_CONSTANTS.EXPORT_BUTTON_ID);
    if (btnExport) {
        btnExport.addEventListener('click', () => {
            const dateSuffix = config.generation_date || APP_CONSTANTS.DEFAULT_EXPORT_DATE;
            const prefix = config.title
                ? config.title.replace(/[^a-z0-9]/gi, '_').toLowerCase()
                : APP_CONSTANTS.DEFAULT_EXPORT_PREFIX;

            window.GLOBAL_DATASETS.forEach((data, idx) => {
                const headers = data.columns.join(",");
                const rows = data.map(row => data.columns.map(c => row[c]).join(",")).join("\n");
                const csvContent = headers + "\n" + rows;

                const blob = new Blob([csvContent], { type: APP_CONSTANTS.CSV_MIME });
                const link = document.createElement("a");
                link.href = URL.createObjectURL(blob);
                link.download = `${prefix}_dataset_${idx}_${dateSuffix}.csv`;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            });
        });
    }

    const container = document.getElementById(APP_CONSTANTS.DASHBOARD_CONTAINER_ID);
    if (!container) {
        console.error("Missing #dashboard-container element in DOM.");
        return;
    }

    const validWidgets = validateWidgetConfig(config);

    validWidgets.forEach(wConfig => {
        const box = document.createElement('div');
        box.className = 'chart-box';
        container.appendChild(box);

        const WidgetClass = WidgetRegistry[wConfig.type];
        const datasetIndex = wConfig.datasetIndex || 0;
        const dataset = window.GLOBAL_DATASETS[datasetIndex] || [];

        try {
            new WidgetClass(box, dataset, wConfig);
        } catch (e) {
            console.error("Failed to initialize widget:", wConfig.type, e);
            box.innerHTML = `<p class="error">Erreur lors du rendu du widget: ${wConfig.type}</p>`;
            document.dispatchEvent(new CustomEvent(APP_CONSTANTS.WIDGET_CRASH_EVENT, {
                detail: { type: wConfig.type, error: e },
            }));
        }
    });
}

window.UI_THEME = UI_THEME;

init();
