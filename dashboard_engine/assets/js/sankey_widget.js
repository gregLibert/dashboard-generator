// ==========================================
// SANKEY WIDGET (Multi-Level Path)
// ==========================================
class SankeyWidget extends BaseWidget {

    update() {
        if (this.state.currentFilter === undefined) {
            this.state.currentFilter = null;
        }

        this.vizWrapper.innerHTML = '';
        const yearsToShow = this.state.yoy ? [this.state.year - 1, this.state.year] : [this.state.year];

        yearsToShow.forEach(year => {
            // 1. Filtrage Temporel
            let data = this.getFilteredData(year);

            // 2. Filtrage Interactif (Drill-down)
            if (this.state.currentFilter) {
                const filterVal = this.state.currentFilter;
                // On récupère la liste des colonnes impliquées
                const pathCols = this.config.mapping.path || [this.config.mapping.source, this.config.mapping.target];

                // On garde la ligne si la valeur cherchée apparaît dans N'IMPORTE QUELLE colonne du path
                data = data.filter(row => {
                    return pathCols.some(col => row[col] === filterVal);
                });
            }

            const container = document.createElement('div');
            container.className = 'sub-chart';
            
            // Titre & Reset Filtre
            const label = Utils.labelForPeriod(this.state.periodType, year, this.state.periodValue);
            const suffix = (this.state.yoy && year === this.state.year) ? ' (N)' : (this.state.yoy ? ' (N-1)' : '');
            
            let htmlTitle = `<h4>${label}${suffix}`;
            if (this.state.currentFilter) {
                htmlTitle += ` <span style="color:#b00020; font-size:0.8em; cursor:pointer;" title="Retirer le filtre">
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
                container.querySelector('div').innerHTML = '<p class="hint" style="text-align:center; padding-top:100px;">Aucune donnée.</p>';
                return;
            }

            this.drawSankey(container.querySelector('div'), data);
        });
    }

    drawSankey(domNode, data) {
        // Support rétro-compatible ou mode liste
        const pathCols = this.config.mapping.path || [this.config.mapping.source, this.config.mapping.target];
        const valCol = this.config.mapping.value;

        const width = domNode.clientWidth || 800;
        const height = 400;

        // --- 1. Construction des Liens et Noeuds ---
        const linksMap = new Map(); // Key: "SourceID->TargetID", Value: sum
        const nodesMap = new Map(); // Key: "ID", Value: {name, layer}

        // Helper pour générer un ID unique par niveau (évite les cycles si "Visa" est à la fois en col 1 et 2)
        const getNodeId = (val, colIndex) => `${val}##${colIndex}`;
        const getNodeName = (id) => id.split('##')[0];

        data.forEach(row => {
            const val = +row[valCol] || 0;
            if (val <= 0) return;

            // On boucle sur le chemin: Col 0 -> Col 1, puis Col 1 -> Col 2...
            for (let i = 0; i < pathCols.length - 1; i++) {
                const srcRaw = row[pathCols[i]];
                const tgtRaw = row[pathCols[i+1]];

                if (!srcRaw || !tgtRaw) continue;

                const srcId = getNodeId(srcRaw, i);
                const tgtId = getNodeId(tgtRaw, i + 1);

                // Enregistrement des noeuds
                if (!nodesMap.has(srcId)) nodesMap.set(srcId, { id: srcId, name: srcRaw });
                if (!nodesMap.has(tgtId)) nodesMap.set(tgtId, { id: tgtId, name: tgtRaw });

                // Aggrégation du lien
                const linkKey = `${srcId}->${tgtId}`;
                const current = linksMap.get(linkKey) || { source: srcId, target: tgtId, value: 0 };
                current.value += val;
                linksMap.set(linkKey, current);
            }
        });

        const nodes = Array.from(nodesMap.values());
        const links = Array.from(linksMap.values());

        if (nodes.length === 0) return;

        // --- 2. Rendu SVG ---
        const svg = d3.select(domNode).append("svg")
            .attr("viewBox", [0, 0, width, height])
            .style("width", "100%")
            .style("height", "auto");

        // Click background = Reset
        svg.on("click", (e) => {
            if (e.target.tagName === 'svg') {
                this.state.currentFilter = null;
                this.update();
            }
        });

        const color = d3.scaleOrdinal(d3.schemeTableau10);
        
        const sankeyGen = sankey()
            .nodeId(d => d.id) // Important: on utilise l'ID unique (avec ##) pour la topo
            .nodeWidth(15)
            .nodePadding(15)
            .extent([[1, 5], [width - 1, height - 5]]);

        // D3 modifie les objets links/nodes en place
        const graph = sankeyGen({ nodes, links });

        // --- Dessin des Liens ---
        svg.append("g")
            .attr("fill", "none")
            .attr("stroke-opacity", 0.4)
            .selectAll("path")
            .data(graph.links)
            .join("path")
            .attr("d", sankeyLinkHorizontal())
            .attr("stroke", d => color(d.source.name)) // Couleur basée sur le nom propre
            .attr("stroke-width", d => Math.max(1, d.width))
            .style("transition", "stroke-opacity 0.3s")
            .style("cursor", "pointer")
            .on("mouseover", function() { d3.select(this).attr("stroke-opacity", 0.7); })
            .on("mouseout", function() { d3.select(this).attr("stroke-opacity", 0.4); })
            .on("click", (e, d) => {
                e.stopPropagation();
                // On filtre sur le nom réel de la source (ex: "Visa")
                this.handleFilterChange(d.source.name); 
            })
            .append("title")
            .text(d => `${d.source.name} → ${d.target.name}\n${Utils.fmtNumber.format(d.value)}`);

        // --- Dessin des Noeuds ---
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
            .text(d => `${d.name}\nTotal: ${Utils.fmtNumber.format(d.value)}`);

        // --- Labels (Texte) ---
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
            .text(d => d.name) // On affiche le nom propre ("Visa"), pas l'ID ("Visa##0")
            .attr("font-weight", "bold")
            .attr("fill", "#333");
    }

    handleFilterChange(newValue) {
        if (this.state.currentFilter === newValue) {
            this.state.currentFilter = null;
        } else {
            this.state.currentFilter = newValue;
        }
        this.update();
    }
}