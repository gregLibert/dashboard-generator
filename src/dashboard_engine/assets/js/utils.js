// ==========================================
// UTILS
// ==========================================
const Utils = {
    moisFR: ['Janvier','Février','Mars','Avril','Mai','Juin','Juillet','Août','Septembre','Octobre','Novembre','Décembre'],
    fmtNumber: new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 0 }),
    
    getQuarter(m) { return Math.ceil(m / 3); },
    getSemester(m) { return m <= 6 ? 1 : 2; },
    
    labelForPeriod(type, year, value) {
        if (type === 'annee') return `Année ${year}`;
        if (type === 'mois') return `${this.moisFR[value-1]} ${year}`;
        if (type === 'trimestre') return `T${value} ${year}`;
        if (type === 'semestre') return `S${value} ${year}`;
        return `${year}`;
    },

    getVal(row, mappingKey, mappingConfig) {
        const colName = mappingConfig[mappingKey];
        return row[colName];
    }
};