// ==========================================
// NESTED TREEMAP WIDGET (SYNC OR HIDE)
// ==========================================
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

        this.colorScale = d3.scaleOrdinal(d3.schemeCategory10);
        this.charts = {}; 
    }

    update() {
        this.vizWrapper.innerHTML = '';
        this.charts = {}; 
        this.updateBreadcrumbs(['Total']);
        
        const yearsToShow = this.state.yoy ? [this.state.year - 1, this.state.year] : [this.state.year];

        yearsToShow.forEach(year => {
            const rawData = this.getFilteredData(year);
            const container = document.createElement('div');
            container.className = 'sub-chart';
            
            container.style.flex = '1';           
            container.style.display = 'flex';     
            container.style.flexDirection = 'column';
            container.style.minWidth = '0';
            container.style.height = '100%';
            
            const label = Utils.labelForPeriod(this.state.periodType, year, this.state.periodValue);
            const suffix = (this.state.yoy && year === this.state.year) ? ' (N)' : (this.state.yoy ? ' (N-1)' : '');

            container.innerHTML = `
                <h4 style="text-align:center; margin: 0 0 10px 0; min-height: 20px; cursor: pointer;" title="Cliquez pour dézoomer">${label}${suffix}</h4>
                <div class="treemap-container" style="flex: 1; min-height: 0; position:relative; overflow:hidden;"></div>
            `;
            
            this.vizWrapper.appendChild(container);
            
            const domNode = container.querySelector('.treemap-container');

            if(rawData.length === 0) {
                this.showNoData(domNode);
                return;
            }

            const { hierarchy: hierarchyCols, value } = this.config.mapping;
            const rolls = d3.rollup(rawData, 
                v => d3.sum(v, d => +d[value]), 
                ...hierarchyCols.map(col => d => d[col] || "N/A")
            );

            const makeTree = (name, val) => {
                if (val instanceof Map) return { name, children: Array.from(val, ([n, v]) => makeTree(n, v)) };
                return { name, value: val }; 
            };

            const fullRoot = d3.hierarchy(makeTree("Total", rolls))
                .sum(d => d.value)
                .sort((a, b) => b.value - a.value);

            this.charts[year] = {
                fullRoot: fullRoot, 
                domNode: domNode,
                currentPath: ['Total']
            };

            this.renderChart(year, fullRoot, ['Total']);
        });
    }

    showNoData(domNode) {
        domNode.innerHTML = 
            '<div style="height:100%; display:flex; align-items:center; justify-content:center; background:#f9f9f9; color:#999; font-style:italic;">No data available for this selection</div>';
    }

    renderChart(year, sourceNode, breadcrumbPath) {
        const chartInfo = this.charts[year];
        if (!chartInfo) return;

        const { domNode } = chartInfo;
        const width = 600; 
        const height = 500; 
        const uid = `chart-${year}`; 
        const formatNum = Utils.fmtNumber;

        const renderRoot = d3.hierarchy(sourceNode.data)
            .sum(d => d.value)
            .sort((a, b) => b.value - a.value);

        domNode.innerHTML = ''; 

        const treemap = d3.treemap()
            .size([width, height])
            .paddingOuter(3)
            .paddingInner(1)
            .round(true);

        treemap.paddingTop(d => d === renderRoot ? 0 : 18)(renderRoot);

        renderRoot.each(d => {
            if (d.children && (d.y1 - d.y0) < 35) {
                d.isCompact = true;
            }
        });

        treemap.paddingTop(d => {
            if (d === renderRoot) return 0;
            return d.isCompact ? 0 : 18;
        })(renderRoot);

        const svg = d3.select(domNode).append("svg")
            .attr("viewBox", [0, 0, width, height])
            .style("font", "10px sans-serif")
            .style("width", "100%")
            .style("height", "100%")
            .style("display", "block");

        const defs = svg.append("defs");
        defs.append("clipPath")
            .attr("id", `${uid}-clip`)
            .append("rect")
            .attr("width", width)
            .attr("height", height);

        const group = svg.append("g")
            .attr("clip-path", `url(#${uid}-clip)`);

        const cell = group.selectAll("g")
            .data(renderRoot.descendants())
            .join("g")
            .attr("transform", d => `translate(${d.x0},${d.y0})`);

        cell.append("rect")
            .attr("id", (d, i) => (d.leafUid = `leaf-${uid}-${i}`))
            .attr("width", d => Math.max(0, d.x1 - d.x0))
            .attr("height", d => Math.max(0, d.y1 - d.y0))
            .attr("fill", d => {
                if (d.depth === 0) return "none";
                return this.colorScale(d.data.name);
            })
            .attr("fill-opacity", d => d.children ? 0.6 : 0.8) 
            .attr("stroke", "#fff")
            .style("cursor", d => d.children ? "pointer" : "default")
            .on("click", (e, d) => {
                if (!d.children) return; 
                e.stopPropagation();
                const localPath = d.ancestors().reverse().map(n => n.data.name).slice(1);
                const fullPath = breadcrumbPath.concat(localPath);
                this.broadcastZoom(fullPath);
            });

        cell.append("clipPath")
            .attr("id", d => (d.clipUid = `clip-${d.leafUid}`))
            .append("use")
            .attr("xlink:href", d => `#${d.leafUid}`);

        const textNodes = cell.append("text")
            .attr("clip-path", d => `url(#${d.clipUid})`)
            .attr("x", 4)
            .attr("y", 12)
            .style("pointer-events", "none")
            .selectAll("tspan")
            .data(d => {
                if ((d.x1 - d.x0) < 30 || (d.y1 - d.y0) < 15) return [];
                if (d === renderRoot) return [];
                if (d.children && d.isCompact) return [];
                if (d.children) return [d.data.name];
                return [d.data.name, formatNum.format(d.value)];
            })
            .join("tspan")
            .attr("x", 4)
            .attr("y", (d, i) => 13 + (i * 12))
            .style("font-weight", (d, i) => i === 0 ? "bold" : "normal")
            .text(d => d);

        cell.append("title")
            .text(d => {
                const total = renderRoot.value;
                const pct = total > 0 ? ((d.value / total) * 100).toFixed(1) : 0;
                const prefix = breadcrumbPath.slice(1).join(" > ");
                const local = d.ancestors().reverse().map(n => n.data.name).join(" > ");
                const fullStr = prefix ? `${prefix} > ${local}` : local;
                return `${fullStr}\nValeur: ${formatNum.format(d.value)}\nPart (Vue): ${pct}%`;
            });
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
        
        Object.keys(this.charts).forEach(year => {
            const chart = this.charts[year];
            chart.currentPath = pathNames;

            let targetNode = chart.fullRoot;
            let pathFound = true; // On assume que le chemin existe au départ
            
            for (let i = 1; i < pathNames.length; i++) {
                const nameToFind = pathNames[i];
                if (targetNode.children) {
                    const child = targetNode.children.find(c => c.data.name === nameToFind);
                    if (child) {
                        targetNode = child;
                    } else {
                        // Chemin introuvable dans cette année
                        pathFound = false;
                        break; 
                    }
                } else {
                    // C'est une feuille, mais on cherche encore à descendre -> introuvable
                    pathFound = false;
                    break;
                }
            }

            if (pathFound) {
                // Si le chemin existe, on dessine normalement
                this.renderChart(year, targetNode, pathNames);
            } else {
                // SINON : On affiche "No Data" à la place du graphique
                this.showNoData(chart.domNode);
            }
        });
    }
}