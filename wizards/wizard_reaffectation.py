# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError


class WizardReaffectation(models.TransientModel):
    _name = 'wizard.reaffectation'
    _description = 'Wizard de réaffectation d\'équipement'

    equipement_id = fields.Many2one(
        'it.equipement', string='Équipement',
        required=True, readonly=True)

    # ── Affectation actuelle (readonly) ────────────────────────
    employee_actuel_id = fields.Many2one(
        'hr.employee', string='Employé actuel',
        related='equipement_id.employee_id', readonly=True)
    department_actuel_id = fields.Many2one(
        'hr.department', string='Département actuel',
        related='equipement_id.department_id', readonly=True)

    # ── Nouvelle affectation ───────────────────────────────────
    employee_id = fields.Many2one(
        'hr.employee', string='Nouvel employé', required=True)
    department_id = fields.Many2one(
        'hr.department', string='Nouveau département')
    date_debut = fields.Date(
        string='Date de début',
        required=True, default=fields.Date.today)
    motif = fields.Text(
        string='Motif de réaffectation', required=True)

    # ── Onchange ───────────────────────────────────────────────
    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id:
            self.department_id = self.employee_id.department_id
            # Warning si même employé
            if self.employee_id == self.employee_actuel_id:
                return {
                    'warning': {
                        'title': 'Même employé',
                        'message': (
                            f'"{self.employee_id.name}" est déjà '
                            f'l\'affectataire actuel de cet équipement.'
                        )
                    }
                }

    @api.onchange('date_debut')
    def _onchange_date_debut(self):
        if self.date_debut:
            # Chercher l'affectation active
            affectation_active = self.env['it.affectation'].search([
                ('equipement_id', '=', self.equipement_id.id),
                ('active', '=', True),
            ], limit=1)
            if affectation_active and affectation_active.date_debut:
                if self.date_debut < affectation_active.date_debut:
                    return {
                        'warning': {
                            'title': 'Date antérieure',
                            'message': (
                                f'La date choisie est antérieure à '
                                f'l\'affectation en cours '
                                f'({affectation_active.date_debut}).'
                            )
                        }
                    }

    # ── Contraintes ────────────────────────────────────────────
    @api.constrains('employee_id', 'employee_actuel_id')
    def _check_different_employee(self):
        for rec in self:
            if (rec.employee_id
                    and rec.employee_actuel_id
                    and rec.employee_id == rec.employee_actuel_id):
                raise ValidationError(
                    'Le nouvel employé est identique '
                    'à l\'affectataire actuel.'
                )

    @api.constrains('motif')
    def _check_motif(self):
        for rec in self:
            if rec.motif and len(rec.motif.strip()) < 10:
                raise ValidationError(
                    'Le motif de réaffectation doit contenir '
                    'au moins 10 caractères.'
                )

    # ── Action principale ──────────────────────────────────────
    def action_confirmer(self):
        self.ensure_one()

        eq = self.equipement_id

        if eq.state == 'retire':
            raise UserError(
                'Impossible de réaffecter un équipement retiré.'
            )

        # 1. Clôturer l'affectation active existante
        affectation_active = self.env['it.affectation'].search([
            ('equipement_id', '=', eq.id),
            ('active', '=', True),
        ])
        if affectation_active:
            affectation_active.write({
                'date_fin': self.date_debut,
                'active': False,
            })

        # 2. Créer la nouvelle affectation
        self.env['it.affectation'].create({
            'equipement_id': eq.id,
            'employee_id': self.employee_id.id,
            'department_id': self.department_id.id,
            'date_debut': self.date_debut,
            'motif': self.motif,
            'active': True,
        })

        # 3. Mettre à jour l'équipement
        eq.write({
            'employee_id': self.employee_id.id,
            'department_id': self.department_id.id,
            'state': 'affecte',
        })

        # 4. Message dans le chatter
        eq.message_post(
            body=(
                f'Réaffectation effectuée : '
                f'{self.employee_actuel_id.name or "Aucun"} → '
                f'{self.employee_id.name}<br/>'
                f'Motif : {self.motif}'
            )
        )

        return {'type': 'ir.actions.act_window_close'}