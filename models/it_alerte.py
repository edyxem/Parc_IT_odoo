# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from datetime import date, timedelta


class ItAlerte(models.Model):
    _name = 'it.alerte'
    _description = "Alerte d'expiration"
    _inherit = ['mail.thread']
    _order = 'date_echeance asc'

    name = fields.Char(
        string='Intitulé', required=True, tracking=True)
    type_alerte = fields.Selection([
        ('garantie', 'Fin de garantie'),
        ('contrat', 'Expiration contrat'),
    ], string='Type', required=True, tracking=True)

    equipement_id = fields.Many2one(
        'it.equipement', string='Équipement', tracking=True)
    contrat_id = fields.Many2one(
        'it.contrat', string='Contrat', tracking=True)
    date_echeance = fields.Date(
        string="Date d'échéance", required=True, tracking=True)
    jours_avant = fields.Integer(
        string="Jours avant échéance",
        compute='_compute_jours_avant', store=True)

    state = fields.Selection([
        ('actif', 'Active'),
        ('traite', 'Traitée'),
        ('ignore', 'Ignorée'),
    ], string='État', default='actif', tracking=True)

    user_ids = fields.Many2many(
        'res.users', string='Destinataires',
        help='Utilisateurs à notifier')
    notes = fields.Text(string='Notes')

    # ── Urgence calculée ───────────────────────────────────────
    urgence = fields.Selection([
        ('critique', 'Critique'),
        ('haute', 'Haute'),
        ('normale', 'Normale'),
    ], string='Urgence', compute='_compute_urgence', store=True)

    # ── Onchange ───────────────────────────────────────────────
    @api.onchange('type_alerte')
    def _onchange_type_alerte(self):
        """Réinitialise les liens selon le type choisi."""
        if self.type_alerte == 'garantie':
            self.contrat_id = False
        elif self.type_alerte == 'contrat':
            self.equipement_id = False

    @api.onchange('equipement_id')
    def _onchange_equipement_id(self):
        """Pré-remplit la date d'échéance depuis la garantie."""
        if self.equipement_id:
            if self.equipement_id.state == 'retire':
                return {
                    'warning': {
                        'title': 'Équipement retiré',
                        'message': (
                            f'"{self.equipement_id.name}" est retiré '
                            f'du parc. Une alerte n\'est probablement '
                            f'pas nécessaire.'
                        )
                    }
                }
            if self.equipement_id.date_fin_garantie:
                self.date_echeance = self.equipement_id.date_fin_garantie
                self.type_alerte = 'garantie'
                # Warning si garantie déjà expirée
                if self.equipement_id.garantie_expiree:
                    return {
                        'warning': {
                            'title': 'Garantie déjà expirée',
                            'message': (
                                f'La garantie de '
                                f'"{self.equipement_id.name}" '
                                f'est déjà expirée depuis '
                                f'{abs(self.equipement_id.jours_avant_fin_garantie)} '
                                f'jour(s).'
                            )
                        }
                    }
            else:
                return {
                    'warning': {
                        'title': 'Pas de date de garantie',
                        'message': (
                            f'"{self.equipement_id.name}" n\'a pas '
                            f'de date de fin de garantie renseignée.'
                        )
                    }
                }

    @api.onchange('contrat_id')
    def _onchange_contrat_id(self):
        """Pré-remplit la date d'échéance depuis le contrat."""
        if self.contrat_id:
            if self.contrat_id.state == 'resilie':
                return {
                    'warning': {
                        'title': 'Contrat résilié',
                        'message': (
                            f'Le contrat "{self.contrat_id.name}" '
                            f'est résilié. Une alerte n\'est '
                            f'pas nécessaire.'
                        )
                    }
                }
            if self.contrat_id.state == 'renouvele':
                return {
                    'warning': {
                        'title': 'Contrat déjà renouvelé',
                        'message': (
                            f'Le contrat "{self.contrat_id.name}" '
                            f'a déjà été renouvelé.'
                        )
                    }
                }
            self.date_echeance = self.contrat_id.date_fin
            self.type_alerte = 'contrat'

    @api.onchange('date_echeance')
    def _onchange_date_echeance(self):
        if self.date_echeance:
            delta = (self.date_echeance - date.today()).days
            if delta < 0:
                return {
                    'warning': {
                        'title': 'Échéance dépassée',
                        'message': (
                            f'La date d\'échéance est déjà dépassée '
                            f'depuis {abs(delta)} jour(s). '
                            f'Cette alerte est peut-être obsolète.'
                        )
                    }
                }
            elif delta == 0:
                return {
                    'warning': {
                        'title': "Échéance aujourd'hui",
                        'message': "L'échéance est fixée à aujourd'hui !"
                    }
                }

    # ── Compute ────────────────────────────────────────────────
    @api.depends('date_echeance')
    def _compute_jours_avant(self):
        today = date.today()
        for rec in self:
            if rec.date_echeance:
                rec.jours_avant = (rec.date_echeance - today).days
            else:
                rec.jours_avant = 0

    @api.depends('jours_avant')
    def _compute_urgence(self):
        for rec in self:
            if rec.jours_avant <= 7:
                rec.urgence = 'critique'
            elif rec.jours_avant <= 30:
                rec.urgence = 'haute'
            else:
                rec.urgence = 'normale'

    # ── Contraintes ────────────────────────────────────────────
    @api.constrains('type_alerte', 'equipement_id', 'contrat_id')
    def _check_source(self):
        """Une alerte doit avoir exactement une source."""
        for rec in self:
            if rec.type_alerte == 'garantie' and not rec.equipement_id:
                raise ValidationError(
                    'Une alerte de type "Fin de garantie" '
                    'doit être liée à un équipement.'
                )
            if rec.type_alerte == 'contrat' and not rec.contrat_id:
                raise ValidationError(
                    'Une alerte de type "Expiration contrat" '
                    'doit être liée à un contrat.'
                )
            if rec.equipement_id and rec.contrat_id:
                raise ValidationError(
                    'Une alerte ne peut pas être liée '
                    'à la fois à un équipement et à un contrat.'
                )

    @api.constrains('date_echeance')
    def _check_date_echeance(self):
        for rec in self:
            if not rec.date_echeance:
                raise ValidationError(
                    "La date d'échéance est obligatoire."
                )

    # ── Actions ────────────────────────────────────────────────
    def action_traiter(self):
        for rec in self:
            if rec.state == 'traite':
                raise UserError('Cette alerte est déjà traitée.')
            if rec.state == 'ignore':
                raise UserError(
                    'Cette alerte a été ignorée. '
                    'Vous ne pouvez pas la traiter.'
                )
        self.write({'state': 'traite'})

    def action_ignorer(self):
        for rec in self:
            if rec.state == 'traite':
                raise UserError(
                    'Cette alerte est déjà traitée. '
                    'Impossible de l\'ignorer.'
                )
            if rec.state == 'ignore':
                raise UserError('Cette alerte est déjà ignorée.')
        self.write({'state': 'ignore'})

    def action_reactiver(self):
        """Remet une alerte ignorée ou traitée en active."""
        for rec in self:
            if rec.state == 'actif':
                raise UserError('Cette alerte est déjà active.')
            if rec.date_echeance < date.today():
                raise UserError(
                    'Impossible de réactiver une alerte '
                    'dont l\'échéance est dépassée.'
                )
        self.write({'state': 'actif'})

    # ── Cron ───────────────────────────────────────────────────
    @api.model
    def _cron_generer_alertes(self):
        """Tâche planifiée quotidienne à 8h."""
        delai = int(
            self.env['ir.config_parameter'].sudo().get_param(
                'it_parc.delai_alerte', default=30
            )
        )
        date_limite = date.today() + timedelta(days=delai)

        # ── Alertes garantie équipements ───────────────────────
        equipements = self.env['it.equipement'].search([
            ('date_fin_garantie', '<=', date_limite),
            ('date_fin_garantie', '>=', date.today()),
            ('state', '!=', 'retire'),
        ])
        for eq in equipements:
            existant = self.search([
                ('equipement_id', '=', eq.id),
                ('type_alerte', '=', 'garantie'),
                ('state', '=', 'actif'),
            ])
            if not existant:
                self.create({
                    'name': f'Garantie expirant : {eq.name}',
                    'type_alerte': 'garantie',
                    'equipement_id': eq.id,
                    'date_echeance': eq.date_fin_garantie,
                })

        # ── Alertes contrats fournisseurs ──────────────────────
        contrats = self.env['it.contrat'].search([
            ('date_fin', '<=', date_limite),
            ('date_fin', '>=', date.today()),
            ('state', '=', 'actif'),
        ])
        for ct in contrats:
            existant = self.search([
                ('contrat_id', '=', ct.id),
                ('type_alerte', '=', 'contrat'),
                ('state', '=', 'actif'),
            ])
            if not existant:
                self.create({
                    'name': f'Contrat expirant : {ct.name}',
                    'type_alerte': 'contrat',
                    'contrat_id': ct.id,
                    'date_echeance': ct.date_fin,
                })