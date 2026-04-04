const RADIAL_CONSTANTS = {
    MARGIN: 10,
};

class RadialAreaWidget extends BaseWidget {

    initLayout() {
        super.initLayout();
        this.container.classList.add('hide-ctrl-period-type');
        this.container.classList.add('hide-ctrl-period-value');
    }

    update() {
        this.vizWrapper.innerHTML = '';

        const container = document.createElement('div');
        container.className = 'sub-chart';
        const L = Utils.CHART_LAYOUT;
        container.innerHTML = `<div style="height:${L.SQUARE_VIEW_SIZE}px"></div>`;
        this.vizWrapper.appendChild(container);

        const year = this.state.year;
        const data = this.rawData.filter(d => !d.year || d.year === year);

        if (!data.length) {
            container.querySelector('div').innerHTML =
                '<p class="hint" style="text-align:center; padding-top:100px;">Aucune donnée pour cette année.</p>';
            return;
        }

        this.drawRadialArea(container.querySelector('div'), data);
    }

    /**
     * Build radial stats over time based on the configured timeUnit.
     * Supported timeUnit values:
     * - "month" (default): aggregates by calendar month (1-12)
     * - "weekday": aggregates by day of week (0=Sunday..6=Saturday)
     * - "dayOfMonth": aggregates by day of month (1-31)
     */
    buildRadialStats(data) {
        const mapping = this.config.mapping || {};
        const dateKey = mapping.date;
        const valueKey = mapping.value;
        const options = this.config.options || {};
        const timeUnit = options.timeUnit || "month";

        const bins = new Map();

        data.forEach(d => {
            const rawDate = d[dateKey];
            if (!rawDate) return;

            const parsed = new Date(rawDate);
            if (Number.isNaN(parsed.getTime())) return;

            const v = +d[valueKey];
            if (isNaN(v)) return;

            let key;
            if (timeUnit === "weekday") {
                key = parsed.getUTCDay(); // 0-6
            } else if (timeUnit === "dayOfMonth") {
                key = parsed.getUTCDate(); // 1-31
            } else {
                // Default: month
                key = parsed.getUTCMonth() + 1; // 1-12
            }

            if (!bins.has(key)) bins.set(key, []);
            bins.get(key).push(v);
        });

        if (!bins.size) {
            return { points: [], timeUnit };
        }

        const stats = [];
        bins.forEach((vals, key) => {
            const min = d3.min(vals);
            const max = d3.max(vals);
            const avg = d3.mean(vals);
            stats.push({ key, min, max, avg });
        });

        const minmin = d3.min(stats, d => d.min);
        const maxmax = d3.max(stats, d => d.max);

        // Normalise into a single synthetic year depending on timeUnit.
        const points = stats
            .sort((a, b) => a.key - b.key)
            .map(d => {
                let date;
                if (timeUnit === "weekday") {
                    // Map weekday 0-6 to a reference week starting Monday 2000-01-03
                    const base = Date.UTC(2000, 0, 3); // Monday
                    date = new Date(base + d.key * 24 * 60 * 60 * 1000);
                } else if (timeUnit === "dayOfMonth") {
                    date = new Date(Date.UTC(2000, 0, d.key));
                } else {
                    // month
                    date = new Date(Date.UTC(2000, d.key - 1, 1));
                }
                return {
                    date,
                    avg: d.avg,
                    min: d.min,
                    max: d.max,
                    minmin,
                    maxmax
                };
            });

        return { points, timeUnit };
    }

    drawRadialArea(domNode, data) {
        const { points, timeUnit } = this.buildRadialStats(data);
        if (!points.length) {
            domNode.innerHTML = '<p class="hint" style="text-align:center; padding-top:100px;">Aucune donnée exploitable.</p>';
            return;
        }

        const width = domNode.clientWidth || Utils.CHART_LAYOUT.SQUARE_VIEW_SIZE;
        const height = width;
        const margin = RADIAL_CONSTANTS.MARGIN;
        const innerRadius = width / 5;
        const outerRadius = width / 2 - margin;

        const svg = d3.select(domNode)
            .append("svg")
            .attr("viewBox", [-width / 2, -height / 2, width, height])
            .attr("style", "width: 100%; height: auto; font: 10px sans-serif;")
            .attr("stroke-linejoin", "round")
            .attr("stroke-linecap", "round");

        const x = d3.scaleUtc()
            .domain([new Date(Date.UTC(2000, 0, 1)), new Date(Date.UTC(2001, 0, 1)) - 1])
            .range([0, 2 * Math.PI]);

        const y = d3.scaleRadial()
            .domain([d3.min(points, d => d.minmin), d3.max(points, d => d.maxmax)])
            .range([innerRadius, outerRadius]);

        const line = d3.lineRadial()
            .curve(d3.curveLinearClosed)
            .angle(d => x(d.date));

        const area = d3.areaRadial()
            .curve(d3.curveLinearClosed)
            .angle(d => x(d.date));

        const areaLayer = svg.append("g").attr("class", "radial-area-layer");

        areaLayer.append("path")
            .attr("fill", "lightsteelblue")
            .attr("fill-opacity", 0.2)
            .attr("d", area
                .innerRadius(d => y(d.minmin))
                .outerRadius(d => y(d.maxmax))
                (points));

        areaLayer.append("path")
            .attr("fill", "steelblue")
            .attr("fill-opacity", 0.2)
            .attr("d", area
                .innerRadius(d => y(d.min))
                .outerRadius(d => y(d.max))
                (points));

        areaLayer.append("path")
            .attr("fill", "none")
            .attr("stroke", UI_THEME.radialSeriesStroke)
            .attr("stroke-width", 1.5)
            .attr("d", line
                .radius(d => y(d.avg))
                (points));

        const radialTicks = y.ticks(4).reverse();
        const valueUnit = (this.config.options && this.config.options.valueUnit) || "";
        const gRadial = svg.append("g")
            .attr("text-anchor", "middle");

        gRadial.selectAll("g")
            .data(radialTicks)
            .join("g")
            .call(g => g.append("circle")
                .attr("fill", "none")
                .attr("stroke", "currentColor")
                .attr("stroke-opacity", 0.2)
                .attr("r", y))
            .call(g => g.append("text")
                .attr("y", d => -y(d))
                .attr("dy", "0.35em")
                .attr("stroke", UI_THEME.white)
                .attr("stroke-width", 5)
                .attr("fill", "currentColor")
                .attr("paint-order", "stroke")
                .text(d => `${d.toFixed(0)}${valueUnit}`)
                .clone(true)
                .attr("y", d => y(d)));

        const formatter =
            timeUnit === "weekday"
                ? d3.utcFormat("%a")
                : timeUnit === "dayOfMonth"
                    ? d => d.getUTCDate().toString()
                    : d3.utcFormat("%b");

        svg.append("g")
            .selectAll("g")
            .data(x.ticks())
            .join("g")
            .call(g => g.append("path")
                .attr("stroke", UI_THEME.black)
                .attr("stroke-opacity", 0.2)
                .attr("d", d => `
                    M${d3.pointRadial(x(d), innerRadius)}
                    L${d3.pointRadial(x(d), outerRadius)}
                `))
            .call(g => g.append("text")
                .attr("transform", d => {
                    const labelRadius = Math.max(innerRadius - 15, 0);
                    const [ax, ay] = d3.pointRadial(x(d), labelRadius);
                    return `translate(${ax},${ay})`;
                })
                .attr("text-anchor", "middle")
                .attr("alignment-baseline", "middle")
                .text(formatter));
    }
}

