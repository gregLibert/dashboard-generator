// ========================
// FINANCIAL SANKEY WIDGET 
// ========================

const PALETTE = {
    'input':  { node: '#546e7a', link: '#cfd8dc' }, // Gris structurel
    'profit': { node: '#2e7d32', link: '#a5d6a7' }, // Vert Succès
    'cost':   { node: '#c62828', link: '#ef9a9a' }, // Rouge Dépense
    'default':{ node: '#90a4ae', link: '#eceff1' }
};

class FinancialSankeyWidget extends BaseWidget {

    initLayout() {
        super.initLayout();
        this.container.classList.add('hide-ctrl-period-type'); 
        this.container.classList.add('hide-ctrl-period-value');
    }

    drawSankey(domNode, data) {
        const { source, target, value, type } = this.config.mapping;
        const width = 800;
        const height = 400;

        // 1. Node Type Mapping
        const nodeTypeMap = new Map();
        data.forEach(d => {
            if (d[target]) {
                const t = d[type] ? d[type].toLowerCase() : 'input';
                nodeTypeMap.set(d[target], t);
            }
        });

        // 2. Aggregation (FlatRollup)
        const aggregatedData = d3.flatRollup(
            data, 
            v => d3.sum(v, d => +d[value]), 
            d => d[source], 
            d => d[target]
        );

        // 3. Construction de la liste UNIQUE des noeuds
        const nodesSet = new Set();
        aggregatedData.forEach(([src, tgt, val]) => {
            nodesSet.add(src);
            nodesSet.add(tgt);
        });

        // Création du tableau de Noeuds
        const nodes = Array.from(nodesSet).map(name => ({ 
            name: name,
            type: nodeTypeMap.get(name) || 'input' 
        }));

        // --- ÉTAPE CRUCIALE (MANUAL INDEXING) ---
        // On crée une map pour savoir que "Revenue" est à l'index 1, "Cost" à l'index 4, etc.
        const nodeIndices = new Map(nodes.map((d, i) => [d.name, i]));

        // On construit les liens en utilisant ces INDEX (Integers) et non plus les Noms
        const graphLinks = aggregatedData.map(([src, tgt, val]) => ({
            source: nodeIndices.get(src), // Renvoie un entier (ex: 0)
            target: nodeIndices.get(tgt), // Renvoie un entier (ex: 1)
            value: val,
            targetType: nodeTypeMap.get(tgt) || 'input'
        }));

        // 4. SVG & Layout
        const svg = d3.select(domNode).append("svg")
            .attr("viewBox", [0, 0, width, height])
            .style("width", "100%")
            .style("height", "100%");

        const sankeyGenerator = sankey()
            // .nodeId() SUPPRIMÉ : On fournit déjà des index, plus besoin de mapping interne
            .nodeWidth(20)
            .nodePadding(20)
            .extent([[1, 5], [width - 1, height - 5]])
            .nodeAlign(sankeyJustify); 

        // Calcul du layout
        // D3 va modifier ces objets en place, mais comme 'source' et 'target' 
        // sont déjà des index valides, il ne plantera plus.
        const { nodes: graphNodes, links: finalLinks } = sankeyGenerator({
            nodes: nodes.map(d => Object.assign({}, d)),
            links: graphLinks.map(d => Object.assign({}, d))
        });

        // 5. Dessin des Liens
        svg.append("g")
            .attr("fill", "none")
            .selectAll("path")
            .data(finalLinks)
            .join("path")
            .attr("d", sankeyLinkHorizontal())
            .attr("stroke-width", d => Math.max(1, d.width))
            .attr("stroke", d => {
                const typeStyle = PALETTE[d.targetType] || PALETTE['default'];
                return typeStyle.link;
            })
            .attr("stroke-opacity", 0.6)
            .append("title")
            .text(d => `${d.source.name} → ${d.target.name}\n${Utils.fmtNumber.format(d.value)}`);

        // 6. Dessin des Noeuds
        svg.append("g")
            .selectAll("rect")
            .data(graphNodes)
            .join("rect")
            .attr("x", d => d.x0)
            .attr("y", d => d.y0)
            .attr("height", d => d.y1 - d.y0)
            .attr("width", d => d.x1 - d.x0)
            .attr("fill", d => {
                // Racine (pas de targetLinks entrant) -> Gris
                if (!d.targetLinks || d.targetLinks.length === 0) return PALETTE['input'].node;
                
                const typeStyle = PALETTE[d.type] || PALETTE['default'];
                return typeStyle.node;
            })
            .append("title")
            .text(d => `${d.name}\n${Utils.fmtNumber.format(d.value)}`);

        // 7. Labels
        svg.append("g")
            .style("font", "11px sans-serif")
            .style("font-weight", "600")
            .style("fill", "#333") 
            .selectAll("text")
            .data(graphNodes)
            .join("text")
            .attr("x", d => d.x0 < width / 2 ? d.x1 + 6 : d.x0 - 6)
            .attr("y", d => (d.y1 + d.y0) / 2)
            .attr("dy", "0.35em")
            .attr("text-anchor", d => d.x0 < width / 2 ? "start" : "end")
            .text(d => d.name)
            .append("tspan")
            .attr("fill-opacity", 0.6)
            .attr("font-weight", "normal")
            .text(d => ` ${Utils.fmtNumber.format(d.value)}`);
    }

    update() {
        this.vizWrapper.innerHTML = '';
        const yearsToShow = this.state.yoy ? [this.state.year - 1, this.state.year] : [this.state.year];

        yearsToShow.forEach(year => {
            const data = this.getFilteredData(year);
            const container = document.createElement('div');
            container.className = 'sub-chart';
            
            // Pour le label, on affiche juste l'année puisque Mois/Trimestre sont masqués
            container.innerHTML = `<h4>Année ${year}</h4><div class="sankey-container" style="width:100%;"></div>`;
            this.vizWrapper.appendChild(container);

            if(data.length === 0) {
                container.querySelector('.sankey-container').innerHTML = '<p class="hint">Aucune donnée</p>';
                return;
            }
            this.drawSankey(container.querySelector('.sankey-container'), data);
        });
    }
}