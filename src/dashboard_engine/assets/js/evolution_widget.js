const EVOLUTION_CONSTANTS = {
    CHART_HEIGHT_PX: 380,
    DEFAULT_INNER_WIDTH: 800,
};

class EvolutionWidget extends BaseWidget {

    initLayout() {
        super.initLayout();
        this.container.classList.add('hide-ctrl-period-type');
        this.container.classList.add('hide-ctrl-period-value');
    }

    update() {
        this.vizWrapper.innerHTML = '';
        const container = document.createElement('div');
        container.className = 'sub-chart';
        container.innerHTML = `<div style="height:${EVOLUTION_CONSTANTS.CHART_HEIGHT_PX}px"></div>`;
        this.vizWrapper.appendChild(container);

        const yearN = this.state.year;
        const yearN1 = yearN - 1;

        const rawN = this.rawData.filter(d => d.year === yearN);
        const rawN1 = this.state.yoy ? this.rawData.filter(d => d.year === yearN1) : [];

        this.drawLineChart(container.querySelector('div'), rawN, rawN1);
    }

    /**
     * Aggregate monthly values for N and N-1 and build series.
     * Pure computation, suitable for table-driven tests.
     */
    buildMonthlySeries(dataN, dataN1) {
        const { value } = this.config.mapping;
        const aggregate = (ds) => d3.rollup(ds, v => d3.sum(v, d => +d[value]), d => d.month);
        const mapN = aggregate(dataN);
        const mapN1 = aggregate(dataN1);
        const dataLineN = Array.from(mapN).sort((a, b) => a[0] - b[0]);
        const dataLineN1 = Array.from(mapN1).sort((a, b) => a[0] - b[0]);

        const allVals = [...mapN.values(), ...mapN1.values()];
        const yMax = allVals.length > 0 ? d3.max(allVals) * 1.1 : 10;

        return { mapN, mapN1, dataLineN, dataLineN1, yMax };
    }

    drawLineChart(domNode, dataN, dataN1) {
        const width = domNode.clientWidth || EVOLUTION_CONSTANTS.DEFAULT_INNER_WIDTH;
        const height = EVOLUTION_CONSTANTS.CHART_HEIGHT_PX;
        const margin = { top: 30, right: 30, bottom: 30, left: 50 };

        const { mapN, mapN1, dataLineN, dataLineN1, yMax } = this.buildMonthlySeries(dataN, dataN1);

        const x = d3.scaleLinear().domain([1, 12]).range([margin.left, width - margin.right]);
        const y = d3.scaleLinear().domain([0, yMax]).nice().range([height - margin.bottom, margin.top]);

        const svg = d3.select(domNode).append("svg").attr("viewBox", [0, 0, width, height]);
        this.drawAxes(svg, x, y, height, margin);

        const line = d3.line().x(d => x(d[0])).y(d => y(d[1]));
        
        if (mapN1.size > 0) {
            this.drawSeries(svg, dataLineN1, line, x, y, { 
                color: UI_THEME.primary, dash: "5,5", width: 2, opacity: 0.6, label: `Année ${this.state.year - 1}` 
            });
        }
        
        if (mapN.size > 0) {
            this.drawSeries(svg, dataLineN, line, x, y, { 
                color: UI_THEME.primary, dash: null, width: 3, opacity: 1, label: `Année ${this.state.year}` 
            });
            
            if (mapN1.size > 0) this.drawEvolutionLabels(svg, dataLineN, mapN1, x, y);
        }

        this.drawLegend(svg, width, margin);
    }

