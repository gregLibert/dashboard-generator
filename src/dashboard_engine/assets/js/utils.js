const UTILS_CONSTANTS = {
    NUMBER_LOCALE: 'fr-FR',
};

const YEAR_COMPARE_LABELS = {
    N_SUFFIX: ' (N)',
    N1_SUFFIX: ' (N-1)',
};

const MONTH_LABELS_FR = [
    'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
    'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre'
];

const NUMBER_FORMAT_FR = new Intl.NumberFormat(UTILS_CONSTANTS.NUMBER_LOCALE, { maximumFractionDigits: 0 });

const Utils = {
    moisFR: MONTH_LABELS_FR,
    fmtNumber: NUMBER_FORMAT_FR,

    getQuarter(m) {
        return Math.ceil(m / 3);
    },

    getSemester(m) {
        return m <= 6 ? 1 : 2;
    },

    /**
     * Human-readable label for the selected period (French labels match legacy configs).
     */
    labelForPeriod(type, year, value) {
        switch (type) {
            case 'annee':
                return `Année ${year}`;
            case 'mois': {
                const index = (value || 0) - 1;
                const label = MONTH_LABELS_FR[index] || value;
                return `${label} ${year}`;
            }
            case 'trimestre':
                return `T${value} ${year}`;
            case 'semestre':
                return `S${value} ${year}`;
            default:
                return `${year}`;
        }
    },

    getVal(row, mappingKey, mappingConfig) {
        if (!mappingConfig) return undefined;
        const colName = mappingConfig[mappingKey];
        if (!colName) return undefined;
        return row[colName];
    },

    /**
     * Rows must include numeric `year` from BaseWidget.processData.
     */
    extractRowsForCalendarYear(rows, year) {
        return rows.filter((d) => !d.year || d.year === year);
    },

    /**
     * Years to render side-by-side when YoY is enabled (N-1 then N).
     */
    calendarYearsForYoYChart(anchorYear, yoyEnabled) {
        if (!yoyEnabled) {
            return [anchorYear];
        }
        return [anchorYear - 1, anchorYear];
    },

    /**
     * Subtitle next to the calendar year in paired YoY panels.
     */
    formatYoYChartTitleSuffix(yoyEnabled, plotYear, anchorYear) {
        if (!yoyEnabled) {
            return '';
        }
        return plotYear === anchorYear ? YEAR_COMPARE_LABELS.N_SUFFIX : YEAR_COMPARE_LABELS.N1_SUFFIX;
    },
};
