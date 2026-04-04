const TREEMAP_CONSTANTS = {
    PADDING_OUTER: 3,
    PADDING_INNER: 1,
};

function renderTreemapSubChartShellHtml(label, suffix) {
    return `
                <h4 style="text-align:center; margin: 0 0 10px 0; min-height: 20px; cursor: pointer;" title="Click to zoom out">${label}${suffix}</h4>
                <div class="treemap-container" style="flex: 1; min-height: 0; position:relative; overflow:hidden;"></div>
            `;
}

function treemapMarkCompactNodes(renderRoot, threshold) {
    renderRoot.each((d) => {
        if (d.children && (d.y1 - d.y0) < threshold) {
            d.isCompact = true;
        }
    });
}

class NestedTreemapWidget extends BaseWidget {

    initLayout() {
        super.initLayout();

        this.breadcrumbDiv = document.createElement('div');
        this.breadcrumbDiv.className = 'breadcrumbs';
        this.breadcrumbDiv.innerHTML = '<span class="crumb active">Total</span>';
        this.vizWrapper.parentNode.insertBefore(this.breadcrumbDiv, this.vizWrapper);

        this.vizWrapper.style.display = 'flex';
        this.vizWrapper.style.width = '100%';
        this.vizWrapper.style.gap = '20px';
        this.vizWrapper.style.alignItems = 'flex-start';

        this.vizWrapper.addEventListener('click', (event) => {
            if (['INPUT', 'SELECT', 'BUTTON', 'OPTION'].includes(event.target.tagName)) return;
            this.broadcastZoom(['Total']);
        });

        this.colorScale = d3.scaleOrdinal(UI_THEME.schemeCategory10);
        this.charts = {};
    }

    update() {
        this.vizWrapper.innerHTML = '';
        this.charts = {};
        this.updateBreadcrumbs(['Total']);

        const anchorYear = this.state.year;
        const yearsToShow = Utils.calendarYearsForYoYChart(anchorYear, this.state.yoy);

        yearsToShow.forEach((year) => {
            const rawData = this.getFilteredData(year);
            const container = document.createElement('div');
            container.className = 'sub-chart';

            container.style.flex = '1';
            container.style.display = 'flex';
            container.style.flexDirection = 'column';
            container.style.minWidth = '0';
            container.style.height = '100%';

            const label = Utils.labelForPeriod(this.state.periodType, year, this.state.periodValue);
            const suffix = Utils.formatYoYChartTitleSuffix(this.state.yoy, year, anchorYear);

            container.innerHTML = renderTreemapSubChartShellHtml(label, suffix);

            this.vizWrapper.appendChild(container);

            const domNode = container.querySelector('.treemap-container');

            if (rawData.length === 0) {
                this.showNoData(domNode);
                return;
            }

            const fullRoot = this.buildHierarchy(rawData);

            this.charts[year] = {
                fullRoot,
                domNode,
                currentPath: ['Total'],
            };

            this.renderChart(year, fullRoot, ['Total']);
        });
    }

    showNoData(domNode) {
        domNode.innerHTML =
            `<div style="height:100%; display:flex; align-items:center; justify-content:center; background:${UI_THEME.emptyStatePanelBg}; color:${UI_THEME.emptyStateMutedText}; font-style:italic;">No data available for this selection</div>`;
    }

    /**
     * Build hierarchical data for the treemap based on the mapping configuration.
     * Pure computation to facilitate table-driven testing.
     */
    buildHierarchy(rawData) {
        const { hierarchy: hierarchyCols, value } = this.config.mapping;
        const rolls = d3.rollup(
            rawData,
            (v) => d3.sum(v, (d) => +d[value]),
            ...hierarchyCols.map((col) => (d) => d[col] || 'N/A')
        );

        const makeTree = (name, val) => {
            if (val instanceof Map) return { name, children: Array.from(val, ([n, v]) => makeTree(n, v)) };
            return { name, value: val };
        };

        return d3.hierarchy(makeTree('Total', rolls))
            .sum((d) => d.value)
            .sort((a, b) => b.value - a.value);
    }

    _treemapBuildRenderRoot(sourceNode) {
        return d3.hierarchy(sourceNode.data)
            .sum((d) => d.value)
            .sort((a, b) => b.value - a.value);
    }

    _treemapApplyPaddingLayout(renderRoot, width, height) {
        const L = Utils.CHART_LAYOUT;
        const treemap = d3.treemap()
            .size([width, height])
            .paddingOuter(TREEMAP_CONSTANTS.PADDING_OUTER)
            .paddingInner(TREEMAP_CONSTANTS.PADDING_INNER)
            .round(true);

        treemap.paddingTop((d) => (d === renderRoot ? 0 : L.TREEMAP_HEADER_PADDING))(renderRoot);

        treemapMarkCompactNodes(renderRoot, L.TREEMAP_COMPACT_ROW_THRESHOLD);

        treemap.paddingTop((d) => {
            if (d === renderRoot) return 0;
            return d.isCompact ? 0 : L.TREEMAP_HEADER_PADDING;
        })(renderRoot);
    }

