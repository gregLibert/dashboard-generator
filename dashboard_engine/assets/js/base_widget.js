// ==========================================
// BASE WIDGET
// ==========================================
class BaseWidget {
    constructor(container, rawData, config) {
        this.container = container;
        this.config = config;
        this.rawData = this.processData(rawData); 
        this.years = Array.from(new Set(this.rawData.map(d => d.year))).sort((a,b)=>a-b);
        
        // Initial State
        this.state = {
            periodType: 'mois', 
            periodValue: 1,     
            year: this.years[this.years.length - 1] || new Date().getFullYear(),
            yoy: true
        };

        this.initLayout();
        this.renderControls();
        this.update();
    }

    processData(data) {
        const dateCol = this.config.mapping.date; 
        return data.map(d => {
            const row = { ...d };
            if (dateCol && d[dateCol]) {
                const parts = d[dateCol].split('-');
                if(parts.length >= 2) {
                    row.year = +parts[0];
                    row.month = +parts[1];
                }
            }
            return row;
        }).filter(d => d.year && d.month);
    }

    initLayout() {
        // On nettoie le conteneur (la .chart-box)
        this.container.innerHTML = '';
        
        // 1. HEADER (Titre + Bouton Info)
        const header = document.createElement('div');
        header.className = 'chart-header';
        
        const titleRow = document.createElement('div');
        titleRow.style.display = 'flex';
        titleRow.style.alignItems = 'center';
        titleRow.style.justifyContent = 'space-between'; // Ecarte le titre et l'icône
        titleRow.style.width = '100%';
        
        const h2 = document.createElement('h2'); // h2 pour respecter ton style original
        h2.className = 'chart-title';
        h2.textContent = this.config.title;
        titleRow.appendChild(h2);

        // Ajout conditionnel du bouton Info
        if (this.config.description) {
            const infoIcon = document.createElement('span');
            infoIcon.className = 'info-icon';
            // SVG Icone 'i'
            infoIcon.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#1f77b4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:block"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>`;
            infoIcon.title = "Information sur la donnée";
            
            infoIcon.onclick = () => {
                const descBox = this.container.querySelector('.widget-description');
                if (descBox) {
                    const isHidden = getComputedStyle(descBox).display === 'none';
                    descBox.style.display = isHidden ? 'block' : 'none';
                }
            };
            titleRow.appendChild(infoIcon);
        }

        header.appendChild(titleRow);
        this.container.appendChild(header);

        // 2. DESCRIPTION BOX (Cachée par défaut)
        if (this.config.description) {
            const descDiv = document.createElement('div');
            descDiv.className = 'widget-description';
            descDiv.innerHTML = this.config.description;
            // On s'assure qu'elle est cachée au démarrage (géré par le CSS, mais sécurité ici)
            descDiv.style.display = 'none'; 
            this.container.appendChild(descDiv);
        }

        // 3. WIDGET BODY (Pour simuler l'ancienne structure si besoin de styling CSS spécifique)
        // On crée un wrapper global pour le contenu (Contrôles + Graphiques)
        const bodyWrapper = document.createElement('div');
        bodyWrapper.className = 'widget-body';
        
        this.controlsDiv = document.createElement('div');
        this.controlsDiv.className = 'controls';
        bodyWrapper.appendChild(this.controlsDiv);
        
        this.vizWrapper = document.createElement('div');
        this.vizWrapper.className = 'viz-wrapper';
        bodyWrapper.appendChild(this.vizWrapper);

        this.container.appendChild(bodyWrapper);
    }

    renderControls() {
        const c = this.controlsDiv;
        c.innerHTML = '';

        // 1. Période Type (Vue) -> classe pour masquage CSS
        const grpPeriod = document.createElement('div');
        grpPeriod.className = 'control-group ctrl-period-type';
        grpPeriod.innerHTML = `<label>Vue:</label>`;
        const selType = document.createElement('select');
        ['mois', 'trimestre', 'semestre', 'annee'].forEach(t => {
            const o = document.createElement('option');
            o.value = t; o.textContent = t.charAt(0).toUpperCase() + t.slice(1);
            if(t === this.state.periodType) o.selected = true;
            selType.appendChild(o);
        });
        selType.onchange = (e) => { 
            this.state.periodType = e.target.value; 
            this.refreshPeriodValueSelect(selVal); 
            this.update(); 
        };
        grpPeriod.appendChild(selType);
        c.appendChild(grpPeriod);

        // 2. Période Value (Janvier...) -> classe pour masquage CSS
        const grpVal = document.createElement('div');
        grpVal.className = 'control-group ctrl-period-value';
        const selVal = document.createElement('select');
        selVal.onchange = (e) => { this.state.periodValue = +e.target.value; this.update(); };
        grpVal.appendChild(selVal);
        c.appendChild(grpVal);
        this.refreshPeriodValueSelect(selVal); 

        // 3. Année
        const grpYear = document.createElement('div');
        grpYear.className = 'control-group';
        grpYear.innerHTML = `<label>Année:</label>`;
        const selYear = document.createElement('select');
        this.years.forEach(y => {
            const o = document.createElement('option');
            o.value = y; o.textContent = y;
            if(y === this.state.year) o.selected = true;
            selYear.appendChild(o);
        });
        selYear.onchange = (e) => { this.state.year = +e.target.value; this.update(); };
        grpYear.appendChild(selYear);
        c.appendChild(grpYear);

        // 4. YoY
        const grpYoy = document.createElement('div');
        grpYoy.className = 'control-group ctrl-yoy';
        grpYoy.innerHTML = `<label><input type="checkbox" ${this.state.yoy ? 'checked' : ''}> N-1</label>`;
        grpYoy.querySelector('input').onchange = (e) => { 
            this.state.yoy = e.target.checked; 
            this.update(); 
        };
        c.appendChild(grpYoy);
    }

    refreshPeriodValueSelect(sel) {
        sel.innerHTML = '';
        const type = this.state.periodType;
        
        if(type === 'annee') {
            sel.parentNode.style.display = 'none';
        } else {
            sel.parentNode.style.display = 'flex';
            let opts = [];
            if(type === 'mois') opts = Utils.moisFR.map((m,i) => ({v: i+1, l: m}));
            if(type === 'trimestre') opts = [1,2,3,4].map(v => ({v, l: `T${v}`}));
            if(type === 'semestre') opts = [1,2].map(v => ({v, l: `S${v}`}));
            
            opts.forEach(o => {
                const opt = document.createElement('option');
                opt.value = o.v; opt.textContent = o.l;
                if(o.v === this.state.periodValue) opt.selected = true;
                sel.appendChild(opt);
            });
            if(!opts.find(o => o.v === this.state.periodValue)) {
                 this.state.periodValue = opts[0].v;
            }
        }
    }

    getFilteredData(year) {
        const { periodType, periodValue } = this.state;
        return this.rawData.filter(d => {
            if(d.year !== year) return false;
            if(periodType === 'annee') return true;
            if(periodType === 'mois') return d.month === periodValue;
            if(periodType === 'trimestre') return Utils.getQuarter(d.month) === periodValue;
            if(periodType === 'semestre') return Utils.getSemester(d.month) === periodValue;
            return false;
        });
    }
}