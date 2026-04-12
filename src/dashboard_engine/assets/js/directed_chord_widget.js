/**
 * Directed chord diagram: flows from source family to target family (matrix via d3.chordDirected).
 */
const DIRECTED_CHORD_CONSTANTS = {
    RIBBON_DIM_OPACITY: 0.12,
    RIBBON_FOCUS_OPACITY: 0.85,
    ARC_DIM_OPACITY: 0.35,
    ARC_FOCUS_OPACITY: 1,
};

/**
 * Build a square flow matrix and ordered node labels from flat rows.
 * @param {Array<object>} rows
 * @param {string} sourceKey
 * @param {string} targetKey
 * @param {string} valueKey
 * @returns {{ labels: string[], matrix: number[][], index: Map<string, number> } | null}
 */
function buildDirectedChordMatrix(rows, sourceKey, targetKey, valueKey) {
    if (!sourceKey || !targetKey || !valueKey || !rows.length) {
        return null;
    }
    const names = new Set();
    rows.forEach((row) => {
        const s = row[sourceKey];
        const t = row[targetKey];
        if (s != null && String(s).length) names.add(String(s));
        if (t != null && String(t).length) names.add(String(t));
    });
    const labels = Array.from(names).sort((a, b) => a.localeCompare(b));
    if (!labels.length) {
        return null;
    }
    const index = new Map(labels.map((name, i) => [name, i]));
    const n = labels.length;
    const matrix = Array.from({ length: n }, () => Array(n).fill(0));
    rows.forEach((row) => {
        const s = row[sourceKey];
        const t = row[targetKey];
        if (s == null || t == null) return;
        const si = index.get(String(s));
        const ti = index.get(String(t));
        if (si === undefined || ti === undefined) return;
        const v = +row[valueKey];
        if (!Number.isFinite(v)) return;
        matrix[si][ti] += v;
    });
    return { labels, matrix, index };
}

class DirectedChordWidget extends BaseWidget {
    initLayout() {
        super.initLayout();
        const opts = this.config.options || {};
        this._summable = opts.summable !== false;
        if (!this._summable) {
            this.container.classList.add('hide-ctrl-period-type');
            this.container.classList.add('hide-ctrl-period-value');
        }
        this.container.classList.add('hide-ctrl-yoy');
        this.state.yoy = false;
    }

    /**
     * Rows for the chord: filtered by period when summable; full year slice when not.
     */
    getChordRows(year) {
        if (!this._summable) {
            return this.rawData.filter((d) => d.year === year);
        }
        return this.getFilteredData(year);
    }

