// ==========================================
// MAIN APP
// ==========================================

// Factory Registry
const WidgetRegistry = { 
    'sankey': SankeyWidget, 
    'evolution': EvolutionWidget,
    'sunburst': SunburstWidget,
    'horizon': HorizonWidget,
    'financial_sankey': FinancialSankeyWidget
};

async function init() {
    // 1. Config Loading
    const configRaw = document.getElementById('dashboard-config').textContent;
    const config = JSON.parse(configRaw);
    
    // 2. Dev Mode Detection
    const urlParams = new URLSearchParams(window.location.search);
    if(config.dev_mode && urlParams.has('dev')) {
        const devZone = document.getElementById('dev-zone');
        if (devZone) devZone.style.display = 'flex';
    }

    // 3. Dataset Parsing
    const datasets = [];
    let i = 0;
    while(document.getElementById(`dataset-${i}`)) {
        const rawContent = document.getElementById(`dataset-${i}`).textContent.trim();
        datasets.push(d3.csvParse(rawContent));
        i++;
    }
    window.GLOBAL_DATASETS = datasets;

    // 4. Export Button Logic
    const btnExport = document.getElementById('btn-export');
    if (btnExport) {
        btnExport.addEventListener('click', () => {
            const dateSuffix = config.generation_date || 'YYYYMMDD';
            const prefix = config.title ? config.title.replace(/[^a-z0-9]/gi, '_').toLowerCase() : 'dashboard';
            
            window.GLOBAL_DATASETS.forEach((data, idx) => {
                const headers = data.columns.join(",");
                const rows = data.map(row => data.columns.map(c => row[c]).join(",")).join("\n");
                const csvContent = headers + "\n" + rows;
                
                const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
                const link = document.createElement("a");
                link.href = URL.createObjectURL(blob);
                link.download = `${prefix}_dataset_${idx}_${dateSuffix}.csv`;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            });
        });
    }

    // 5. Widget Instantiation
    const container = document.getElementById('dashboard-container');
    
    config.widgets.forEach(wConfig => {
        const box = document.createElement('div');
        box.className = 'chart-box';
        container.appendChild(box);
        
        // MODIFICATION : On ne crée plus le HTML (header/h2) ici.
        // On passe la "boîte" vide directement au Widget. 
        // C'est le Widget qui va créer son header, son titre et son corps.
        
        const WidgetClass = WidgetRegistry[wConfig.type];
        
        if (WidgetClass) {
            // On passe 'box' au lieu de 'widgetBody'
            new WidgetClass(box, datasets[wConfig.datasetIndex || 0], wConfig);
        } else {
            console.error("Widget type unknown:", wConfig.type);
            box.innerHTML = `<p class="error">Type de widget inconnu: ${wConfig.type}</p>`;
        }
    });
}

// Start Application
init();