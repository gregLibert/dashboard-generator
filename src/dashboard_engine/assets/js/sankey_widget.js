const SANKEY_CONSTANTS = {
    SUB_CHART_MIN_HEIGHT_PX: 350,
    NODE_WIDTH: 15,
    NODE_PADDING: 15,
    LABEL_FONT_PX: 10,
};

function renderSankeySubChartTitleHtml(label, suffix, currentFilter) {
    let html = `<h4>${label}${suffix}`;
    if (currentFilter) {
        html += ` <span style="color:${UI_THEME.filterActive}; font-size:0.8em; cursor:pointer;" title="Cliquez pour retirer le filtre">
                    (Filtre: ${currentFilter} ✖)
                </span>`;
    }
    html += '</h4>';
    return html;
}

class SankeyWidget extends BaseWidget {

    initLayout() {
        this.colorScale = d3.scaleOrdinal(UI_THEME.schemeTableau10);
        super.initLayout();
    }

    update() {
        if (this.state.currentFilter === undefined) {
            this.state.currentFilter = null;
        }

        this.vizWrapper.innerHTML = '';
        const anchorYear = this.state.year;
        const yearsToShow = Utils.calendarYearsForYoYChart(anchorYear, this.state.yoy);

        yearsToShow.forEach((year) => {
            let data = this.getFilteredData(year);

            if (this.state.currentFilter) {
                const val = this.state.currentFilter;
                const mapping = this.config.mapping || {};
                const pathCols = mapping.path || [mapping.source, mapping.target];
                data = data.filter(row => pathCols.some(col => col && row[col] === val));
            }

            const container = document.createElement('div');
            container.className = 'sub-chart';

            const label = Utils.labelForPeriod(this.state.periodType, year, this.state.periodValue);
            const suffix = Utils.formatYoYChartTitleSuffix(this.state.yoy, year, anchorYear);

            const htmlTitle = renderSankeySubChartTitleHtml(label, suffix, this.state.currentFilter);

            container.innerHTML = `${htmlTitle}<div style="width:100%; min-height:${SANKEY_CONSTANTS.SUB_CHART_MIN_HEIGHT_PX}px;"></div>`;
            this.vizWrapper.appendChild(container);

            if (this.state.currentFilter) {
                container.querySelector('h4 span').addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.state.currentFilter = null;
                    this.update();
                });
            }

            if (data.length === 0) {
                container.querySelector('div').innerHTML = '<p class="hint" style="text-align:center; padding-top:100px;">Aucune donnée pour ce filtre.</p>';
                return;
            }

            this.drawSankey(container.querySelector('div'), data);
        });
    }

    /**
     * Build a node/link representation from flat path-based rows.
     * Pure computation to ease testing.
     */
    buildGraphFromData(data) {
        const mapping = this.config.mapping || {};
        const pathCols = mapping.path || [mapping.source, mapping.target];
        const valueCol = mapping.value;

        const nodesMap = new Map();
        const linksMap = new Map();

        const getNodeId = (name, level) => `${name}##${level}`;

        data.forEach(row => {
            const rawVal = row[valueCol];
            const val = +rawVal || 0;
            if (val <= 0) return;

            for (let i = 0; i < pathCols.length - 1; i++) {
                const srcKey = pathCols[i];
                const tgtKey = pathCols[i + 1];
                const srcName = srcKey && row[srcKey];
                const tgtName = tgtKey && row[tgtKey];

                if (!srcName || !tgtName) continue;

                const srcId = getNodeId(srcName, i);
                const tgtId = getNodeId(tgtName, i + 1);

                if (!nodesMap.has(srcId)) nodesMap.set(srcId, { id: srcId, name: srcName });
                if (!nodesMap.has(tgtId)) nodesMap.set(tgtId, { id: tgtId, name: tgtName });

                const linkKey = `${srcId}->${tgtId}`;
                if (!linksMap.has(linkKey)) {
                    linksMap.set(linkKey, { source: srcId, target: tgtId, value: 0 });
                }
                linksMap.get(linkKey).value += val;
            }
        });

        return {
            nodes: Array.from(nodesMap.values()),
            links: Array.from(linksMap.values())
        };
    }

    drawSankey(domNode, data) {
        const width = Utils.CHART_LAYOUT.DEFAULT_INNER_WIDTH;
        const height = Utils.CHART_LAYOUT.SANKEY_VIEW_HEIGHT;

        const { nodes, links } = this.buildGraphFromData(data);

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

        if (nodes.length === 0) return;

        const sankeyGen = sankey()
            .nodeId(d => d.id)
            .nodeWidth(SANKEY_CONSTANTS.NODE_WIDTH)
            .nodePadding(SANKEY_CONSTANTS.NODE_PADDING)
            .extent([[1, 5], [width - 1, height - 5]]);

        const graph = sankeyGen({ nodes, links });

        const levelTotals = new Map();
        graph.nodes.forEach(n => {
            const levelKey = Math.round(n.x0);
            levelTotals.set(levelKey, (levelTotals.get(levelKey) || 0) + n.value);
        });

        const getNameFromId = (id) => id.split('##')[0];

        svg.append("g")
            .attr("fill", "none")
            .attr("stroke-opacity", 0.5)
            .selectAll("path")
            .data(graph.links)
            .join("path")
            .attr("d", sankeyLinkHorizontal())
            .attr("stroke", d => this.colorScale(getNameFromId(d.source.id)))
            .attr("stroke-width", d => Math.max(1, d.width))
            .style("cursor", "pointer")
            .on("click", (e, d) => {
                e.stopPropagation();
                this.handleFilterChange(getNameFromId(d.source.id));
            })
            .append("title")
            .text(d => `${getNameFromId(d.source.id)} → ${getNameFromId(d.target.id)}\n${Utils.fmtNumber.format(d.value)}`);

        svg.append("g")
            .selectAll("rect")
            .data(graph.nodes)
            .join("rect")
            .attr("x", d => d.x0)
            .attr("y", d => d.y0)
            .attr("height", d => d.y1 - d.y0)
            .attr("width", d => d.x1 - d.x0)
            .attr("fill", d => this.colorScale(d.name))
            .attr("stroke", UI_THEME.black)
            .attr("stroke-opacity", 0.1)
            .style("cursor", "pointer")
            .on("click", (e, d) => {
                e.stopPropagation();
                this.handleFilterChange(d.name);
            })
            .append("title")
            .text(d => {
                const totalLevel = levelTotals.get(Math.round(d.x0)) || d.value;
                const pct = totalLevel > 0 ? ((d.value / totalLevel) * 100).toFixed(1) : 0;
                return `${d.name}\nTotal: ${Utils.fmtNumber.format(d.value)} (${pct}%)\n(Cliquez pour isoler)`;
            });

        svg.append("g")
            .attr("font-size", SANKEY_CONSTANTS.LABEL_FONT_PX)
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
