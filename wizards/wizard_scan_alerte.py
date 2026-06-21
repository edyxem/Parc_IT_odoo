# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import date, timedelta


class WizardScanAlerte(models.TransientModel):
    _name = 'wizard.scan.alerte'
    _description = 'Wizard de scan manuel des alertes'

    delai_jours = fields.Integer(
        string='Délai d\'anticipation (jours)',
        required=True, default=30,
        help='Générer des alertes pour les échéances '
             'dans les X prochains jours.')
    inclure_garanties = fields.Boolean(
        string='Garanties équipements', default=True)
    inclure_contrats = fields.Boolean(
        string='Contrats fournisseurs', default=True)

    # ── Résultats ──────────────────────────────────────────────
    state = fields.Selection([
        ('draft', 'En attente'),
        ('done', 'Terminé'),
    ], default='draft')
    nb_alertes_creees = fields.Integer(
        string='Alertes créées', readonly=True)
    nb_alertes_existantes = fields.Integer(
        string='Alertes déjà existantes', readonly=True)
    rapport_texte = fields.Text(
        string='Détail', readonly=True)

    # ── Onchange ───────────────────────────────────────────────
    @api.onchange('delai_jours')
    def _onchange_delai_jours(self):
        if self.delai_jours <= 0:
            return {
                'warning': {
                    'title': 'Délai invalide',
                    'message': (
                        'Le délai doit être supérieur à 0 jour.'
                    )
                }
            }
        if self.delai_jours > 365:
            return {
                'warning': {
                    'title': 'Délai trop long',
                    'message': (
                        'Un délai supérieur à 365 jours '
                        'risque de générer beaucoup d\'alertes.'
                    )
                }
            }

    @api.onchange('inclure_garanties', 'inclure_contrats')
    def _onchange_inclure(self):
        if not self.inclure_garanties and not self.inclure_contrats:
            return {
                'warning': {
                    'title': 'Rien à scanner',
                    'message': (
                        'Veuillez sélectionner au moins '
                        'un type d\'alerte à scanner.'
                    )
                }
            }

    def action_lancer_scan(self):
        self.ensure_one()

        if self.delai_jours <= 0:
            raise UserError(
                'Le délai doit être supérieur à 0 jour.'
            )
        if not self.inclure_garanties and not self.inclure_contrats:
            raise UserError(
                'Sélectionnez au moins un type d\'alerte.'
            )

        date_limite = date.today() + timedelta(days=self.delai_jours)
        Alerte = self.env['it.alerte']
        nb_crees = 0
        nb_existants = 0
        rapport = []

        # ── Scan garanties ─────────────────────────────────────
        if self.inclure_garanties:
            equipements = self.env['it.equipement'].search([
                ('date_fin_garantie', '<=', date_limite),
                ('date_fin_garantie', '>=', date.today()),
                ('state', '!=', 'retire'),
            ])
            for eq in equipements:
                existant = Alerte.search([
                    ('equipement_id', '=', eq.id),
                    ('type_alerte', '=', 'garantie'),
                    ('state', '=', 'actif'),
                ], limit=1)
                if existant:
                    nb_existants += 1
                    rapport.append(
                        f'EXISTANT — Garantie : {eq.name} '
                        f'(alerte déjà active)'
                    )
                else:
                    Alerte.create({
                        'name': f'Garantie expirant : {eq.name}',
                        'type_alerte': 'garantie',
                        'equipement_id': eq.id,
                        'date_echeance': eq.date_fin_garantie,
                    })
                    nb_crees += 1
                    rapport.append(
                        f'CRÉÉ — Garantie : {eq.name} '
                        f'(expire le {eq.date_fin_garantie})'
                    )

        # ── Scan contrats ──────────────────────────────────────
        if self.inclure_contrats:
            contrats = self.env['it.contrat'].search([
                ('date_fin', '<=', date_limite),
                ('date_fin', '>=', date.today()),
                ('state', '=', 'actif'),
            ])
            for ct in contrats:
                existant = Alerte.search([
                    ('contrat_id', '=', ct.id),
                    ('type_alerte', '=', 'contrat'),
                    ('state', '=', 'actif'),
                ], limit=1)
                if existant:
                    nb_existants += 1
                    rapport.append(
                        f'EXISTANT — Contrat : {ct.name} '
                        f'(alerte déjà active)'
                    )
                else:
                    Alerte.create({
                        'name': f'Contrat expirant : {ct.name}',
                        'type_alerte': 'contrat',
                        'contrat_id': ct.id,
                        'date_echeance': ct.date_fin,
                    })
                    nb_crees += 1
                    rapport.append(
                        f'CRÉÉ — Contrat : {ct.name} '
                        f'(expire le {ct.date_fin})'
                    )

        rapport_final = (
            f'Scan terminé — '
            f'{nb_crees} alerte(s) créée(s), '
            f'{nb_existants} déjà existante(s).\n\n'
            + '\n'.join(rapport)
        )

        self.write({
            'state': 'done',
            'nb_alertes_creees': nb_crees,
            'nb_alertes_existantes': nb_existants,
            'rapport_texte': rapport_final,
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }