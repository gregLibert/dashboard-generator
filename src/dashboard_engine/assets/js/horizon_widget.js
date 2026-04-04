class HorizonWidget extends BaseWidget {

    initLayout() {
        super.initLayout();
        
        this.container.classList.add('hide-ctrl-period-type'); 
        this.container.classList.add('hide-ctrl-period-value');
        this.container.classList.add('hide-ctrl-yoy'); 
        this.state.yoy = false;
    }

    update() {
        this.vizWrapper.innerHTML = '';
        
        const year = this.state.year;
        const data = this.rawData.filter(d => !d.year || d.year === year);

        const container = document.createElement('div');
        container.className = 'sub-chart';
        container.style.flex = "1 1 100%"; 
        
        container.innerHTML = `<h4>Analyse temporelle - Année ${year}</h4>
                               <div class="horizon-wrapper" style="width:100%;"></div>`;
        this.vizWrapper.appendChild(container);

        if (data.length === 0) {
            container.querySelector('.horizon-wrapper').innerHTML = '<p class="hint">Aucune donnée pour cette année</p>';
            return;
        }

        this.drawRidgeline(container.querySelector('.horizon-wrapper'), data);
    }

    /**
     * Prepare grouped data and basic scales for the horizon chart.
     * Pure computation to ease table-driven testing.
     */
    buildRidgelineModel(data) {
        const { x: xCol, y: yCol, value: valCol } = this.config.mapping;
        const bands = this.config.options?.bands || 3;
        const rowHeight = this.config.options?.height || 40;
        const colorBase = this.config.options?.color || UI_THEME.defaultHorizonBlue;
        const xAxisMode = this.config.options?.xAxisMode || "linear";

        const margin = { top: 5, right: 20, bottom: 25, left: 100 };

        const groups = d3.group(data, d => d[yCol]);
        const groupKeys = Array.from(groups.keys());

        const xDomain = d3.extent(data, d => +d[xCol]);
        const maxVal = d3.max(data, d => +d[valCol]) || 0;

        return {
            bands,
            rowHeight,
            colorBase,
            xAxisMode,
            margin,
            groups,
            groupKeys,
            xDomain,
            maxVal
        };
    }

    drawRidgeline(domNode, data) {
        const { x: xCol, y: yCol, value: valCol } = this.config.mapping;
        const model = this.buildRidgelineModel(data);

        const width = domNode.clientWidth || Utils.CHART_LAYOUT.DEFAULT_INNER_WIDTH;
        const totalHeight = model.groupKeys.length * model.rowHeight;

        const x = d3.scaleLinear()
            .domain(model.xDomain)
            .range([model.margin.left, width - model.margin.right]);

        const y = d3.scaleLinear()
            .domain([0, model.maxVal])
            .range([model.rowHeight, model.rowHeight - (model.rowHeight * model.bands)]);

        const area = d3.area()
            .curve(d3.curveBasis)
            .x(d => x(+d[xCol]))
            .y0(model.rowHeight)
            .y1(d => y(+d[valCol]));

        const uid = `ridge-${Math.random().toString(36).substr(2, 5)}`;
        const svg = d3.select(domNode).append("svg")
            .attr("viewBox", [0, 0, width, totalHeight + model.margin.bottom])
            .style("width", "100%")
            .style("height", "auto");

        const color = d3.scaleSequential(d3.interpolateRgb(UI_THEME.white, model.colorBase))
                        .domain([-0.5, model.bands]);

        model.groupKeys.forEach((key, index) => {
            const groupData = model.groups.get(key).sort((a, b) => +a[xCol] - +b[xCol]);
            const g = svg.append("g").attr("transform", `translate(0, ${index * model.rowHeight})`);

            g.append("defs").append("clipPath")
                .attr("id", `${uid}-${index}`)
                .append("rect")
                .attr("x", model.margin.left)
                .attr("y", 0)
                .attr("width", width - model.margin.left - model.margin.right)
                .attr("height", model.rowHeight);

            const clipG = g.append("g").attr("clip-path", `url(#${uid}-${index})`);

            for (let i = 0; i < model.bands; i++) {
                clipG.append("path")
                    .datum(groupData)
                    .attr("fill", color(i))
                    .attr("d", area)
                    .attr("transform", `translate(0, ${i * model.rowHeight})`);
            }

            g.append("text")
                .attr("x", model.margin.left - 10)
                .attr("y", model.rowHeight / 2)
                .attr("dy", "0.35em")
                .attr("text-anchor", "end")
                .attr("font-size", "10px")
                .text(key);
            
            if (model.xAxisMode === "weekly") {
                const gridHours = [24, 48, 72, 96, 120, 144];
                gridHours.forEach(t => {
                    g.append("line")
                        .attr("x1", x(t)).attr("x2", x(t))
                        .attr("y1", 0).attr("y2", model.rowHeight)
                        .attr("stroke", "rgba(0,0,0,0.05)");
                });
            }
        });

        let xAxis = d3.axisBottom(x).ticks(width / 60);
        
        if (model.xAxisMode === "weekly") {
            const days = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"];
            const hours = [0, 24, 48, 72, 96, 120, 144];
            xAxis = xAxis
                .tickValues(hours)
                .tickFormat((d, i) => days[i] || "");
        }

        svg.append("g")
            .attr("transform", `translate(0, ${totalHeight})`)
            .call(xAxis)
            .call(g => g.select(".domain").remove());
    }
}