// ==========================================
// ZOOMABLE SUNBURST WIDGET 
// ==========================================
class SunburstWidget extends BaseWidget {

    initLayout() {
        super.initLayout();
        // Breadcrumbs setup
        this.breadcrumbDiv = document.createElement('div');
        this.breadcrumbDiv.className = 'breadcrumbs';
        this.breadcrumbDiv.innerHTML = '<span class="crumb active">Total</span>';

        this.vizWrapper.parentNode.insertBefore(this.breadcrumbDiv, this.vizWrapper);
        
        this.chartControllers = [];
    }

    update() {
        this.vizWrapper.innerHTML = '';
        this.chartControllers = [];
        this.updateBreadcrumbs(['Total']);

        const useLogScale = this.config.options?.useLogScale || false;

        const yearsToShow = this.state.yoy ? [this.state.year - 1, this.state.year] : [this.state.year];

        yearsToShow.forEach(year => {
            const data = this.getFilteredData(year);
            const container = document.createElement('div');
            container.className = 'sub-chart';
            
            const label = Utils.labelForPeriod(this.state.periodType, year, this.state.periodValue);
            const suffix = (this.state.yoy && year === this.state.year) ? ' (N)' : (this.state.yoy ? ' (N-1)' : '');

            const logIndicator = useLogScale 
                ? '<span class="log-svg" title="Échelle Logarithmique (‰)" style="color:#6a1b9a; background:#f3e5f5; padding:2px; border-radius:4px; display:inline-flex; align-items:center; margin-left:6px;"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/><path d="M11 8v6"/><path d="M8 11h6"/></svg></span>'
                : '';

            container.innerHTML = `<h4 style="display:flex; justify-content:center; align-items:center;">
                ${label}${suffix}${logIndicator}
            </h4>
            <div class="sunburst-container" style="height:400px; display:flex; justify-content:center; align-items:center;"></div>`;
            
            this.vizWrapper.appendChild(container);
            
            if(data.length === 0) {
                container.querySelector('.sunburst-container').innerHTML = '<p class="hint">No data available</p>';
                return;
            }

            const controller = this.drawZoomableSunburst(container.querySelector('.sunburst-container'), data);
            if (controller) {
                this.chartControllers.push(controller);
            }
        });
    }

    updateBreadcrumbs(pathNames) {
        this.breadcrumbDiv.innerHTML = '';
        pathNames.forEach((name, index) => {
            const span = document.createElement('span');
            span.className = `crumb ${index === pathNames.length - 1 ? 'active' : ''}`;
            span.textContent = name;
            
            if (index !== pathNames.length - 1) {
                span.onclick = () => {
                    const targetPath = pathNames.slice(0, index + 1);
                    this.broadcastZoom(targetPath);
                };
            }
            this.breadcrumbDiv.appendChild(span);
        });
    }

    broadcastZoom(pathNames) {
        this.updateBreadcrumbs(pathNames);
        this.chartControllers.forEach(zoomToPathFn => {
            zoomToPathFn(pathNames);
        });
    }

