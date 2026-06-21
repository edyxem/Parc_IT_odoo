# -*- coding: utf-8 -*-
{
    'name': 'IT Parc - Gestion de parc informatique',
    'version': '18.0.1.0.0',
    'category': 'Technical',
    'summary': 'Gestion complète du parc informatique de TECHPARK CI',
    'description': """
        Module de gestion de parc informatique pour Odoo 18.
        - Inventaire des équipements
        - Affectation aux employés
        - Suivi des interventions
        - Gestion des contrats fournisseurs
        - Alertes automatiques de garantie
        - Rapports PDF et exports Excel
        - Dashboard OWL
    """,
    'author': 'TECHPARK CI',
    'website': 'https://www.techpark-ci.com',
    'license': 'LGPL-3',

    # ── Dépendances ──────────────────────────────────────────
    'depends': [
        'base',        # res.users, res.company
        'mail',        # mail.thread, mail.activity.mixin
        'hr',          # hr.employee, hr.department
        'contacts',    # res.partner (fournisseurs)
        'stock',       # product.template (optionnel)
        'purchase',    # contrats fournisseurs
        'account',     # coûts, valorisation
        'maintenance', # interventions
        'web',         # composants OWL, RPC
    ],

    # ── Données chargées à l'installation ────────────────────
    'data': [
        # Sécurité en premier (obligatoire)
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'security/ir_rules.xml',

        # Données de base
        'data/ir_sequence.xml',
        'data/ir_cron.xml',

        # Vues
        'views/equipement_views.xml',
        'views/affectation_views.xml',
        'views/intervention_views.xml',
        'views/contrat_views.xml',
        'views/alerte_views.xml',
        'views/menus.xml',

        # Wizards
        'wizards/wizard_reaffectation_views.xml',
        'wizards/wizard_import_csv_views.xml',
        'wizards/wizard_scan_alerte_views.xml',
        'wizards/wizard_renouvellement_views.xml',

        # Rapports PDF
        'report/report_actions.xml',
        'report/report_equipement.xml',
        'report/report_inventaire.xml',
        'report/report_maintenance.xml',
    ],

    # ── Données de démo ──────────────────────────────────────
    'demo': [
        'data/it_parc_demo.xml',
    ],

    # ── Assets front-end (dashboard OWL) ─────────────────────
    'assets': {
        'web.assets_backend': [
            'it_parc/static/src/components/ItParcDashboard.js',
            'it_parc/static/src/components/ItParcDashboard.xml',
            'it_parc/static/src/components/dashboard.scss',
        ],
    },

    'installable': True,
    'application': True,
    'auto_install': False,
}