    _treemapAppendClipSvg(domNode, width, height, uid) {
        const svg = d3.select(domNode).append('svg')
            .attr('viewBox', [0, 0, width, height])
            .style('font', '10px sans-serif')
            .style('width', '100%')
            .style('height', '100%')
            .style('display', 'block');

        svg.append('defs')
            .append('clipPath')
            .attr('id', `${uid}-clip`)
            .append('rect')
            .attr('width', width)
            .attr('height', height);

        const group = svg.append('g')
            .attr('clip-path', `url(#${uid}-clip)`);

        return { svg, group };
    }

    _treemapAppendCells(group, renderRoot, breadcrumbPath, uid, formatNum) {
        const cell = group.selectAll('g')
            .data(renderRoot.descendants())
            .join('g')
            .attr('transform', (d) => `translate(${d.x0},${d.y0})`);

        cell.append('rect')
            .attr('id', (d, i) => (d.leafUid = `leaf-${uid}-${i}`))
            .attr('width', (d) => Math.max(0, d.x1 - d.x0))
            .attr('height', (d) => Math.max(0, d.y1 - d.y0))
            .attr('fill', (d) => {
                if (d.depth === 0) return 'none';
                return this.colorScale(d.data.name);
            })
            .attr('fill-opacity', (d) => (d.children ? 0.6 : 0.8))
            .attr('stroke', UI_THEME.white)
            .style('cursor', (d) => (d.children ? 'pointer' : 'default'))
            .on('click', (e, d) => {
                if (!d.children) return;
                e.stopPropagation();
                const localPath = d.ancestors().reverse().map((n) => n.data.name).slice(1);
                const fullPath = breadcrumbPath.concat(localPath);
                this.broadcastZoom(fullPath);
            });

        cell.append('clipPath')
            .attr('id', (d) => (d.clipUid = `clip-${d.leafUid}`))
            .append('use')
            .attr('xlink:href', (d) => `#${d.leafUid}`);

        cell.append('text')
            .attr('clip-path', (d) => `url(#${d.clipUid})`)
            .attr('x', 4)
            .attr('y', 12)
            .style('pointer-events', 'none')
            .selectAll('tspan')
            .data((d) => {
                if ((d.x1 - d.x0) < 30 || (d.y1 - d.y0) < 15) return [];
                if (d === renderRoot) return [];
                if (d.children && d.isCompact) return [];
                if (d.children) return [d.data.name];
                return [d.data.name, formatNum.format(d.value)];
            })
            .join('tspan')
            .attr('x', 4)
            .attr('y', (d, i) => 13 + (i * 12))
            .style('font-weight', (d, i) => (i === 0 ? 'bold' : 'normal'))
            .text((d) => d);

        cell.append('title')
            .text((d) => {
                const total = renderRoot.value;
                const pct = total > 0 ? ((d.value / total) * 100).toFixed(1) : 0;
                const prefix = breadcrumbPath.slice(1).join(' > ');
                const local = d.ancestors().reverse().map((n) => n.data.name).join(' > ');
                const fullStr = prefix ? `${prefix} > ${local}` : local;
                return `${fullStr}\nValue: ${formatNum.format(d.value)}\nShare (view): ${pct}%`;
            });
    }

    renderChart(year, sourceNode, breadcrumbPath) {
        const chartInfo = this.charts[year];
        if (!chartInfo) return;

        const { domNode } = chartInfo;
        const L = Utils.CHART_LAYOUT;
        const width = L.TREEMAP_WIDTH;
        const height = L.TREEMAP_HEIGHT;
        const uid = `chart-${year}`;
        const formatNum = Utils.fmtNumber;

        const renderRoot = this._treemapBuildRenderRoot(sourceNode);
        domNode.innerHTML = '';

        this._treemapApplyPaddingLayout(renderRoot, width, height);

        const { group } = this._treemapAppendClipSvg(domNode, width, height, uid);
        this._treemapAppendCells(group, renderRoot, breadcrumbPath, uid, formatNum);
    }

    updateBreadcrumbs(pathNames) {
        this.breadcrumbDiv.innerHTML = '';
        pathNames.forEach((name, index) => {
            const span = document.createElement('span');
            span.className = `crumb ${index === pathNames.length - 1 ? 'active' : ''}`;
            span.textContent = name;

            if (index !== pathNames.length - 1) {
                span.onclick = (e) => {
                    e.stopPropagation();
                    const targetPath = pathNames.slice(0, index + 1);
                    this.broadcastZoom(targetPath);
                };
            }
            this.breadcrumbDiv.appendChild(span);
        });
    }

    broadcastZoom(pathNames) {
        this.updateBreadcrumbs(pathNames);

        Object.keys(this.charts).forEach((year) => {
            const chart = this.charts[year];
            chart.currentPath = pathNames;

            let targetNode = chart.fullRoot;
            let pathFound = true;

            for (let i = 1; i < pathNames.length; i++) {
                const nameToFind = pathNames[i];
                if (targetNode.children) {
                    const child = targetNode.children.find((c) => c.data.name === nameToFind);
                    if (child) {
                        targetNode = child;
                    } else {
                        pathFound = false;
                        break;
                    }
                } else {
                    pathFound = false;
                    break;
                }
            }

            if (pathFound) {
                this.renderChart(year, targetNode, pathNames);
            } else {
                this.showNoData(chart.domNode);
            }
        });
    }
}
