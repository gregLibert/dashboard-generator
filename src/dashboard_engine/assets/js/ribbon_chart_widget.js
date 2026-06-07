const RIBBON_CHART_CONSTANTS = {
    NODE_WIDTH: 38,
    RIBBON_FLOW_OPACITY: 0.48,
    NODE_STROKE_WIDTH: 1,
    MIN_LABEL_HEIGHT: 16,
    GUIDE_DASH: '4,4',
    LEGEND_SWATCH_SIZE: 10,
    LEGEND_TEXT_X: 26,
    LEGEND_SWATCH_X: 10,
};

/**
 * Pure helpers for ribbon chart X bucketing (testable without DOM).
 */
function ribbonXBucket(row, periodType) {
    switch (periodType) {
        case 'trimestre':
            return Utils.getQuarter(row.month);
        case 'semestre':
            return Utils.getSemester(row.month);
        case 'annee':
            return 1;
        case 'mois':
        default:
            return row.month;
    }
}

function ribbonXDomainMax(periodType) {
    switch (periodType) {
        case 'trimestre':
            return 4;
        case 'semestre':
            return 2;
        case 'annee':
            return 1;
        case 'mois':
        default:
            return 12;
    }
}

function ribbonXTickLabel(periodType, value) {
    switch (periodType) {
        case 'trimestre':
            return `T${value}`;
        case 'semestre':
            return `S${value}`;
        case 'annee':
            return 'Année';
        case 'mois':
        default: {
            const label = Utils.moisFR[value - 1];
            return label ? label.substring(0, 3) : String(value);
        }
    }
}

function ribbonValueAt(seriesByCategory, category, x) {
    const series = seriesByCategory.find((s) => s[0].category === category);
    if (!series) {
        return 0;
    }
    const pt = series.find((p) => p.x === x);
    return pt ? pt.value : 0;
}

/**
 * Aggregate rows into stacked series keyed by X bucket and category.
 */
function buildRibbonStackedSeries(rows, mapping, periodType) {
    const valueCol = mapping.value;
    const categoryCol = mapping.category;
    const xMax = ribbonXDomainMax(periodType);
    const xValues = Array.from({ length: xMax }, (_, i) => i + 1);

    const rollup = d3.rollup(
        rows,
        (v) => d3.sum(v, (d) => +d[valueCol]),
        (d) => ribbonXBucket(d, periodType),
        (d) => (categoryCol ? d[categoryCol] : 'default')
    );

    const categories = new Set();
    rollup.forEach((inner) => {
        inner.forEach((_, cat) => categories.add(cat));
    });
    const categoriesArr = Array.from(categories).sort((a, b) => String(a).localeCompare(String(b)));

    const seriesByCategory = categoriesArr.map((cat) =>
        xValues.map((x) => {
            const inner = rollup.get(x);
            const val = inner ? inner.get(cat) || 0 : 0;
            return { x, value: val, category: cat };
        })
    );

    return { xValues, categories: categoriesArr, seriesByCategory, periodType };
}

/**
 * Per-column stacked segments (smallest at bottom, largest at top).
 * @returns {Array<{ x: number, total: number, segments: Record<string, { category: string, x: number, y0: number, y1: number, value: number }> }>}
 */
function buildRibbonColumnStacks(xValues, categories, seriesByCategory) {
    return xValues.map((x) => {
        const row = {};
        categories.forEach((cat) => {
            row[cat] = ribbonValueAt(seriesByCategory, cat, x);
        });
        const keys = categories
            .slice()
            .sort((a, b) => (row[a] || 0) - (row[b] || 0));
        const layers = d3.stack().keys(keys).order(d3.stackOrderNone).offset(d3.stackOffsetNone)([row]);
        const segments = {};
        layers.forEach((layer) => {
            const [y0, y1] = layer[0];
            segments[layer.key] = {
                category: layer.key,
                x,
                y0,
                y1,
                value: row[layer.key] || 0,
            };
        });
        return { x, total: d3.sum(categories, (c) => row[c] || 0), segments };
    });
}

/** Categories ordered top → bottom for one column stack. */
function ribbonColumnRankFromTop(column) {
    return Object.values(column.segments)
        .filter((s) => s.value > 0)
        .sort((a, b) => b.y1 - a.y1)
        .map((s) => s.category);
}

/**
 * Bump-chart link generator: sigmoid-like S-curves without vertical overshoot.
 * @see d3.curveBumpX (horizontal tangents, y stays between endpoints).
 */
function ribbonBumpLink() {
    const curve =
        typeof d3.curveBumpX === 'function' ? d3.curveBumpX : d3.curveHorizontalLink;
    return d3.link(curve).x((d) => d.x).y((d) => d.y);
}

/**
 * Closed ribbon polygon between two column segments (pixel coordinates).
 */
