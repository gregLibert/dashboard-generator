// ==========================================
// SANKEY WIDGET (Interactif)
// ==========================================
class SankeyWidget extends BaseWidget {
    
    // Surcharge de update pour gérer le filtrage interactif
    update() {
        // Initialisation du filtre s'il n'existe pas encore dans l'état
        if (this.state.currentFilter === undefined) {
            this.state.currentFilter = null;
        }

        this.vizWrapper.innerHTML = '';
        const yearsToShow = this.state.yoy ? [this.state.year - 1, this.state.year] : [this.state.year];
        
        yearsToShow.forEach(year => {
            // 1. Filtrage Temporel (Année / Mois) via BaseWidget
            let data = this.getFilteredData(year);

            // 2. Filtrage Interactif (Drill-down)
            if (this.state.currentFilter) {
                const val = this.state.currentFilter;
                const { source, target } = this.config.mapping;
                
                // On ne garde que les lignes où la source OU la target correspond à la valeur cliquée
                data = data.filter(row => 
                    row[this.config.mapping[source]] === val ||
                    row[this.config.mapping[target]] === val ||
                    // Cas ou mapping direct (si le mapping contient directement le nom de colonne)
                    row[source] === val || 
                    row[target] === val ||
                    // Gestion robuste : on vérifie les valeurs mappées
                    Utils.getVal(row, 'source', this.config.mapping) === val ||
                    Utils.getVal(row, 'target', this.config.mapping) === val
                );
            }

            // Préparation du conteneur DOM
            const container = document.createElement('div');
            container.className = 'sub-chart';
            
            // Construction du titre avec indicateur de filtre
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
            
            // Gestion du clic sur le titre pour reset le filtre
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
        const { source, target, value } = this.config.mapping;
        
        const width = 800; 
        const height = 400;

        // --- Agrégation ---
        const agg = d3.rollup(data, 
            v => d3.sum(v, d => +d[value]), 
            d => Utils.getVal(d, 'source', this.config.mapping), 
            d => Utils.getVal(d, 'target', this.config.mapping)
        );

        const nodesSet = new Set();
        const links = [];
        
        for (const [src, targets] of agg) {
            if(!src) continue;
            nodesSet.add(src);
            for (const [tgt, val] of targets) {
                if(!tgt) continue;
                nodesSet.add(tgt);
                if (val > 0) links.push({ source: src, target: tgt, value: val });
            }
        }
        
        const nodes = Array.from(nodesSet).map(name => ({ name }));
        
        // --- Rendu SVG ---
        const svg = d3.select(domNode).append("svg")
            .attr("viewBox", [0, 0, width, height])
            .attr("preserveAspectRatio", "xMidYMid meet") 
            .style("width", "100%")
            .style("height", "100%");

        // Interaction : Clic sur le fond = Reset
        svg.on("click", (e) => {
            if (e.target.tagName === 'svg') {
                this.state.currentFilter = null;
                this.update();
            }
        });

        if(nodes.length === 0) return;

        const color = d3.scaleOrdinal(d3.schemeTableau10);
        const sankeyGen = sankey()
            .nodeId(d => d.name)
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
            .attr("stroke", d => color(d.source.name))
            .attr("stroke-width", d => Math.max(1, d.width))
            .style("cursor", "pointer")
            .on("click", (e, d) => {
                e.stopPropagation();
                // Comportement original : clic sur lien = filtre sur la source
                this.handleFilterChange(d.source.name);
            })
            .append("title")
            .text(d => `${d.source.name} → ${d.target.name}\n${Utils.fmtNumber.format(d.value)}`);

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

    // Gestionnaire centralisé du changement de filtre
    handleFilterChange(newValue) {
        if (this.state.currentFilter === newValue) {
            this.state.currentFilter = null; // Toggle off
        } else {
            this.state.currentFilter = newValue; // Toggle on
        }
        this.update();
    }
}