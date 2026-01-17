// ==========================================
// EVOLUTION WIDGET
// ==========================================
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
        container.innerHTML = `<div style="height:350px"></div>`;
        this.vizWrapper.appendChild(container);
        
        const yearN = this.state.year;
        const yearN1 = yearN - 1;
        
        
        const rawN = this.rawData.filter(d => d.year === yearN);
        const rawN1 = this.state.yoy ? this.rawData.filter(d => d.year === yearN1) : [];

        this.drawLineChart(container.querySelector('div'), rawN, rawN1);
    }

    drawLineChart(domNode, dataN, dataN1) {
        const { value } = this.config.mapping;
        const width = domNode.clientWidth || 800;
        const height = 350;
        const margin = {top:20, right:30, bottom:30, left:40};

        const agg = (dataset) => d3.rollup(dataset, v => d3.sum(v, d => +d[value]), d => d.month);
        const mapN = agg(dataN);
        const mapN1 = agg(dataN1);
        
        const x = d3.scaleLinear().domain([1, 12]).range([margin.left, width - margin.right]);
        const allVals = [...mapN.values(), ...mapN1.values()];
        const yMax = allVals.length > 0 ? d3.max(allVals) : 10;
        const y = d3.scaleLinear().domain([0, yMax]).nice().range([height - margin.bottom, margin.top]);

        const svg = d3.select(domNode).append("svg").attr("viewBox", [0, 0, width, height]);

        svg.append("g").attr("transform", `translate(0,${height-margin.bottom})`)
           .call(d3.axisBottom(x).ticks(12).tickFormat(m => Utils.moisFR[m-1] ? Utils.moisFR[m-1].substring(0,3) : m));
           
        svg.append("g").attr("transform", `translate(${margin.left},0)`).call(d3.axisLeft(y).ticks(5).tickFormat(d => Utils.fmtNumber.format(d)));

        const line = d3.line().x(d => x(d[0])).y(d => y(d[1]));

        if(mapN.size > 0) {
            const dataLineN = Array.from(mapN).sort((a,b)=>a[0]-b[0]);
            svg.append("path").datum(dataLineN).attr("fill","none").attr("stroke","#1f77b4").attr("stroke-width",3).attr("d", line);
            
            svg.selectAll(".dotN").data(dataLineN).join("circle")
                .attr("cx", d=>x(d[0])).attr("cy", d=>y(d[1])).attr("r", 4).attr("fill", "#1f77b4")
                .append("title").text(d => `${Utils.moisFR[d[0]-1]}: ${Utils.fmtNumber.format(d[1])}`);
        }

        if(mapN1.size > 0) {
            const dataLineN1 = Array.from(mapN1).sort((a,b)=>a[0]-b[0]);
            svg.append("path").datum(dataLineN1).attr("fill","none").attr("stroke","#1f77b4").attr("stroke-width",2).attr("stroke-dasharray","5,5").attr("d", line);
        }
        
        // Légende
        const legend = svg.append("g").attr("transform", `translate(${width - 100}, ${margin.top})`);
        legend.append("text").attr("x", 20).attr("y", 0).text(`Année ${this.state.year}`).attr("font-size", "10px").attr("fill", "#1f77b4");
        legend.append("line").attr("x1", 0).attr("y1", -3).attr("x2", 15).attr("y2", -3).attr("stroke", "#1f77b4").attr("stroke-width", 3);
        
        if(this.state.yoy) {
            legend.append("text").attr("x", 20).attr("y", 15).text(`Année ${this.state.year-1}`).attr("font-size", "10px").attr("fill", "#1f77b4").attr("opacity", 0.7);
            legend.append("line").attr("x1", 0).attr("y1", 12).attr("x2", 15).attr("y2", 12).attr("stroke", "#1f77b4").attr("stroke-width", 2).attr("stroke-dasharray", "4,2");
        }
    }
}