function ribbonFlowPathD(x0, x1, segA, segB, yScale) {
    const link = ribbonBumpLink();
    const y0Top = yScale(segA.y1);
    const y0Bot = yScale(segA.y0);
    const y1Top = yScale(segB.y1);
    const y1Bot = yScale(segB.y0);

    const top = link({
        source: { x: x0, y: y0Top },
        target: { x: x1, y: y1Top },
    });
    const bottom = link({
        source: { x: x1, y: y1Bot },
        target: { x: x0, y: y0Bot },
    });
    if (!top || !bottom) {
        return '';
    }
    return `${top}${bottom.replace(/^M/, 'L')}Z`;
}

class RibbonChartWidget extends BaseWidget {
    initLayout() {
        super.initLayout();
        this.container.classList.add('hide-ctrl-period-value');
    }

    update() {
        this.vizWrapper.innerHTML = '';

        const L = Utils.CHART_LAYOUT;
        if (this.state.yoy) {
            this.chartWidth = this.vizWrapper.clientWidth || L.DEFAULT_INNER_WIDTH;
        } else {
            this.chartWidth = null;
        }

        const anchorYear = this.state.year;
        const yearsToShow = Utils.calendarYearsForYoYChart(anchorYear, this.state.yoy);
        const periodType = this.state.periodType;

        yearsToShow.forEach((year) => {
            const container = document.createElement('div');
            container.className = 'sub-chart';
            const ySuffix = Utils.formatYoYChartTitleSuffix(this.state.yoy, year, anchorYear);
            container.innerHTML =
                `<h4>Année ${year}${ySuffix}</h4><div class="ribbon-chart-mount" style="height:${L.STANDARD_PLOT_HEIGHT}px"></div>`;
            this.vizWrapper.appendChild(container);

            const data = Utils.extractRowsForCalendarYear(this.rawData, year);
            if (!data.length) {
                container.querySelector('.ribbon-chart-mount').innerHTML =
                    '<p class="hint" style="text-align:center; padding-top:100px;">Aucune donnée pour cette année.</p>';
                return;
            }

            this.drawRibbonChart(container.querySelector('.ribbon-chart-mount'), data, periodType);
        });
    }