    update() {
        this.vizWrapper.innerHTML = '';
        const mapping = this.config.mapping || {};
        const sourceKey = mapping.source;
        const targetKey = mapping.target;
        const valueKey = mapping.value;
        const year = this.state.year;

        const rows = this.getChordRows(year);
        const built = buildDirectedChordMatrix(rows, sourceKey, targetKey, valueKey);
        if (!built) {
            const wrap = document.createElement('div');
            wrap.className = 'sub-chart';
            wrap.innerHTML =
                '<p class="hint" style="text-align:center; padding-top:80px;">Aucune donnée pour cette période.</p>';
            this.vizWrapper.appendChild(wrap);
            return;
        }

        const { labels, matrix } = built;
        const hasFlow = matrix.some((row) => row.some((v) => v > 0));
        if (!hasFlow) {
            const wrap = document.createElement('div');
            wrap.className = 'sub-chart';
            wrap.innerHTML =
                '<p class="hint" style="text-align:center; padding-top:80px;">Aucun flux à afficher.</p>';
            this.vizWrapper.appendChild(wrap);
            return;
        }

        if (typeof d3.chordDirected !== 'function') {
            const wrap = document.createElement('div');
            wrap.className = 'sub-chart';
            wrap.innerHTML =
                '<p class="hint" style="text-align:center; padding-top:80px;">d3.chordDirected indisponible (D3 7 requis).</p>';
            this.vizWrapper.appendChild(wrap);
            return;
        }

        const chordLayout = d3
            .chordDirected()
            .padAngle(0.05)
            .sortSubgroups(d3.descending);
        let chords;
        try {
            chords = chordLayout(matrix);
        } catch (e) {
            console.error('DirectedChordWidget: chord layout failed', e);
            const wrap = document.createElement('div');
            wrap.className = 'sub-chart';
            wrap.innerHTML =
                '<p class="hint" style="text-align:center; padding-top:80px;">Données insuffisantes pour le diagramme.</p>';
            this.vizWrapper.appendChild(wrap);
            return;
        }

        if (!chords.groups || !chords.groups.length) {
            const wrap = document.createElement('div');
            wrap.className = 'sub-chart';
            wrap.innerHTML =
                '<p class="hint" style="text-align:center; padding-top:80px;">Aucun flux à afficher.</p>';
            this.vizWrapper.appendChild(wrap);
            return;
        }

        const L = Utils.CHART_LAYOUT;
        const width = this.vizWrapper.clientWidth || L.DEFAULT_INNER_WIDTH;
        const height = Math.min(L.STANDARD_PLOT_HEIGHT, width * 0.85);
        const outerRadius = Math.min(width, height) * 0.42;
        const innerRadius = outerRadius - 22;

        const wrap = document.createElement('div');
        wrap.className = 'sub-chart';
        wrap.style.textAlign = 'center';
        this.vizWrapper.appendChild(wrap);

        const svg = d3
            .select(wrap)
            .append('svg')
            .attr('class', 'directed-chord-svg')
            .attr('viewBox', `${-width / 2} ${-height / 2} ${width} ${height}`)
            .attr('width', width)
            .attr('height', height);

        const color = d3.scaleOrdinal(UI_THEME.schemeTableau10).domain(labels);

        const arc = d3
            .arc()
            .innerRadius(innerRadius)
            .outerRadius(outerRadius);

        const ribbon = d3
            .ribbonArrow()
            .radius(outerRadius - 2)
            .padAngle(1 / outerRadius);

        const gMain = svg.append('g').attr('class', 'directed-chord-root');

        const gRibbons = gMain.append('g').attr('class', 'directed-chord-ribbons').attr('fill-opacity', DIRECTED_CHORD_CONSTANTS.RIBBON_FOCUS_OPACITY);

        const ribbonPaths = gRibbons
            .selectAll('path')
            .data(chords)
            .join('path')
            .attr('class', 'directed-chord-ribbon')
            .attr('fill', (d) => color(labels[d.source.index]))
            .attr('stroke', UI_THEME.white)
            .attr('stroke-width', 0.35)
            .attr('data-source-index', (d) => d.source.index)
            .attr('data-target-index', (d) => d.target.index)
            .attr('d', ribbon)
            .each(function (d) {
                const sName = labels[d.source.index];
                const tName = labels[d.target.index];
                const v = matrix[d.source.index][d.target.index];
                d3.select(this)
                    .append('title')
                    .text(`Flux: ${sName} → ${tName}\nVolume: ${Utils.fmtNumber.format(v)}`);
            });

        const gArcs = gMain.append('g').attr('class', 'directed-chord-arcs');

        const arcPaths = gArcs
            .selectAll('path')
            .data(chords.groups)
            .join('path')
            .attr('class', 'directed-chord-arc')
            .attr('fill', (d) => color(labels[d.index]))
            .attr('stroke', UI_THEME.white)
            .attr('stroke-width', 1)
            .attr('data-group-index', (d) => d.index)
            .attr('d', arc)
            .style('cursor', 'default')
            .each(function (d) {
                const idx = d.index;
                let inflow = 0;
                let outflow = 0;
                for (let ri = 0; ri < matrix.length; ri++) {
                    inflow += matrix[ri][idx] || 0;
                }
                const outRow = matrix[idx] || [];
                for (let cj = 0; cj < outRow.length; cj++) {
                    outflow += outRow[cj] || 0;
                }
                d3.select(this)
                    .append('title')
                    .text(
                        `${labels[idx]}\nSortant (Σ): ${Utils.fmtNumber.format(outflow)}\nEntrant (Σ): ${Utils.fmtNumber.format(inflow)}`
                    );
            });

        const resetHighlight = () => {
            ribbonPaths
                .attr('fill-opacity', DIRECTED_CHORD_CONSTANTS.RIBBON_FOCUS_OPACITY)
                .style('filter', null);
            arcPaths.attr('fill-opacity', DIRECTED_CHORD_CONSTANTS.ARC_FOCUS_OPACITY).style('filter', null);
        };

        arcPaths
            .on('mouseenter', function (_event, d) {
                const idx = d.index;
                ribbonPaths.each(function (r) {
                    const el = d3.select(this);
                    const hit = r.source.index === idx || r.target.index === idx;
                    el.attr('fill-opacity', hit ? DIRECTED_CHORD_CONSTANTS.RIBBON_FOCUS_OPACITY : DIRECTED_CHORD_CONSTANTS.RIBBON_DIM_OPACITY);
                });
                arcPaths.attr('fill-opacity', (a) => (a.index === idx ? DIRECTED_CHORD_CONSTANTS.ARC_FOCUS_OPACITY : DIRECTED_CHORD_CONSTANTS.ARC_DIM_OPACITY));
            })
            .on('mouseleave', resetHighlight);

        ribbonPaths
            .on('mouseenter', function (_event, d) {
                const si = d.source.index;
                const ti = d.target.index;
                ribbonPaths.each(function (r) {
                    const el = d3.select(this);
                    const hit = r.source.index === si && r.target.index === ti;
                    el.attr('fill-opacity', hit ? DIRECTED_CHORD_CONSTANTS.RIBBON_FOCUS_OPACITY : DIRECTED_CHORD_CONSTANTS.RIBBON_DIM_OPACITY);
                });
                arcPaths.attr('fill-opacity', (a) => (a.index === si || a.index === ti ? DIRECTED_CHORD_CONSTANTS.ARC_FOCUS_OPACITY : DIRECTED_CHORD_CONSTANTS.ARC_DIM_OPACITY));
            })
            .on('mouseleave', resetHighlight);
    }
}
