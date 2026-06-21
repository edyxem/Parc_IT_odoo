# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError


class ItIntervention(models.Model):
    _name = 'it.intervention'
    _description = 'Intervention / Maintenance'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_debut desc'

    name = fields.Char(
        string='Titre', required=True, tracking=True)
    reference = fields.Char(
        string='Référence', readonly=True,
        copy=False, default='Nouveau')
    equipement_id = fields.Many2one(
        'it.equipement', string='Équipement',
        required=True, tracking=True)
    type_intervention = fields.Selection([
        ('corrective', 'Corrective'),
        ('preventive', 'Préventive'),
    ], string='Type', required=True,
        default='corrective', tracking=True)
    technicien_id = fields.Many2one(
        'hr.employee', string='Technicien', tracking=True)
    date_debut = fields.Datetime(
        string='Date début', required=True,
        default=fields.Datetime.now, tracking=True)
    date_fin = fields.Datetime(
        string='Date fin', tracking=True)
    duree_heures = fields.Float(
        string='Durée (heures)',
        compute='_compute_duree', store=True, digits=(6, 2))
    description = fields.Text(
        string='Description du problème')
    rapport = fields.Text(
        string="Rapport d'intervention")
    cout = fields.Float(
        string='Coût (FCFA)', digits=(16, 0), tracking=True)
    state = fields.Selection([
        ('planifie', 'Planifié'),
        ('en_cours', 'En cours'),
        ('termine', 'Terminé'),
        ('annule', 'Annulé'),
    ], string='État', default='planifie', tracking=True)

    # ── Séquence ───────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', 'Nouveau') == 'Nouveau':
                vals['reference'] = self.env['ir.sequence'].next_by_code(
                    'it.intervention') or 'Nouveau'
        return super().create(vals_list)

    # ── Onchange ───────────────────────────────────────────────
    @api.onchange('equipement_id')
    def _onchange_equipement_id(self):
        if self.equipement_id:
            # Warning si équipement retiré
            if self.equipement_id.state == 'retire':
                return {
                    'warning': {
                        'title': 'Équipement retiré',
                        'message': (
                            f'"{self.equipement_id.name}" est retiré '
                            f'du parc. Vous ne pouvez pas créer '
                            f'd\'intervention dessus.'
                        )
                    }
                }
            # Pré-remplir technicien avec l'utilisateur connecté
            if not self.technicien_id:
                employee = self.env['hr.employee'].search([
                    ('user_id', '=', self.env.uid)
                ], limit=1)
                if employee:
                    self.technicien_id = employee

    @api.onchange('date_debut', 'date_fin')
    def _onchange_dates(self):
        if self.date_debut and self.date_fin:
            if self.date_fin < self.date_debut:
                return {
                    'warning': {
                        'title': 'Dates invalides',
                        'message': (
                            'La date de fin ne peut pas être '
                            'antérieure à la date de début.'
                        )
                    }
                }

    @api.onchange('cout')
    def _onchange_cout(self):
        if self.cout and self.cout < 0:
            return {
                'warning': {
                    'title': 'Coût invalide',
                    'message': 'Le coût ne peut pas être négatif.'
                }
            }

    # ── Compute ────────────────────────────────────────────────
    @api.depends('date_debut', 'date_fin')
    def _compute_duree(self):
        for rec in self:
            if rec.date_debut and rec.date_fin:
                delta = rec.date_fin - rec.date_debut
                rec.duree_heures = delta.total_seconds() / 3600
            else:
                rec.duree_heures = 0.0

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

    @api.constrains('cout')
    def _check_cout(self):
        for rec in self:
            if rec.cout < 0:
                raise ValidationError(
                    'Le coût de l\'intervention ne peut pas '
                    'être négatif.'
                )

    @api.constrains('equipement_id')
    def _check_equipement_state(self):
        for rec in self:
            if rec.equipement_id.state == 'retire':
                raise ValidationError(
                    f'L\'équipement "{rec.equipement_id.name}" '
                    f'est retiré du parc. Impossible de créer '
                    f'une intervention.'
                )

    # ── Workflow ───────────────────────────────────────────────
    def action_demarrer(self):
        for rec in self:
            if rec.state != 'planifie':
                raise UserError(
                    'Seule une intervention planifiée '
                    'peut être démarrée.'
                )
            if rec.equipement_id.state == 'retire':
                raise UserError(
                    'L\'équipement est retiré du parc.'
                )
        self.write({'state': 'en_cours'})
        self.mapped('equipement_id').write({'state': 'maintenance'})

    def action_terminer(self):
        for rec in self:
            if rec.state != 'en_cours':
                raise UserError(
                    'Seule une intervention en cours '
                    'peut être terminée.'
                )
            if not rec.rapport:
                raise UserError(
                    'Veuillez renseigner le rapport '
                    'd\'intervention avant de terminer.'
                )
        self.write({
            'state': 'termine',
            'date_fin': fields.Datetime.now(),
        })
        for rec in self:
            eq = rec.equipement_id
            if eq.state == 'maintenance':
                new_state = 'affecte' if eq.employee_id else 'brouillon'
                eq.write({'state': new_state})

    def action_annuler(self):
        for rec in self:
            if rec.state == 'termine':
                raise UserError(
                    'Une intervention terminée ne peut '
                    'pas être annulée.'
                )
        self.write({'state': 'annule'})