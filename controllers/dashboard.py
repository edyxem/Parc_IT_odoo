# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from datetime import date, datetime


class ItParcDashboardController(http.Controller):

    @http.route(
        '/it_parc/dashboard_data',
        auth='user',
        type='json',
        methods=['POST'],
        csrf=False,
    )
    def dashboard_data(self):
        """Retourne toutes les données du dashboard en un seul appel."""

        today = date.today()
        debut_mois = today.replace(day=1)

        # ── KPIs équipements ───────────────────────────────────
        Equipement = request.env['it.equipement']
        tous = Equipement.search([])
        actifs = tous.filtered(lambda e: e.state != 'retire')
        en_maintenance = tous.filtered(
            lambda e: e.state == 'maintenance')
        brouillon = tous.filtered(
            lambda e: e.state == 'brouillon')
        retire = tous.filtered(
            lambda e: e.state == 'retire')

        # ── KPI alertes ────────────────────────────────────────
        Alerte = request.env['it.alerte']
        alertes_actives = Alerte.search_count([
            ('state', '=', 'actif')
        ])

        # ── KPI coût du mois ───────────────────────────────────
        Intervention = request.env['it.intervention']
        interventions_mois = Intervention.search([
            ('state', '=', 'termine'),
            ('date_debut', '>=', datetime.combine(
                debut_mois, datetime.min.time())),
        ])
        cout_mois = sum(interventions_mois.mapped('cout'))

        # ── Alertes urgentes (10 max) ──────────────────────────
        alertes = Alerte.search([
            ('state', '=', 'actif'),
        ], order='jours_avant asc', limit=10)

        alertes_urgentes = []
        for al in alertes:
            source = ''
            if al.equipement_id:
                source = al.equipement_id.name
            elif al.contrat_id:
                source = al.contrat_id.name
            alertes_urgentes.append({
                'id': al.id,
                'name': al.name,
                'urgence': al.urgence,
                'jours_avant': al.jours_avant,
                'source': source,
            })

        # ── Graphique : 6 derniers mois ────────────────────────
        labels = []
        correctives = []
        preventives = []

        for i in range(5, -1, -1):
            if today.month - i <= 0:
                mois_num = today.month - i + 12
                annee = today.year - 1
            else:
                mois_num = today.month - i
                annee = today.year

            debut = datetime(annee, mois_num, 1)
            fin = datetime(annee + 1, 1, 1) \
                if mois_num == 12 \
                else datetime(annee, mois_num + 1, 1)

            labels.append(debut.strftime('%b %Y'))

            nb_corr = Intervention.search_count([
                ('type_intervention', '=', 'corrective'),
                ('date_debut', '>=', debut),
                ('date_debut', '<', fin),
                ('state', '!=', 'annule'),
            ])
            nb_prev = Intervention.search_count([
                ('type_intervention', '=', 'preventive'),
                ('date_debut', '>=', debut),
                ('date_debut', '<', fin),
                ('state', '!=', 'annule'),
            ])
            correctives.append(nb_corr)
            preventives.append(nb_prev)

        # ── Répartition par catégorie ──────────────────────────
        categories = [
            ('poste', 'Postes de travail'),
            ('serveur', 'Serveurs'),
            ('imprimante', 'Imprimantes'),
            ('reseau', 'Équipements réseau'),
            ('telephone', 'Téléphones IP'),
            ('autre', 'Autres'),
        ]
        repartition = []
        for code, label in categories:
            eqs_cat = tous.filtered(
                lambda e: e.categorie == code)
            if not eqs_cat:
                continue
            repartition.append({
                'code': code,
                'label': label,
                'total': len(eqs_cat),
                'affecte': len(eqs_cat.filtered(
                    lambda e: e.state == 'affecte')),
                'maintenance': len(eqs_cat.filtered(
                    lambda e: e.state == 'maintenance')),
                'retire': len(eqs_cat.filtered(
                    lambda e: e.state == 'retire')),
                'valeur': sum(eqs_cat.mapped('valeur_achat')),
            })

        return {
            'kpis': {
                'total_equipements': len(actifs),
                'en_maintenance': len(en_maintenance),
                'alertes_actives': alertes_actives,
                'cout_mois': cout_mois,
                'brouillon': len(brouillon),
                'retire': len(retire),
            },
            'alertes_urgentes': alertes_urgentes,
            'chart_data': {
                'labels': labels,
                'correctives': correctives,
                'preventives': preventives,
            },
            'repartition': repartition,
        }