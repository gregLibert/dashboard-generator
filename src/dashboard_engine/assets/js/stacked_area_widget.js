class StackedAreaWidget extends BaseWidget {

    initLayout() {
        super.initLayout();
        this.container.classList.add('hide-ctrl-period-type');
        this.container.classList.add('hide-ctrl-period-value');
        this.state.periodType = 'annee';
        this.state.normalized = false;
    }

    renderControls() {
        super.renderControls();

        const typeCtrl = this.container.querySelector('.ctrl-period-type');
        const valCtrl = this.container.querySelector('.ctrl-period-value');
        if (typeCtrl) typeCtrl.style.display = 'none';
        if (valCtrl) valCtrl.style.display = 'none';

        // Add a toggle to switch between absolute and 100% stacked.
        const toggleGroup = document.createElement('div');
        toggleGroup.className = 'control-group ctrl-normalized-toggle';
        toggleGroup.innerHTML = `
            <label>
                <input type="checkbox" ${this.state.normalized ? 'checked' : ''}>
                100% stacked
            </label>
        `;
        const input = toggleGroup.querySelector('input');
        input.onchange = (e) => {
            this.state.normalized = e.target.checked;
            this.update();
        };

        this.controlsDiv.appendChild(toggleGroup);
    }

    /**
     * Prepare stacked series data per month and category.
     * Returns { xValues, categories, seriesByCategory }.
     */
    buildStackedSeries(rawData) {
        const mapping = this.config.mapping || {};
        const valueCol = mapping.value;
        const categoryCol = mapping.category;

        // Aggregate values per (month, category).
        const rollup = d3.rollup(
            rawData,
            v => d3.sum(v, d => +d[valueCol]),
            d => d.month,
            d => categoryCol ? d[categoryCol] : 'default'
        );

        const xValues = Array.from(rollup.keys()).sort((a, b) => a - b);
        const categories = new Set();

        xValues.forEach(m => {
            const inner = rollup.get(m);
            if (!inner) return;
            inner.forEach((_, cat) => categories.add(cat));
        });

        const categoriesArr = Array.from(categories);

        const seriesByCategory = categoriesArr.map(cat => {
            return xValues.map(month => {
                const inner = rollup.get(month);
                const val = inner ? inner.get(cat) || 0 : 0;
                return { month, value: val, category: cat };
            });
        });

        return { xValues, categories: categoriesArr, seriesByCategory };
    }

    update() {
        this.vizWrapper.innerHTML = '';

        // When YoY is enabled, use a single width reference for all sub-charts (N and N-1)
        // so that their diagrams share the exact same dimensions. For a single year view,
        // we let each chart compute its own width from its container to avoid overflow.
        if (this.state.yoy) {
            this.chartWidth = this.vizWrapper.clientWidth || 800;
        } else {
            this.chartWidth = null;
        }

        const yearsToShow = this.state.yoy
            ? [this.state.year - 1, this.state.year]
            : [this.state.year];

        yearsToShow.forEach(year => {
            const container = document.createElement('div');
            container.className = 'sub-chart';
            container.innerHTML = `<h4>Année ${year}</h4><div style="height:380px"></div>`;
            this.vizWrapper.appendChild(container);

            const data = this.rawData.filter(d => d.year === year);
            if (!data.length) {
                container.querySelector('div').innerHTML =
                    '<p class="hint" style="text-align:center; padding-top:100px;">Aucune donnée pour cette année.</p>';
                return;
            }

            this.drawStackedArea(container.querySelector('div'), data);
        });
    }

    drawStackedArea(domNode, data) {
        const { value } = this.config.mapping;

        const width = this.chartWidth || domNode.clientWidth || 800;
        const height = 380;
        const margin = { top: 30, right: 30, bottom: 30, left: 50 };

        const { xValues, categories, seriesByCategory } = this.buildStackedSeries(data);
        const stackedInput = xValues.map((month, idx) => {
            const row = { month };
            categories.forEach((cat, cIdx) => {
                row[cat] = seriesByCategory[cIdx][idx].value;
            });
            return row;
        });

        // Build stacks.
        const stackGen = d3.stack()
            .keys(categories)
            .order(d3.stackOrderNone)
            .offset(d3.stackOffsetNone);

        let stackedSeries = stackGen(stackedInput);

        // Optional normalization to 100% stacked.
        if (this.state.normalized) {
            stackedSeries = stackedSeries.map(layer => {
                const key = layer.key;
                const normalizedLayer = layer.map(d => {
                    const total = categories.reduce((acc, cat) => acc + (d.data[cat] || 0), 0);
                    const base = total > 0 ? (d[0] / total) : 0;
                    const top = total > 0 ? (d[1] / total) : 0;
                    return [base, top, d.data];
                });
                // Preserve the series key so that color mapping stays stable.
                normalizedLayer.key = key;
                return normalizedLayer;
            });
        }

        const x = d3.scaleLinear()
            .domain([1, 12])
            .range([margin.left, width - margin.right]);

        // IMPORTANT: for stacked areas, the Y domain must be based on the stacked
        // total (max of y1 across all layers), not the max of a single category.
        const stackedMax = d3.max(stackedSeries, layer => d3.max(layer, d => d[1])) || 0;
        const yDomainMax = this.state.normalized ? 1 : (stackedMax || 1);

        const y = d3.scaleLinear()
            .domain([0, yDomainMax])
            .nice()
            .range([height - margin.bottom, margin.top]);

        const color = d3.scaleOrdinal(UI_THEME.schemeTableau10).domain(categories);

        const svg = d3.select(domNode)
            .append("svg")
            .attr("viewBox", [0, 0, width, height])
            .attr("data-normalized", this.state.normalized ? "true" : "false");

        // Axes.
        svg.append("g")
            .attr("transform", `translate(0,${height - margin.bottom})`)
            .call(
                d3.axisBottom(x)
                    .ticks(12)
                    .tickFormat(m => Utils.moisFR[m - 1] ? Utils.moisFR[m - 1].substring(0, 3) : m)
            )
            .call(g => g.select(".domain").attr("stroke", UI_THEME.axisDomain))
            .call(g => g.selectAll("line").attr("stroke", UI_THEME.gridMajor));

        svg.append("g")
            .attr("transform", `translate(${margin.left},0)`)
            .call(
                d3.axisLeft(y)
                    .ticks(5)
                    .tickFormat(d => this.state.normalized
                        ? `${Math.round(d * 100)}%`
                        : Utils.fmtNumber.format(d))
            )
            .call(g => g.select(".domain").remove())
            .call(g => g.selectAll("line").attr("stroke", UI_THEME.gridMajor).attr("stroke-dasharray", "2,2"));

        const area = d3.area()
            .x(d => x(d[2].month))
            .y0(d => y(d[0]))
            .y1(d => y(d[1]))
            .curve(d3.curveMonotoneX);

        const groups = svg.append("g")
            .selectAll("path")
            .data(stackedSeries)
            .join("path")
            .attr("class", "stacked-area-layer")
            // Color is bound to the series key (category) and does not change
            // between absolute and 100% stacked modes.
            .attr("fill", layer => color(layer.key))
            .attr("fill-opacity", 0.8)
            .attr("stroke", UI_THEME.white)
            .attr("stroke-width", 0.5)
            .attr("d", layer => area(layer.map((d, idx) => {
                const dataPoint = this.state.normalized
                    ? { month: xValues[idx] }
                    : d.data;
                return [d[0], d[1], dataPoint];
            })))
            .append("title")
            .text((layer, layerIndex, nodes) => {
                const key = categories[layerIndex] || "series";
                return this.state.normalized
                    ? `${key} (100% stacked mode)`
                    : `${key}`;
            });
    }
}

