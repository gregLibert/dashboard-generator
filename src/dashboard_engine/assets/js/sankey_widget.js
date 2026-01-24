// ==========================================
// SANKEY WIDGET (Multi-Level / Path-Based)
// ==========================================
class SankeyWidget extends BaseWidget {
    
    update() {
        if (this.state.currentFilter === undefined) {
            this.state.currentFilter = null;
        }

        this.vizWrapper.innerHTML = '';
        const yearsToShow = this.state.yoy ? [this.state.year - 1, this.state.year] : [this.state.year];
        
        yearsToShow.forEach(year => {
            let data = this.getFilteredData(year);

            // 1. Filtrage Interactif Multi-Colonnes
            if (this.state.currentFilter) {
                const val = this.state.currentFilter;
                // On récupère le chemin (path) ou on fallback sur source/target
                const pathCols = this.config.mapping.path || [this.config.mapping.source, this.config.mapping.target];
                
                // On garde la ligne si la valeur est présente dans n'importe quelle colonne du flux
                data = data.filter(row => pathCols.some(col => row[col] === val));
            }

            const container = document.createElement('div');
            container.className = 'sub-chart';
            
            const label = Utils.labelForPeriod(this.state.periodType, year, this.state.periodValue);
            const suffix = (this.state.yoy && year === this.state.year) ? ' (N)' : (this.state.yoy ? ' (N-1)' : '');
            
            let htmlTitle = `<h4>${label}${suffix}`;
            if (this.state.currentFilter) {
                htmlTitle += ` <span style="color:#b00020; font-size:0.8em; cursor:pointer;" title="Cliquez pour retirer le filtre">
                    (Filtre: ${this.state.currentFilter} ✖)
                </span>`;
            }
            htmlTitle += `</h4>`;

            container.innerHTML = `${htmlTitle}<div style="width:100%; min-height:350px;"></div>`;
            this.vizWrapper.appendChild(container);
            
            if(this.state.currentFilter) {
                container.querySelector('h4 span').addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.state.currentFilter = null;
                    this.update();
                });
            }
            
            if(data.length === 0) {
                container.querySelector('div').innerHTML = '<p class="hint" style="text-align:center; padding-top:100px;">Aucune donnée pour ce filtre.</p>';
                return;
            }

            this.drawSankey(container.querySelector('div'), data);
        });
    }

    drawSankey(domNode, data) {
        // Configuration du mapping
        const pathCols = this.config.mapping.path || [this.config.mapping.source, this.config.mapping.target];
        const valueCol = this.config.mapping.value;
        
        const width = 800; 
        const height = 400;

        // --- 1. Génération dynamique des Noeuds et Liens (Chainage) ---
        const nodesMap = new Map();
        const linksMap = new Map();

        // Helper pour garantir l'unicité des noms par niveau (évite les boucles D3)
        const getNodeId = (name, level) => `${name}##${level}`;
        const getNameFromId = (id) => id.split('##')[0];

        data.forEach(row => {
            const val = +row[valueCol] || 0;
            if (val <= 0) return;

            // On parcourt le "path" pour créer des paires Source -> Target
            for (let i = 0; i < pathCols.length - 1; i++) {
                const srcName = row[pathCols[i]];
                const tgtName = row[pathCols[i+1]];

                if (!srcName || !tgtName) continue;

                const srcId = getNodeId(srcName, i);
                const tgtId = getNodeId(tgtName, i + 1);

                // Enregistrement des Noeuds
                if (!nodesMap.has(srcId)) nodesMap.set(srcId, { id: srcId, name: srcName });
                if (!nodesMap.has(tgtId)) nodesMap.set(tgtId, { id: tgtId, name: tgtName });

                // Aggrégation des Liens
                const linkKey = `${srcId}->${tgtId}`;
                if (!linksMap.has(linkKey)) {
                    linksMap.set(linkKey, { source: srcId, target: tgtId, value: 0 });
                }
                linksMap.get(linkKey).value += val;
            }
        });
        
        const nodes = Array.from(nodesMap.values());
        const links = Array.from(linksMap.values());
        
        // --- 2. Rendu SVG (Conservation stricte de ton style) ---
        const svg = d3.select(domNode).append("svg")
            .attr("viewBox", [0, 0, width, height])
            .attr("preserveAspectRatio", "xMidYMid meet") 
            .style("width", "100%")
            .style("height", "100%");

        svg.on("click", (e) => {
            if (e.target.tagName === 'svg') {
                this.state.currentFilter = null;
                this.update();
            }
        });

        if(nodes.length === 0) return;

        const color = d3.scaleOrdinal(d3.schemeTableau10);
        const sankeyGen = sankey()
            .nodeId(d => d.id) // On utilise l'ID technique pour D3
            .nodeWidth(15)
            .nodePadding(15)
            .extent([[1, 5], [width - 1, height - 5]]);

        const graph = sankeyGen({ nodes, links });

        // --- Liens ---
        svg.append("g")
            .attr("fill", "none")
            .attr("stroke-opacity", 0.5)
            .selectAll("path")
            .data(graph.links)
            .join("path")
            .attr("d", sankeyLinkHorizontal())
            .attr("stroke", d => color(getNameFromId(d.source.id)))
            .attr("stroke-width", d => Math.max(1, d.width))
            .style("cursor", "pointer")
            .on("click", (e, d) => {
                e.stopPropagation();
                this.handleFilterChange(getNameFromId(d.source.id));
            })
            .append("title")
            .text(d => `${getNameFromId(d.source.id)} → ${getNameFromId(d.target.id)}\n${Utils.fmtNumber.format(d.value)}`);

        // --- Noeuds ---
        svg.append("g")
            .selectAll("rect")
            .data(graph.nodes)
            .join("rect")
            .attr("x", d => d.x0)
            .attr("y", d => d.y0)
            .attr("height", d => d.y1 - d.y0)
            .attr("width", d => d.x1 - d.x0)
            .attr("fill", d => color(d.name))
            .attr("stroke", "#000")
            .attr("stroke-opacity", 0.1)
            .style("cursor", "pointer")
            .on("click", (e, d) => {
                e.stopPropagation();
                this.handleFilterChange(d.name);
            })
            .append("title")
            .text(d => `${d.name}\nTotal: ${Utils.fmtNumber.format(d.value)}\n(Cliquez pour isoler)`);

        // --- Labels ---
        svg.append("g")
            .attr("font-size", 10)
            .attr("font-family", "sans-serif")
            .style("pointer-events", "none")
            .selectAll("text")
            .data(graph.nodes)
            .join("text")
            .attr("x", d => d.x0 < width / 2 ? d.x1 + 6 : d.x0 - 6)
            .attr("y", d => (d.y1 + d.y0) / 2)
            .attr("dy", "0.35em")
            .attr("text-anchor", d => d.x0 < width / 2 ? "start" : "end")
            .text(d => d.name);
    }

    handleFilterChange(newValue) {
        this.state.currentFilter = (this.state.currentFilter === newValue) ? null : newValue;
        this.update();
    }
}