    drawZoomableSunburst(domNode, data) {
        const { hierarchy, value } = this.config.mapping;
        const useLogScale = this.config.options?.useLogScale || false;

        const width = 400; 
        const height = 400;
        const radius = width / 6;

        // --- Data Preparation ---
        const rolls = d3.rollup(data, 
            v => d3.sum(v, d => +d[value]), 
            ...hierarchy.map(col => d => d[col] || "N/A")
        );

        const makeTree = (name, val) => {
            if (val instanceof Map) return { name, children: Array.from(val, ([n, v]) => makeTree(n, v)) };
            return { name, value: val }; 
        };
        
        const treeData = makeTree("Total", rolls);
        const root = d3.hierarchy(treeData);

        // Pre-calculate Linear Values (Real Sums) for Tooltips
        root.eachAfter(d => {
            if (d.children) {
                d.linearValue = d3.sum(d.children, c => c.linearValue);
            } else {
                d.linearValue = d.data.value; 
            }
        });

        const totalValue = root.linearValue;

        // Apply Scale (Log or Linear) for Visual Sizing
        if (useLogScale) {
            root.sum(d => d.value ? Math.log(d.value + 1) : 0);
        } else {
            root.sum(d => d.value);
        }

        root.sort((a, b) => b.value - a.value);

        const partition = d3.partition().size([2 * Math.PI, root.height + 1]);
        root.each(d => d.current = d); 
        partition(root);

        // --- COLOR LOGIC CHANGE ---
        // Using schemePaired (12 colors) to support more distinct categories
        const color = d3.scaleOrdinal(d3.schemePaired);
        const format = Utils.fmtNumber;

        const svg = d3.select(domNode).append("svg")
            .attr("viewBox", [-width / 2, -height / 2, width, height])
            .style("font", "10px sans-serif");

        const arc = d3.arc()
            .startAngle(d => d.x0)
            .endAngle(d => d.x1)
            .padAngle(d => Math.min((d.x1 - d.x0) / 2, 0.005))
            .padRadius(radius * 1.5)
            .innerRadius(d => d.y0 * radius)
            .outerRadius(d => Math.max(d.y0 * radius, d.y1 * radius - 1));

        const path = svg.append("g")
            .selectAll("path")
            .data(root.descendants().slice(1)) 
            .join("path")
            .attr("fill", d => { 
                // --- NEW COLOR STRATEGY ---
                // We use the node's name directly. 
                // "Credit" will be the same color regardless of its parent (Visa or MasterCard)
                return color(d.data.name); 
            })
            .attr("fill-opacity", d => arcVisible(d.current) ? (d.children ? 0.8 : 0.6) : 0)
            .attr("pointer-events", d => arcVisible(d.current) ? "auto" : "none")
            .attr("d", d => arc(d.current))
            // Adding a white stroke is crucial when colors are not hierarchical
            // to distinguish adjacent slices
            .attr("stroke", "white")
            .attr("stroke-width", "1px");

        path.filter(d => d.children)
            .style("cursor", "pointer")
            .on("click", (event, d) => {
                const pathNames = d.ancestors().reverse().map(node => node.data.name);
                this.broadcastZoom(pathNames);
            });

        // --- TOOLTIP UPDATE (Per Mille support) ---
        path.append("title")
            .text(d => {
                const pathStr = d.ancestors().reverse()
                    .slice(1) 
                    .map(n => n.data.name)
                    .join(" > ");
                
                const realVal = d.linearValue;
                
                // Logic: Log Scale -> Permille (‰), Linear -> Percent (%)
                let ratioStr = "";
                if (totalValue > 0) {
                    if (useLogScale) {
                        // Per mille calculation
                        const pm = (realVal / totalValue) * 1000;
                        ratioStr = `${pm.toFixed(1)}‰`;
                    } else {
                        // Percent calculation
                        const pct = (realVal / totalValue) * 100;
                        ratioStr = `${pct.toFixed(1)}%`;
                    }
                } else {
                    ratioStr = "0%";
                }

                return `${pathStr} ${format.format(realVal)} (${ratioStr})`;
            });

        const label = svg.append("g")
            .attr("pointer-events", "none")
            .attr("text-anchor", "middle")
            .style("user-select", "none")
            .selectAll("text")
            .data(root.descendants().slice(1))
            .join("text")
            .attr("dy", "0.35em")
            .attr("fill-opacity", d => +labelVisible(d.current))
            .attr("transform", d => labelTransform(d.current))
            .text(d => d.data.name);

        const parent = svg.append("circle")
            .datum(root)
            .attr("r", radius)
            .attr("fill", "none")
            .attr("pointer-events", "all")
            .on("click", (event, p) => {
                const targetNode = p.parent || root;
                const pathNames = targetNode.ancestors().reverse().map(node => node.data.name);
                this.broadcastZoom(pathNames);
            });

        // --- Internal Transition Engine ---
        const internalTransition = (targetNode) => {
            parent.datum(targetNode.parent || root);

            root.each(d => d.target = {
                x0: Math.max(0, Math.min(1, (d.x0 - targetNode.x0) / (targetNode.x1 - targetNode.x0))) * 2 * Math.PI,
                x1: Math.max(0, Math.min(1, (d.x1 - targetNode.x0) / (targetNode.x1 - targetNode.x0))) * 2 * Math.PI,
                y0: Math.max(0, d.y0 - targetNode.depth),
                y1: Math.max(0, d.y1 - targetNode.depth)
            });

            const t = svg.transition().duration(750);

            path.transition(t)
                .tween("data", d => {
                    const i = d3.interpolate(d.current, d.target);
                    return t => d.current = i(t);
                })
                .filter(function(d) { return +this.getAttribute("fill-opacity") || arcVisible(d.target); })
                .attr("fill-opacity", d => arcVisible(d.target) ? (d.children ? 0.8 : 0.6) : 0)
                .attr("pointer-events", d => arcVisible(d.target) ? "auto" : "none")
                .attrTween("d", d => () => arc(d.current));

            label.filter(function(d) { return +this.getAttribute("fill-opacity") || labelVisible(d.target); })
                .transition(t)
                .attr("fill-opacity", d => +labelVisible(d.target))
                .attrTween("transform", d => () => labelTransform(d.current));
        };

        function arcVisible(d) { return d.y1 <= 3 && d.y0 >= 1 && d.x1 > d.x0; }
        function labelVisible(d) { return d.y1 <= 3 && d.y0 >= 1 && (d.y1 - d.y0) * (d.x1 - d.x0) > 0.03; }
        function labelTransform(d) {
            const x = (d.x0 + d.x1) / 2 * 180 / Math.PI;
            const y = (d.y0 + d.y1) / 2 * radius;
            return `rotate(${x - 90}) translate(${y},0) rotate(${x < 180 ? 0 : 180})`;
        }

        return (pathNames) => {
            let currentNode = root;
            let match = true;
            for (let i = 1; i < pathNames.length; i++) {
                const nameToFind = pathNames[i];
                if (currentNode.children) {
                    const found = currentNode.children.find(c => c.data.name === nameToFind);
                    if (found) currentNode = found;
                    else { match = false; break; }
                } else { match = false; break; }
            }
            if (match) internalTransition(currentNode);
        };
    }
}