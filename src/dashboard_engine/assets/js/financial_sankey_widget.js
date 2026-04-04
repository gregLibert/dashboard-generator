const FIN_SANKEY_CONSTANTS = {
    VIEW_WIDTH: 800,
    VIEW_HEIGHT: 400,
    NODE_WIDTH: 20,
    NODE_PADDING: 20,
};

class FinancialSankeyWidget extends BaseWidget {

    initLayout() {
        super.initLayout();
        this.container.classList.add('hide-ctrl-period-type');
        this.container.classList.add('hide-ctrl-period-value');
    }

    /**
     * Build nodes and links from the flat financial data.
     * Pure computation: suitable for table-driven unit tests.
     */
    buildGraphFromData(data) {
        const { source, target, value, type } = this.config.mapping;

        const nodeTypeMap = new Map();
        data.forEach(d => {
            const targetName = d[target];
            if (targetName) {
                const t = d[type] ? String(d[type]).toLowerCase() : 'input';
                nodeTypeMap.set(targetName, t);
            }
        });

        const aggregatedData = d3.flatRollup(
            data,
            v => d3.sum(v, d => +d[value]),
            d => d[source],
            d => d[target]
        );

        const nodesSet = new Set();
        aggregatedData.forEach(([src, tgt]) => {
            nodesSet.add(src);
            nodesSet.add(tgt);
        });

        const nodes = Array.from(nodesSet).map(name => ({
            name,
            type: nodeTypeMap.get(name) || 'input'
        }));

        const nodeIndices = new Map(nodes.map((d, i) => [d.name, i]));

        const links = aggregatedData.map(([src, tgt, val]) => ({
            source: nodeIndices.get(src),
            target: nodeIndices.get(tgt),
            value: val,
            targetType: nodeTypeMap.get(tgt) || 'input'
        }));

        return { nodes, links };
    }

    drawSankey(domNode, data) {
        const width = FIN_SANKEY_CONSTANTS.VIEW_WIDTH;
        const height = FIN_SANKEY_CONSTANTS.VIEW_HEIGHT;

        const { nodes, links } = this.buildGraphFromData(data);
        const palette = UI_THEME.financialSankey;

        const svg = d3.select(domNode).append("svg")
            .attr("viewBox", [0, 0, width, height])
            .style("width", "100%")
            .style("height", "100%");

        const sankeyGenerator = sankey()
            .nodeWidth(FIN_SANKEY_CONSTANTS.NODE_WIDTH)
            .nodePadding(FIN_SANKEY_CONSTANTS.NODE_PADDING)
            .extent([[1, 5], [width - 1, height - 5]])
            .nodeAlign(sankeyJustify);

        const { nodes: graphNodes, links: finalLinks } = sankeyGenerator({
            nodes: nodes.map(d => Object.assign({}, d)),
            links: links.map(d => Object.assign({}, d))
        });

        svg.append("g")
            .attr("fill", "none")
            .selectAll("path")
            .data(finalLinks)
            .join("path")
            .attr("d", sankeyLinkHorizontal())
            .attr("stroke-width", d => Math.max(1, d.width))
            .attr("stroke", d => {
                const typeStyle = palette[d.targetType] || palette.default;
                return typeStyle.link;
            })
            .attr("stroke-opacity", 0.6)
            .append("title")
            .text(d => `${d.source.name} → ${d.target.name}\n${Utils.fmtNumber.format(d.value)}`);

        svg.append("g")
            .selectAll("rect")
            .data(graphNodes)
            .join("rect")
            .attr("x", d => d.x0)
            .attr("y", d => d.y0)
            .attr("height", d => d.y1 - d.y0)
            .attr("width", d => d.x1 - d.x0)
            .attr("fill", d => {
                if (!d.targetLinks || d.targetLinks.length === 0) return palette.input.node;

                const typeStyle = palette[d.type] || palette.default;
                return typeStyle.node;
            })
            .append("title")
            .text(d => `${d.name}\n${Utils.fmtNumber.format(d.value)}`);

        svg.append("g")
            .style("font", "11px sans-serif")
            .style("font-weight", "600")
            .style("fill", UI_THEME.textMuted)
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

            container.innerHTML = `<h4>Année ${year}</h4><div class="sankey-container" style="width:100%;"></div>`;
            this.vizWrapper.appendChild(container);

            if (data.length === 0) {
                container.querySelector('.sankey-container').innerHTML = '<p class="hint">Aucune donnée</p>';
                return;
            }
            this.drawSankey(container.querySelector('.sankey-container'), data);
        });
    }
}