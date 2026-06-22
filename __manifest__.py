# -*- coding: utf-8 -*-
{
    'name': 'IT Parc',
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
    'author': 'Tossou',
    'website': 'https://www.techpark-ci.com',
    'license': 'LGPL-3',

    'depends': [
        'base',
        'mail',
        'hr',
        'stock',
        'contacts',
        'web',
    ],

    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'security/ir_rules.xml',

        'data/ir_sequence.xml',
        'data/ir_cron.xml',
        
        'views/it_parc_menus.xml',
        'views/it_parc_actions.xml',

        'views/dashboard_action.xml',

        'views/equipement_views.xml',
        'views/affectation_views.xml',
        'views/intervention_views.xml',
        'views/contrat_views.xml',
        'views/alerte_views.xml',
        

        'wizards/wizard_reaffectation_views.xml',
        'wizards/wizard_import_csv_views.xml',
        'wizards/wizard_scan_alerte_views.xml',
        'wizards/wizard_renouvellement_views.xml',

        'report/report_actions.xml',
        'report/report_fiche_equipement.xml',
        'report/report_inventaire.xml',
        'report/report_maintenance.xml',
    ],

    'demo': [
        'data/it_parc_demo.xml',
    ],

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