    drawRibbonChart(domNode, data, periodType) {
        const mapping = this.config.mapping || {};
        const { xValues, categories, seriesByCategory } = buildRibbonStackedSeries(
            data,
            mapping,
            periodType
        );

        if (!categories.length) {
            domNode.innerHTML =
                '<p class="hint" style="text-align:center; padding-top:100px;">Aucune donnée exploitable.</p>';
            return;
        }

        const columns = buildRibbonColumnStacks(xValues, categories, seriesByCategory);
        const maxTotal = d3.max(columns, (c) => c.total) || 1;

        const L = Utils.CHART_LAYOUT;
        const width = this.chartWidth || domNode.clientWidth || L.DEFAULT_INNER_WIDTH;
        const height = L.STANDARD_PLOT_HEIGHT;
        const margin = { top: 24, right: 24, bottom: 36, left: 96 };
        const nodeHalf = RIBBON_CHART_CONSTANTS.NODE_WIDTH / 2;

        const x = d3
            .scalePoint()
            .domain(xValues)
            .range([margin.left + nodeHalf, width - margin.right - nodeHalf])
            .padding(0.35);

        const y = d3
            .scaleLinear()
            .domain([0, maxTotal])
            .nice()
            .range([height - margin.bottom, margin.top]);

        const color = d3.scaleOrdinal(UI_THEME.schemeTableau10).domain(categories);

        const svg = d3
            .select(domNode)
            .append('svg')
            .attr('class', 'ribbon-chart-svg')
            .attr('viewBox', [0, 0, width, height])
            .attr('data-period-type', periodType)
            .attr('data-category-count', categories.length);

        const flowLinks = [];
        for (let i = 0; i < columns.length - 1; i++) {
            const colA = columns[i];
            const colB = columns[i + 1];
            const x0 = x(colA.x);
            const x1 = x(colB.x);
            categories.forEach((cat) => {
                const segA = colA.segments[cat];
                const segB = colB.segments[cat];
                if (!segA || !segB || (segA.value <= 0 && segB.value <= 0)) {
                    return;
                }
                flowLinks.push({
                    category: cat,
                    sourceX: colA.x,
                    targetX: colB.x,
                    d: ribbonFlowPathD(x0, x1, segA, segB, y),
                });
            });
        }

        const gGuides = svg.append('g').attr('class', 'ribbon-chart-guides');
        gGuides
            .selectAll('line')
            .data(xValues)
            .join('line')
            .attr('class', 'ribbon-chart-guide')
            .attr('x1', (xv) => x(xv))
            .attr('x2', (xv) => x(xv))
            .attr('y1', margin.top)
            .attr('y2', height - margin.bottom)
            .attr('stroke', UI_THEME.gridMajor)
            .attr('stroke-dasharray', RIBBON_CHART_CONSTANTS.GUIDE_DASH)
            .attr('stroke-width', 1);

        const gFlows = svg.append('g').attr('class', 'ribbon-chart-flows');
        gFlows
            .selectAll('path')
            .data(flowLinks)
            .join('path')
            .attr('class', 'ribbon-chart-flow')
            .attr('d', (d) => d.d)
            .attr('data-category', (d) => d.category)
            .attr('data-source-x', (d) => d.sourceX)
            .attr('data-target-x', (d) => d.targetX)
            .attr('fill', (d) => color(d.category))
            .attr('fill-opacity', RIBBON_CHART_CONSTANTS.RIBBON_FLOW_OPACITY)
            .attr('stroke', 'none')
            .append('title')
            .text((d) => d.category);

        const nodeData = [];
        columns.forEach((col) => {
            const xCenter = x(col.x);
            categories.forEach((cat) => {
                const seg = col.segments[cat];
                if (!seg || seg.value <= 0) {
                    return;
                }
                const yTop = y(seg.y1);
                const yBot = y(seg.y0);
                nodeData.push({
                    category: cat,
                    x: col.x,
                    xCenter,
                    yTop,
                    yBot,
                    height: yBot - yTop,
                    value: seg.value,
                });
            });
        });

        const gNodes = svg.append('g').attr('class', 'ribbon-chart-nodes');
        gNodes
            .selectAll('rect')
            .data(nodeData)
            .join('rect')
            .attr('class', 'ribbon-chart-node')
            .attr('x', (d) => d.xCenter - nodeHalf)
            .attr('y', (d) => d.yTop)
            .attr('width', RIBBON_CHART_CONSTANTS.NODE_WIDTH)
            .attr('height', (d) => Math.max(0, d.height))
            .attr('fill', (d) => color(d.category))
            .attr('stroke', UI_THEME.white)
            .attr('stroke-width', RIBBON_CHART_CONSTANTS.NODE_STROKE_WIDTH)
            .attr('data-category', (d) => d.category)
            .attr('data-x', (d) => d.x)
            .append('title')
            .text((d) => `${d.category}: ${Utils.fmtNumber.format(d.value)}`);

        const firstColumn = columns[0];
        const swatchHalf = RIBBON_CHART_CONSTANTS.LEGEND_SWATCH_SIZE / 2;
        const legendData = categories
            .map((cat) => {
                const seg = firstColumn.segments[cat];
                if (!seg || seg.value <= 0) {
                    return null;
                }
                return {
                    category: cat,
                    yCenter: y((seg.y0 + seg.y1) / 2),
                };
            })
            .filter(Boolean)
            .sort((a, b) => a.yCenter - b.yCenter);

        const gLegend = svg.append('g').attr('class', 'ribbon-chart-category-legend');
        gLegend
            .selectAll('rect')
            .data(legendData)
            .join('rect')
            .attr('class', 'ribbon-chart-category-swatch')
            .attr('x', RIBBON_CHART_CONSTANTS.LEGEND_SWATCH_X)
            .attr('y', (d) => d.yCenter - swatchHalf)
            .attr('width', RIBBON_CHART_CONSTANTS.LEGEND_SWATCH_SIZE)
            .attr('height', RIBBON_CHART_CONSTANTS.LEGEND_SWATCH_SIZE)
            .attr('fill', (d) => color(d.category))
            .attr('stroke', UI_THEME.white)
            .attr('stroke-width', 0.75)
            .attr('rx', 1);

        gLegend
            .selectAll('text')
            .data(legendData)
            .join('text')
            .attr('class', 'ribbon-chart-category-label')
            .attr('x', RIBBON_CHART_CONSTANTS.LEGEND_TEXT_X)
            .attr('y', (d) => d.yCenter)
            .attr('dy', '0.35em')
            .attr('text-anchor', 'start')
            .attr('fill', UI_THEME.textMuted)
            .attr('font-size', '11px')
            .attr('font-weight', '500')
            .style('pointer-events', 'none')
            .text((d) => d.category);

        const gLabels = svg.append('g').attr('class', 'ribbon-chart-node-labels');
        gLabels
            .selectAll('text')
            .data(nodeData.filter((d) => d.height >= RIBBON_CHART_CONSTANTS.MIN_LABEL_HEIGHT))
            .join('text')
            .attr('class', 'ribbon-chart-node-label')
            .attr('x', (d) => d.xCenter)
            .attr('y', (d) => d.yTop + d.height / 2)
            .attr('dy', '0.35em')
            .attr('text-anchor', 'middle')
            .attr('fill', UI_THEME.white)
            .attr('font-size', '11px')
            .attr('font-weight', '600')
            .style('pointer-events', 'none')
            .text((d) => Utils.fmtNumber.format(d.value));

        svg.append('g')
            .attr('transform', `translate(0,${height - margin.bottom})`)
            .call(
                d3
                    .axisBottom(x)
                    .tickFormat((v) => ribbonXTickLabel(periodType, v))
            )
            .call((g) => g.select('.domain').attr('stroke', UI_THEME.axisDomain))
            .call((g) => g.selectAll('line').attr('stroke', UI_THEME.gridMajor));
    }
}

/** Exposed for integration tests (full JS bundle). */
window.buildRibbonStackedSeries = buildRibbonStackedSeries;
window.buildRibbonColumnStacks = buildRibbonColumnStacks;
window.ribbonColumnRankFromTop = ribbonColumnRankFromTop;
window.ribbonFlowPathD = ribbonFlowPathD;
