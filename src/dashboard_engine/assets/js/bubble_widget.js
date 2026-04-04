const BUBBLE_CONSTANTS = {
    MAX_RADIUS_PX: 30,
};

function buildBubblePoints(rows, mapping) {
    const xKey = mapping.x;
    const yKey = mapping.y;
    const rKey = mapping.r;
    const categoryKey = mapping.category;
    if (!xKey || !yKey || !rKey) {
        return [];
    }

    return rows
        .map((d) => {
            const xVal = +d[xKey];
            const yVal = +d[yKey];
            const rVal = +d[rKey];
            if (isNaN(xVal) || isNaN(yVal) || isNaN(rVal)) {
                return null;
            }
            const category = categoryKey ? d[categoryKey] : 'default';
            return { x: xVal, y: yVal, r: rVal, category, raw: d };
        })
        .filter(Boolean);
}

/**
 * Shared numeric domains for YoY (each panel re-ranges to its own width).
 */
function bubbleDomainsFromPoints(allPoints) {
    if (!allPoints.length) {
        return null;
    }
    return {
        xExtent: d3.extent(allPoints, (d) => d.x),
        yExtent: d3.extent(allPoints, (d) => d.y),
        rMax: d3.max(allPoints, (d) => d.r) || 1,
        categories: Array.from(new Set(allPoints.map((d) => d.category))),
    };
}

function buildBubbleScalesForSize(domains, innerWidth, chartHeight, margin) {
    const x = d3.scaleLinear()
        .domain(domains.xExtent)
        .nice()
        .range([margin.left, innerWidth - margin.right]);

    const y = d3.scaleLinear()
        .domain(domains.yExtent)
        .nice()
        .range([chartHeight - margin.bottom, margin.top]);

    const rScale = d3.scaleSqrt()
        .domain([0, domains.rMax])
        .range([0, BUBBLE_CONSTANTS.MAX_RADIUS_PX]);

    const color = d3.scaleOrdinal(UI_THEME.schemeTableau10).domain(domains.categories);

    return { x, y, rScale, color };
}

class BubbleWidget extends BaseWidget {

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

        const allPoints = rowSlices.flatMap((rows) => buildBubblePoints(rows, mapping));
        const domains = bubbleDomainsFromPoints(allPoints);

        years.forEach((year) => {
            const data = Utils.extractRowsForCalendarYear(this.rawData, year);
            const container = document.createElement('div');
            container.className = 'sub-chart';
            const suffix = Utils.formatYoYChartTitleSuffix(this.state.yoy, year, anchorYear);
            container.innerHTML =
                `<h4>${year}${suffix}</h4><div class="bubble-chart" style="height:${Utils.CHART_LAYOUT.STANDARD_PLOT_HEIGHT}px;"></div>`;
            this.vizWrapper.appendChild(container);

            const mount = container.querySelector('.bubble-chart');
            if (!data.length) {
                mount.innerHTML =
                    '<p class="hint" style="text-align:center; padding-top:100px;">Aucune donnée pour cette année.</p>';
                return;
            }

            this.drawBubbleChart(mount, data, domains);
        });
    }

    buildBubbleData(data) {
        return buildBubblePoints(data, this.config.mapping || {});
    }

    drawBubbleChart(domNode, data, sharedDomains) {
        const bubbles = this.buildBubbleData(data);
        if (!bubbles.length) {
            domNode.innerHTML =
                '<p class="hint" style="text-align:center; padding-top:100px;">Aucune donnée exploitable.</p>';
            return;
        }

        const margin = { top: 30, right: 30, bottom: 40, left: 50 };
        const L = Utils.CHART_LAYOUT;
        const chartHeight = L.STANDARD_PLOT_HEIGHT;
        const innerWidth = domNode.clientWidth || L.DEFAULT_INNER_WIDTH;

        const domains = sharedDomains || bubbleDomainsFromPoints(bubbles);
        if (!domains) {
            domNode.innerHTML =
                '<p class="hint" style="text-align:center; padding-top:100px;">Aucune donnée exploitable.</p>';
            return;
        }

        const { x, y, rScale, color } = buildBubbleScalesForSize(
            domains,
            innerWidth,
            chartHeight,
            margin
        );

        const svg = d3.select(domNode)
            .append('svg')
            .attr('viewBox', [0, 0, innerWidth, chartHeight]);

        svg.append('g')
            .attr('transform', `translate(0,${chartHeight - margin.bottom})`)
            .call(d3.axisBottom(x).ticks(6))
            .call((g) => g.select('.domain').attr('stroke', UI_THEME.axisDomain))
            .call((g) => g.selectAll('line').attr('stroke', UI_THEME.gridMajor));

        svg.append('g')
            .attr('transform', `translate(${margin.left},0)`)
            .call(d3.axisLeft(y).ticks(5))
            .call((g) => g.select('.domain').remove())
            .call((g) => g.selectAll('line').attr('stroke', UI_THEME.gridMajor).attr('stroke-dasharray', '2,2'));

        svg.append('g')
            .attr('class', 'bubble-layer')
            .selectAll('circle')
            .data(bubbles)
            .join('circle')
            .attr('cx', (d) => x(d.x))
            .attr('cy', (d) => y(d.y))
            .attr('r', (d) => rScale(d.r))
            .attr('fill', (d) => color(d.category))
            .attr('fill-opacity', 0.7)
            .attr('stroke', UI_THEME.white)
            .attr('stroke-width', 1)
            .append('title')
            .text((d) => {
                const mapping = this.config.mapping || {};
                const xKey = mapping.x;
                const yKey = mapping.y;
                const rKey = mapping.r;
                const categoryKey = mapping.category;
                const catLabel = categoryKey ? d.raw[categoryKey] : d.category;
                return `${xKey}: ${d.raw[xKey]}\n${yKey}: ${d.raw[yKey]}\n${rKey}: ${d.raw[rKey]}\nCategory: ${catLabel}`;
            });
    }
}
