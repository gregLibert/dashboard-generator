// ==========================================
// RIDGELINE HORIZON WIDGET
// ==========================================
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

        if(data.length === 0) {
            container.querySelector('.horizon-wrapper').innerHTML = '<p class="hint">Aucune donnée pour cette année</p>';
            return;
        }

        this.drawRidgeline(container.querySelector('.horizon-wrapper'), data);
    }

    drawRidgeline(domNode, data) {
        const { x: xCol, y: yCol, value: valCol } = this.config.mapping;
        const bands = this.config.options?.bands || 3;
        const rowHeight = this.config.options?.height || 40;
        const colorBase = this.config.options?.color || "#08519c";
        
        const xAxisMode = this.config.options?.xAxisMode || "linear"; // "linear" ou "weekly"

        const margin = {top: 5, right: 20, bottom: 25, left: 100};
        const width = domNode.clientWidth || 800;

        // Groupement par ligne (Y)
        const groups = d3.group(data, d => d[yCol]);
        const groupKeys = Array.from(groups.keys());
        const totalHeight = groupKeys.length * rowHeight;

        // --- AXE X ---
        const x = d3.scaleLinear()
            .domain(d3.extent(data, d => +d[xCol]))
            .range([margin.left, width - margin.right]);

        // --- AXE Y (Hauteur des pics) ---
        const maxVal = d3.max(data, d => +d[valCol]);
        const y = d3.scaleLinear()
            .domain([0, maxVal])
            .range([rowHeight, rowHeight - (rowHeight * bands)]);

        // Générateur d'aire
        const area = d3.area()
            .curve(d3.curveBasis)
            .x(d => x(+d[xCol]))
            .y0(rowHeight)
            .y1(d => y(+d[valCol]));

        const uid = `ridge-${Math.random().toString(36).substr(2, 5)}`;
        const svg = d3.select(domNode).append("svg")
            .attr("viewBox", [0, 0, width, totalHeight + margin.bottom])
            .style("width", "100%")
            .style("height", "auto");

        const color = d3.scaleSequential(d3.interpolateRgb("#ffffff", colorBase))
                        .domain([-0.5, bands]);

        // --- DESSIN DES LIGNES ---
        groupKeys.forEach((key, index) => {
            const groupData = groups.get(key).sort((a,b) => +a[xCol] - +b[xCol]);
            const g = svg.append("g").attr("transform", `translate(0, ${index * rowHeight})`);

            // Clip Path pour couper ce qui dépasse en haut de la ligne
            g.append("defs").append("clipPath")
                .attr("id", `${uid}-${index}`)
                .append("rect")
                .attr("x", margin.left)
                .attr("y", 0)
                .attr("width", width - margin.left - margin.right)
                .attr("height", rowHeight);

            const clipG = g.append("g").attr("clip-path", `url(#${uid}-${index})`);

            // Boucle des bandes Horizon
            for (let i = 0; i < bands; i++) {
                clipG.append("path")
                    .datum(groupData)
                    .attr("fill", color(i))
                    .attr("d", area)
                    .attr("transform", `translate(0, ${i * rowHeight})`);
            }

            // Label à gauche
            g.append("text")
                .attr("x", margin.left - 10)
                .attr("y", rowHeight / 2)
                .attr("dy", "0.35em")
                .attr("text-anchor", "end")
                .attr("font-size", "10px")
                .text(key);
            
            // --- GRILLE VERTICALE (Si mode weekly) ---
            if (xAxisMode === "weekly") {
                // Traits verticaux tous les jours (24h, 48h...)
                [24, 48, 72, 96, 120, 144].forEach(t => {
                    g.append("line")
                        .attr("x1", x(t)).attr("x2", x(t))
                        .attr("y1", 0).attr("y2", rowHeight)
                        .attr("stroke", "rgba(0,0,0,0.05)");
                });
            }
        });

        // --- AXE X LOGIQUE (Labels) ---
        let xAxis = d3.axisBottom(x).ticks(width / 60);
        
        if (xAxisMode === "weekly") {
            const days = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"];
            xAxis.tickValues([0, 24, 48, 72, 96, 120, 144])
                 .tickFormat((d, i) => days[i] || "");
        }

        svg.append("g")
            .attr("transform", `translate(0, ${totalHeight})`)
            .call(xAxis)
            .call(g => g.select(".domain").remove());
    }
}