# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from datetime import date


class ItContrat(models.Model):
    _name = 'it.contrat'
    _description = 'Contrat fournisseur'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_fin asc'

    name = fields.Char(
        string='Intitulé du contrat',
        required=True, tracking=True)
    reference = fields.Char(
        string='Référence', readonly=True,
        copy=False, default='Nouveau')
    type_contrat = fields.Selection([
        ('maintenance', 'Maintenance'),
        ('licence', 'Licence logicielle'),
        ('support', 'Support technique'),
        ('autre', 'Autre'),
    ], string='Type', required=True, tracking=True)
    fournisseur_id = fields.Many2one(
        'res.partner', string='Fournisseur', required=True,
        domain=[('supplier_rank', '>', 0)], tracking=True)
    date_debut = fields.Date(
        string='Date de début', required=True, tracking=True)
    date_fin = fields.Date(
        string='Date de fin', required=True, tracking=True)
    montant = fields.Float(
        string='Montant (FCFA)', digits=(16, 0), tracking=True)
    equipement_ids = fields.Many2many(
        'it.equipement', string='Équipements couverts',
        relation='it_contrat_equipement_rel',
        column1='contrat_id', column2='equipement_id')
    notes = fields.Text(string='Notes')
    state = fields.Selection([
        ('actif', 'Actif'),
        ('expire', 'Expiré'),
        ('renouvele', 'Renouvelé'),
        ('resilie', 'Résilié'),
    ], string='État', default='actif', tracking=True)
    jours_restants = fields.Integer(
        string='Jours restants',
        compute='_compute_jours_restants', store=True)
    expire_bientot = fields.Boolean(
        string='Expire bientôt',
        compute='_compute_jours_restants', store=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', 'Nouveau') == 'Nouveau':
                vals['reference'] = self.env['ir.sequence'].next_by_code(
                    'it.contrat') or 'Nouveau'
        return super().create(vals_list)

    # ── Onchange ───────────────────────────────────────────────
    @api.onchange('date_debut', 'date_fin')
    def _onchange_dates(self):
        if self.date_debut and self.date_fin:
            if self.date_fin < self.date_debut:
                return {
                    'warning': {
                        'title': 'Dates invalides',
                        'message': (
                            'La date de fin doit être postérieure '
                            'à la date de début du contrat.'
                        )
                    }
                }
            delta = (self.date_fin - date.today()).days
            if delta < 0:
                return {
                    'warning': {
                        'title': 'Contrat déjà expiré',
                        'message': (
                            f'Ce contrat a expiré '
                            f'il y a {abs(delta)} jour(s).'
                        )
                    }
                }
            elif delta <= 30:
                return {
                    'warning': {
                        'title': 'Expiration proche',
                        'message': (
                            f'Ce contrat expire dans {delta} jour(s). '
                            f'Anticipez le renouvellement.'
                        )
                    }
                }

    @api.onchange('montant')
    def _onchange_montant(self):
        if self.montant and self.montant < 0:
            return {
                'warning': {
                    'title': 'Montant invalide',
                    'message': 'Le montant ne peut pas être négatif.'
                }
            }

    # ── Compute ────────────────────────────────────────────────
    @api.depends('date_fin')
    def _compute_jours_restants(self):
        today = date.today()
        for rec in self:
            if rec.date_fin:
                delta = (rec.date_fin - today).days
                rec.jours_restants = delta
                rec.expire_bientot = 0 <= delta <= 60
                if delta < 0 and rec.state == 'actif':
                    rec.state = 'expire'
            else:
                rec.jours_restants = 0
                rec.expire_bientot = False

    # ── Contraintes ────────────────────────────────────────────
    @api.constrains('date_debut', 'date_fin')
    def _check_dates(self):
        for rec in self:
            if rec.date_debut and rec.date_fin:
                if rec.date_fin < rec.date_debut:
                    raise ValidationError(
                        'La date de fin doit être postérieure '
                        'à la date de début.'
                    )

    @api.constrains('montant')
    def _check_montant(self):
        for rec in self:
            if rec.montant < 0:
                raise ValidationError(
                    'Le montant du contrat ne peut pas être négatif.'
                )

    # ── Actions ────────────────────────────────────────────────
    def action_renouveler(self):
        self.ensure_one()
        if self.state == 'resilie':
            raise UserError(
                'Un contrat résilié ne peut pas être renouvelé.'
            )
        if self.state == 'renouvele':
            raise UserError(
                'Ce contrat a déjà été renouvelé.'
            )
        return {
            'type': 'ir.actions.act_window',
            'name': 'Renouveler le contrat',
            'res_model': 'wizard.renouvellement',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_contrat_id': self.id},
        }

    def action_resilier(self):
        for rec in self:
            if rec.state == 'resilie':
                raise UserError('Ce contrat est déjà résilié.')
        self.write({'state': 'resilie'})