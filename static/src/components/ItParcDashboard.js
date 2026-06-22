/** @odoo-module **/

import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class ItParcDashboard extends Component {
    static template = "it_parc.ItParcDashboard";

    setup() {
        this.action = useService("action");

        this.state = useState({
            loading: true,
            kpis: {
                total_equipements: 0,
                en_maintenance: 0,
                alertes_actives: 0,
                cout_mois: 0,
                brouillon: 0,
                retire: 0,
            },
            alertes_urgentes: [],
            chart_data: {
                labels: [],
                correctives: [],
                preventives: [],
            },
            repartition: [],
            last_updated: null,
        });

        onWillStart(async () => {
            await this._loadDashboardData();
        });

        onMounted(() => {
            this._refreshInterval = setInterval(async () => {
                await this._loadDashboardData();
            }, 5 * 60 * 1000);
        });
    }

    // ── Chargement via contrôleur HTTP ─────────────────────────
    async _loadDashboardData() {
        try {
            const response = await fetch('/it_parc/dashboard_data', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest',
                },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'call',
                    id: 1,
                    params: {},
                }),
            });

            const json = await response.json();

            if (json.error) {
                console.error('Dashboard IT Parc — erreur:', json.error);
                this.state.loading = false;
                return;
            }

            const result = json.result;
            this.state.kpis = result.kpis;
            this.state.alertes_urgentes = result.alertes_urgentes;
            this.state.chart_data = result.chart_data;
            this.state.repartition = result.repartition;
            this.state.last_updated = new Date().toLocaleTimeString('fr-FR');
            this.state.loading = false;
        } catch (e) {
            console.error('Dashboard IT Parc — erreur réseau:', e);
            this.state.loading = false;
        }
    }

    // ── Calcul des données du graphique SVG ────────────────────
    get chartConfig() {
    const width = 600;
    const height = 260;
    const padding = { top: 40, right: 20, bottom: 40, left: 50 };
    const plotWidth = width - padding.left - padding.right;
    const plotHeight = height - padding.top - padding.bottom;

    const { labels, correctives, preventives } = this.state.chart_data;
    const nbMois = labels.length || 6;

    // Valeur max réelle
    const maxVal = Math.max(0, ...correctives, ...preventives);

    // ── Calcul intelligent de l'échelle Y ──────────────────────
    let yMax;
    let nbTicks;
    if (maxVal === 0) {
        yMax = 5;
        nbTicks = 5;
    } else if (maxVal <= 5) {
        yMax = maxVal + 1;
        nbTicks = yMax;
    } else if (maxVal <= 10) {
        yMax = Math.ceil(maxVal / 2) * 2 + 2;
        nbTicks = 5;
    } else {
        yMax = Math.ceil(maxVal * 1.15 / 5) * 5;
        nbTicks = 5;
    }

    const groupWidth = plotWidth / nbMois;
    const barWidth = Math.min(18, groupWidth / 3);
    const barGap = 4;

    // Barres
    const bars = [];
    for (let i = 0; i < nbMois; i++) {
        const groupX = padding.left + i * groupWidth + groupWidth / 2;
        const corr = correctives[i] || 0;
        const prev = preventives[i] || 0;

        const hCorr = (corr / yMax) * plotHeight;
        bars.push({
            key: `c-${i}`,
            x: groupX - barWidth - barGap / 2,
            y: padding.top + plotHeight - hCorr,
            width: barWidth,
            height: hCorr,
            color: '#DC3545',
            value: corr,
            labelY: padding.top + plotHeight - hCorr - 6,
            labelX: groupX - barWidth / 2 - barGap / 2,
        });

        const hPrev = (prev / yMax) * plotHeight;
        bars.push({
            key: `p-${i}`,
            x: groupX + barGap / 2,
            y: padding.top + plotHeight - hPrev,
            width: barWidth,
            height: hPrev,
            color: '#198754',
            value: prev,
            labelY: padding.top + plotHeight - hPrev - 6,
            labelX: groupX + barWidth / 2 + barGap / 2,
        });
    }

    // Labels X (mois)
    const xLabels = labels.map((label, i) => ({
        key: `x-${i}`,
        x: padding.left + i * groupWidth + groupWidth / 2,
        y: padding.top + plotHeight + 20,
        text: label,
    }));

    // Ticks Y avec valeurs uniques entières
    const yTicks = [];
    for (let i = 0; i <= nbTicks; i++) {
        const val = Math.round((yMax * i) / nbTicks);
        const y = padding.top + plotHeight - (i / nbTicks) * plotHeight;
        yTicks.push({
            key: `y-${i}`,
            y: y,
            value: val,
            lineX1: padding.left,
            lineX2: width - padding.right,
        });
    }

    return {
        width,
        height,
        padding,
        plotWidth,
        plotHeight,
        bars,
        xLabels,
        yTicks,
        axisXY: padding.top + plotHeight,
    };
}
    // ── Navigation ─────────────────────────────────────────────
    async _openEquipements(domain = []) {
        await this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Équipements',
            res_model: 'it.equipement',
            view_mode: 'list,kanban,form',
            domain: domain,
        });
    }

    async _openInterventions(domain = []) {
        await this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Interventions',
            res_model: 'it.intervention',
            view_mode: 'list,form',
            domain: domain,
        });
    }

    async _openAlertes(domain = []) {
        await this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Alertes',
            res_model: 'it.alerte',
            view_mode: 'list,form',
            domain: domain,
        });
    }

    // ── Handlers KPIs ──────────────────────────────────────────
    onClickTotal() {
        this._openEquipements([['state', '!=', 'retire']]);
    }

    onClickMaintenance() {
        this._openEquipements([['state', '=', 'maintenance']]);
    }

    onClickAlertes() {
        this._openAlertes([['state', '=', 'actif']]);
    }

    onClickCout() {
        const today = new Date();
        const debut = new Date(today.getFullYear(), today.getMonth(), 1)
            .toISOString()
            .split('T')[0];
        this._openInterventions([
            ['state', '=', 'termine'],
            ['date_debut', '>=', debut],
        ]);
    }

    onClickAlerte(alerteId) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'it.alerte',
            res_id: alerteId,
            view_mode: 'form',
            views: [[false, 'form']],
        });
    }

    async onRefresh() {
        this.state.loading = true;
        await this._loadDashboardData();
    }

    // ── Utilitaires ────────────────────────────────────────────
    formatMoney(val) {
        return new Intl.NumberFormat('fr-FR', {
            style: 'decimal',
            maximumFractionDigits: 0,
        }).format(val) + ' FCFA';
    }

    urgenceClass(urgence) {
        return {
            critique: 'text-danger fw-bold',
            haute: 'text-warning fw-bold',
            normale: 'text-success',
        }[urgence] || '';
    }

    urgenceIcon(urgence) {
        return {
            critique: '🚨',
            haute: '⚠️',
            normale: '✅',
        }[urgence] || '🔔';
    }
}

registry.category('actions').add('it_parc_dashboard', ItParcDashboard);