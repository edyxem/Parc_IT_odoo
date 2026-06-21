# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from datetime import date
from dateutil.relativedelta import relativedelta


class WizardRenouvellement(models.TransientModel):
    _name = 'wizard.renouvellement'
    _description = 'Wizard de renouvellement de contrat'

    contrat_id = fields.Many2one(
        'it.contrat', string='Contrat à renouveler',
        required=True, readonly=True)

    # ── Info contrat actuel (readonly) ─────────────────────────
    date_fin_actuelle = fields.Date(
        string='Date de fin actuelle',
        related='contrat_id.date_fin', readonly=True)
    montant_actuel = fields.Float(
        string='Montant actuel (FCFA)',
        related='contrat_id.montant', readonly=True,
        digits=(16, 0))
    fournisseur_id = fields.Many2one(
        'res.partner', string='Fournisseur',
        related='contrat_id.fournisseur_id', readonly=True)

    # ── Nouveau contrat ────────────────────────────────────────
    nouvelle_date_debut = fields.Date(
        string='Nouvelle date de début',
        required=True)
    nouvelle_date_fin = fields.Date(
        string='Nouvelle date de fin',
        required=True)
    nouveau_montant = fields.Float(
        string='Nouveau montant (FCFA)',
        digits=(16, 0))
    duree_mois = fields.Integer(
        string='Durée (mois)',
        compute='_compute_duree_mois')
    notes = fields.Text(string='Notes de renouvellement')
    copier_equipements = fields.Boolean(
        string='Copier les équipements couverts',
        default=True,
        help='Lier les mêmes équipements au nouveau contrat.')

    # ── Defaults intelligents ──────────────────────────────────
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        contrat_id = self.env.context.get('default_contrat_id')
        if contrat_id:
            contrat = self.env['it.contrat'].browse(contrat_id)
            if contrat.date_fin:
                # Nouvelle date début = lendemain de l'ancienne fin
                nouvelle_debut = contrat.date_fin + relativedelta(days=1)
                # Durée par défaut = même durée que l'ancien contrat
                if contrat.date_debut:
                    duree = relativedelta(
                        contrat.date_fin, contrat.date_debut)
                    nouvelle_fin = nouvelle_debut + duree
                else:
                    nouvelle_fin = nouvelle_debut + relativedelta(years=1)
                res['nouvelle_date_debut'] = nouvelle_debut
                res['nouvelle_date_fin'] = nouvelle_fin
                res['nouveau_montant'] = contrat.montant
        return res

    # ── Onchange ───────────────────────────────────────────────
    @api.onchange('nouvelle_date_debut', 'nouvelle_date_fin')
    def _onchange_dates(self):
        if self.nouvelle_date_debut and self.nouvelle_date_fin:
            if self.nouvelle_date_fin <= self.nouvelle_date_debut:
                return {
                    'warning': {
                        'title': 'Dates invalides',
                        'message': (
                            'La nouvelle date de fin doit être '
                            'postérieure à la date de début.'
                        )
                    }
                }
            # Warning si chevauchement avec l'ancien contrat
            if (self.date_fin_actuelle
                    and self.nouvelle_date_debut <= self.date_fin_actuelle):
                return {
                    'warning': {
                        'title': 'Chevauchement de dates',
                        'message': (
                            f'La nouvelle date de début '
                            f'({self.nouvelle_date_debut}) chevauche '
                            f'l\'ancien contrat '
                            f'(fin : {self.date_fin_actuelle}).'
                        )
                    }
                }

    @api.onchange('nouveau_montant')
    def _onchange_nouveau_montant(self):
        if self.nouveau_montant and self.nouveau_montant < 0:
            return {
                'warning': {
                    'title': 'Montant invalide',
                    'message': 'Le montant ne peut pas être négatif.'
                }
            }
        # Info si montant augmente de plus de 20%
        if (self.montant_actuel and self.nouveau_montant
                and self.montant_actuel > 0):
            hausse = (
                (self.nouveau_montant - self.montant_actuel)
                / self.montant_actuel * 100
            )
            if hausse > 20:
                return {
                    'warning': {
                        'title': 'Hausse importante',
                        'message': (
                            f'Le nouveau montant est en hausse '
                            f'de {hausse:.1f}% par rapport '
                            f'à l\'ancien contrat.'
                        )
                    }
                }

    # ── Compute ────────────────────────────────────────────────
    @api.depends('nouvelle_date_debut', 'nouvelle_date_fin')
    def _compute_duree_mois(self):
        for rec in self:
            if rec.nouvelle_date_debut and rec.nouvelle_date_fin:
                delta = relativedelta(
                    rec.nouvelle_date_fin,
                    rec.nouvelle_date_debut)
                rec.duree_mois = delta.years * 12 + delta.months
            else:
                rec.duree_mois = 0

    # ── Contraintes ────────────────────────────────────────────
    @api.constrains('nouvelle_date_debut', 'nouvelle_date_fin')
    def _check_dates(self):
        for rec in self:
            if (rec.nouvelle_date_debut
                    and rec.nouvelle_date_fin
                    and rec.nouvelle_date_fin <= rec.nouvelle_date_debut):
                raise ValidationError(
                    'La nouvelle date de fin doit être '
                    'postérieure à la date de début.'
                )

    @api.constrains('nouveau_montant')
    def _check_montant(self):
        for rec in self:
            if rec.nouveau_montant < 0:
                raise ValidationError(
                    'Le montant ne peut pas être négatif.'
                )

    # ── Action principale ──────────────────────────────────────
    def action_confirmer(self):
        self.ensure_one()
        contrat = self.contrat_id

        if contrat.state == 'resilie':
            raise UserError(
                'Un contrat résilié ne peut pas être renouvelé.'
            )
        if contrat.state == 'renouvele':
            raise UserError(
                'Ce contrat a déjà été renouvelé.'
            )

        # 1. Créer le nouveau contrat
        vals = {
            'name': f'{contrat.name} (Renouvellement)',
            'type_contrat': contrat.type_contrat,
            'fournisseur_id': contrat.fournisseur_id.id,
            'date_debut': self.nouvelle_date_debut,
            'date_fin': self.nouvelle_date_fin,
            'montant': self.nouveau_montant,
            'notes': self.notes or contrat.notes,
            'state': 'actif',
        }
        if self.copier_equipements:
            vals['equipement_ids'] = [
                (6, 0, contrat.equipement_ids.ids)
            ]

        nouveau_contrat = self.env['it.contrat'].create(vals)

        # 2. Passer l'ancien contrat en "Renouvelé"
        contrat.write({'state': 'renouvele'})

        # 3. Message dans le chatter de l'ancien contrat
        contrat.message_post(
            body=(
                f'Contrat renouvelé. '
                f'Nouveau contrat créé : '
                f'<a href="/odoo/it-contrats/{nouveau_contrat.id}">'
                f'{nouveau_contrat.name}</a><br/>'
                f'Période : {self.nouvelle_date_debut} → '
                f'{self.nouvelle_date_fin}<br/>'
                f'Montant : {self.nouveau_montant:,.0f} FCFA'
            )
        )

        # 4. Ouvrir le nouveau contrat
        return {
            'type': 'ir.actions.act_window',
            'name': 'Nouveau contrat',
            'res_model': 'it.contrat',
            'res_id': nouveau_contrat.id,
            'view_mode': 'form',
            'target': 'current',
        }