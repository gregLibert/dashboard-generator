const HEATMAP_CONSTANTS = {
    CHART_HEIGHT_PX: 380,
    DEFAULT_INNER_WIDTH: 800,
};

/**
 * Pure: build heatmap matrix from flat rows (no instance state).
 */
function buildHeatmapMatrix(rows, mapping) {
    const xKey = mapping.x;
    const yKey = mapping.y;
    const valueKey = mapping.value;
    if (!xKey || !yKey || !valueKey) {
        return { cells: [], xValues: [], yValues: [] };
    }

    const cells = rows
        .map((d) => {
            const xVal = d[xKey];
            const yVal = d[yKey];
            const v = +d[valueKey];
            if (xVal == null || yVal == null || isNaN(v)) {
                return null;
            }
            return { x: xVal, y: yVal, value: v, raw: d };
        })
        .filter(Boolean);

    const xValues = Array.from(new Set(cells.map((d) => d.x)));
    const yValues = Array.from(new Set(cells.map((d) => d.y)));

    return { cells, xValues, yValues };
}

/**
 * Shared color domain across multiple year slices so comparable cells use the same scale.
 */
function heatmapValueExtentFromSlices(rowsByYear, mapping) {
    const merged = [];
    for (const rows of rowsByYear) {
        merged.push(...buildHeatmapMatrix(rows, mapping).cells);
    }
    if (!merged.length) {
        return [0, 1];
    }
    return d3.extent(merged, (d) => d.value);
}

class HeatmapWidget extends BaseWidget {

    initLayout() {
        super.initLayout();
        this.container.classList.add('hide-ctrl-period-type');
        this.container.classList.add('hide-ctrl-period-value');
    }

    update() {
        this.vizWrapper.innerHTML = '';

        const mapping = this.config.mapping || {};
        const anchorYear = this.state.year;
        const years = Utils.calendarYearsForYoYChart(anchorYear, this.state.yoy);
        const rowSlices = years.map((y) => Utils.extractRowsForCalendarYear(this.rawData, y));
        const anyData = rowSlices.some((r) => r.length > 0);

        if (!anyData) {
            const empty = document.createElement('div');
            empty.className = 'sub-chart';
            empty.innerHTML =
                '<p class="hint" style="text-align:center; padding-top:100px;">Aucune donnée pour cette année.</p>';
            this.vizWrapper.appendChild(empty);
            return;
        }

        const colorDomain = heatmapValueExtentFromSlices(rowSlices, mapping);
        const color = d3.scaleSequential(UI_THEME.heatmapInterpolator).domain(colorDomain);

        years.forEach((year) => {
            const data = Utils.extractRowsForCalendarYear(this.rawData, year);
            const container = document.createElement('div');
            container.className = 'sub-chart';
            const suffix = Utils.formatYoYChartTitleSuffix(this.state.yoy, year, anchorYear);
            container.innerHTML =
                `<h4>${year}${suffix}</h4><div class="heatmap-chart" style="height:${HEATMAP_CONSTANTS.CHART_HEIGHT_PX}px;"></div>`;
            this.vizWrapper.appendChild(container);

            const mount = container.querySelector('.heatmap-chart');
            if (!data.length) {
                mount.innerHTML =
                    '<p class="hint" style="text-align:center; padding-top:100px;">Aucune donnée pour cette année.</p>';
                return;
            }

            this.drawHeatmap(mount, data, color);
        });
    }

    buildHeatmapData(data) {
        return buildHeatmapMatrix(data, this.config.mapping || {});
    }

    drawHeatmap(domNode, data, sharedColorScale) {
        const { cells, xValues, yValues } = this.buildHeatmapData(data);
        if (!cells.length) {
            domNode.innerHTML =
                '<p class="hint" style="text-align:center; padding-top:100px;">Aucune donnée exploitable.</p>';
            return;
        }

        const width = domNode.clientWidth || HEATMAP_CONSTANTS.DEFAULT_INNER_WIDTH;
        const height = HEATMAP_CONSTANTS.CHART_HEIGHT_PX;
        const margin = { top: 30, right: 30, bottom: 40, left: 70 };

        const x = d3.scaleBand()
            .domain(xValues)
            .range([margin.left, width - margin.right])
            .padding(0.05);

        const y = d3.scaleBand()
            .domain(yValues)
            .range([margin.top, height - margin.bottom])
            .padding(0.05);

        const vExtent = d3.extent(cells, (d) => d.value);
        const color =
            sharedColorScale ||
            d3.scaleSequential(UI_THEME.heatmapInterpolator).domain(vExtent);

        const svg = d3.select(domNode)
            .append('svg')
            .attr('viewBox', [0, 0, width, height]);

        svg.append('g')
            .attr('transform', `translate(0,${height - margin.bottom})`)
            .call(d3.axisBottom(x))
            .selectAll('text')
            .attr('transform', 'rotate(-30)')
            .style('text-anchor', 'end');

        svg.append('g')
            .attr('transform', `translate(${margin.left},0)`)
            .call(d3.axisLeft(y));

        svg.append('g')
            .attr('class', 'heatmap-layer')
            .selectAll('rect')
            .data(cells)
            .join('rect')
            .attr('x', (d) => x(d.x))
            .attr('y', (d) => y(d.y))
            .attr('width', x.bandwidth())
            .attr('height', y.bandwidth())
            .attr('fill', (d) => color(d.value))
            .append('title')
            .text((d) => {
                const m = this.config.mapping || {};
                const xKey = m.x;
                const yKey = m.y;
                const valueKey = m.value;
                return `${xKey}: ${d.raw[xKey]}\n${yKey}: ${d.raw[yKey]}\n${valueKey}: ${d.raw[valueKey]}`;
            });
    }
}