    drawAxes(svg, x, y, height, margin) {
        svg.append("g").attr("transform", `translate(0,${height - margin.bottom})`)
            .call(d3.axisBottom(x).ticks(12).tickFormat(m => Utils.moisFR[m - 1] ? Utils.moisFR[m - 1].substring(0, 3) : m))
            .call(g => g.select(".domain").attr("stroke", UI_THEME.axisDomain))
            .call(g => g.selectAll("line").attr("stroke", UI_THEME.gridMajor));

        svg.append("g").attr("transform", `translate(${margin.left},0)`)
            .call(d3.axisLeft(y).ticks(5).tickFormat(d => Utils.fmtNumber.format(d)))
            .call(g => g.select(".domain").remove())
            .call(g => g.selectAll("line").attr("stroke", UI_THEME.gridMajor).attr("stroke-dasharray", "2,2"));
    }

    drawSeries(svg, data, lineGen, x, y, opts) {
        svg.append("path").datum(data)
            .attr("fill", "none")
            .attr("stroke", opts.color)
            .attr("stroke-width", opts.width)
            .attr("stroke-dasharray", opts.dash)
            .attr("opacity", opts.opacity)
            .attr("d", lineGen);
        
        const className = `dot-${opts.dash ? 'N1' : 'N'}`;

        svg.selectAll(`.${className}`)
            .data(data).join("circle")
            .attr("class", className)
            .attr("cx", d => x(d[0]))
            .attr("cy", d => y(d[1]))
            .attr("r", 4)
            .attr("fill", UI_THEME.white)
            .attr("stroke", opts.color)
            .attr("stroke-width", 2)
            .style("cursor", "pointer")
            .on("mouseover", function() { d3.select(this).attr("r", 6).attr("fill", opts.color); })
            .on("mouseout", function() { d3.select(this).attr("r", 4).attr("fill", UI_THEME.white); })
            .append("title")
            .text(d => `${opts.label} - ${Utils.moisFR[d[0] - 1]}\nVal: ${Utils.fmtNumber.format(d[1])}`);
    }

    drawEvolutionLabels(svg, dataN, mapN1, x, y) {
        svg.append("g")
            .style("font-size", "10px")
            .style("font-weight", "bold")
            .selectAll("text")
            .data(dataN)
            .join("text")
            .attr("x", d => x(d[0]))
            .attr("y", d => y(d[1]) - 10)
            .attr("text-anchor", "middle")
            .each(function(d) {
                const month = d[0];
                const valN = d[1];
                const valN1 = mapN1.get(month);
                
                if (valN1 && valN1 > 0) {
                    const pct = ((valN - valN1) / valN1) * 100;
                    const symbol = pct > 0 ? "+" : "";
                    const color = pct >= 0 ? UI_THEME.positiveDelta : UI_THEME.negativeDelta;
                    
                    d3.select(this)
                        .text(`${symbol}${Math.round(pct)}%`)
                        .attr("fill", color);
                }
            });
    }

    drawLegend(svg, width, margin) {
        const legendG = svg.append("g").attr("transform", `translate(${width - 110}, ${margin.top})`);

        legendG.append("rect")
            .attr("x", -10).attr("y", -10)
            .attr("width", 120).attr("height", 50)
            .attr("fill", UI_THEME.legendBackdrop)
            .attr("stroke", UI_THEME.axisDomain)
            .attr("rx", 4);

        legendG.append("text").attr("x", 25).attr("y", 5).text(`Année ${this.state.year}`).attr("font-size", "11px").attr("fill", UI_THEME.primary);
        legendG.append("line").attr("x1", 0).attr("y1", 2).attr("x2", 20).attr("y2", 2).attr("stroke", UI_THEME.primary).attr("stroke-width", 3);

        if (this.state.yoy) {
            legendG.append("text").attr("x", 25).attr("y", 25).text(`Année ${this.state.year - 1}`).attr("font-size", "11px").attr("fill", UI_THEME.primary).attr("opacity", 0.7);
            legendG.append("line").attr("x1", 0).attr("y1", 22).attr("x2", 20).attr("y2", 22).attr("stroke", UI_THEME.primary).attr("stroke-width", 2).attr("stroke-dasharray", "4,2");
        }
    }
}