# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ItAffectation(models.Model):
    _name = 'it.affectation'
    _description = 'Historique des affectations'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_debut desc'

    equipement_id = fields.Many2one(
        'it.equipement', string='Équipement',
        required=True, ondelete='cascade', tracking=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Employé',
        required=True, tracking=True)
    department_id = fields.Many2one(
        'hr.department', string='Département', tracking=True)
    date_debut = fields.Date(
        string='Date de début', required=True,
        default=fields.Date.today, tracking=True)
    date_fin = fields.Date(
        string='Date de fin', tracking=True)
    motif = fields.Text(string='Motif', tracking=True)
    active = fields.Boolean(
        string='Active', default=True, tracking=True)
    user_id = fields.Many2one(
        'res.users', string='Enregistré par',
        default=lambda self: self.env.user, readonly=True)
    duree_jours = fields.Integer(
        string='Durée (jours)',
        compute='_compute_duree', store=True)

    # ── Onchange ───────────────────────────────────────────────
    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id:
            self.department_id = self.employee_id.department_id

    @api.onchange('date_fin')
    def _onchange_date_fin(self):
        if self.date_debut and self.date_fin:
            if self.date_fin < self.date_debut:
                return {
                    'warning': {
                        'title': 'Date invalide',
                        'message': (
                            'La date de fin ne peut pas être '
                            'antérieure à la date de début.'
                        )
                    }
                }

    # ── Compute ────────────────────────────────────────────────
    @api.depends('date_debut', 'date_fin')
    def _compute_duree(self):
        for rec in self:
            if rec.date_debut and rec.date_fin:
                rec.duree_jours = (rec.date_fin - rec.date_debut).days
            elif rec.date_debut:
                from datetime import date
                rec.duree_jours = (date.today() - rec.date_debut).days
            else:
                rec.duree_jours = 0

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

    @api.constrains('equipement_id', 'active')
    def _check_affectation_unique(self):
        """Un équipement ne peut avoir qu'une affectation active."""
        for rec in self:
            if rec.active:
                doublon = self.search([
                    ('equipement_id', '=', rec.equipement_id.id),
                    ('active', '=', True),
                    ('id', '!=', rec.id),
                ])
                if doublon:
                    raise ValidationError(
                        f'L\'équipement "{rec.equipement_id.name}" '
                        f'a déjà une affectation active '
                        f'pour {doublon[0].employee_id.name}.\n'
                        f'Clôturez-la d\'abord.'
                    )

    def action_cloturer(self):
        for rec in self:
            if not rec.active:
                raise ValidationError(
                    'Cette affectation est déjà clôturée.'
                )
        self.write({
            'date_fin': fields.Date.today(),
            'active': False,
        })