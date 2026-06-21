# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from datetime import date


class ItEquipement(models.Model):
    _name = 'it.equipement'
    _description = 'Équipement informatique'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name asc'

    # ── Identification ─────────────────────────────────────────
    name = fields.Char(
        string='Nom', required=True, tracking=True)
    reference = fields.Char(
        string='Référence', readonly=True, copy=False,
        default='Nouveau')
    numero_serie = fields.Char(
        string='Numéro de série', tracking=True)
    categorie = fields.Selection([
        ('poste', 'Poste de travail'),
        ('serveur', 'Serveur'),
        ('imprimante', 'Imprimante'),
        ('reseau', 'Équipement réseau'),
        ('telephone', 'Téléphone IP'),
        ('autre', 'Autre'),
    ], string='Catégorie', required=True, tracking=True)

    # ── Caractéristiques techniques ────────────────────────────
    marque = fields.Char(string='Marque')
    modele = fields.Char(string='Modèle')
    processeur = fields.Char(string='Processeur')
    ram = fields.Char(string='RAM')
    stockage = fields.Char(string='Stockage')
    systeme_exploitation = fields.Char(string="Système d'exploitation")
    adresse_ip = fields.Char(string='Adresse IP')
    adresse_mac = fields.Char(string='Adresse MAC')

    # ── Achat et garantie ──────────────────────────────────────
    date_achat = fields.Date(string="Date d'achat", tracking=True)
    valeur_achat = fields.Float(
        string='Valeur d\'achat (FCFA)', digits=(16, 0))
    date_fin_garantie = fields.Date(
        string='Fin de garantie', tracking=True)
    fournisseur_id = fields.Many2one(
        'res.partner', string='Fournisseur',
        domain=[('supplier_rank', '>', 0)])
    facture_ref = fields.Char(string='Référence facture')

    # ── Localisation ───────────────────────────────────────────
    site = fields.Selection([
        ('abidjan1', 'Abidjan - Site 1'),
        ('abidjan2', 'Abidjan - Site 2'),
        ('bouake', 'Bouaké'),
    ], string='Site', tracking=True)
    localisation = fields.Char(
        string='Localisation', tracking=True,
        help='Bureau, salle serveur, etc.')

    # ── Affectation courante ───────────────────────────────────
    employee_id = fields.Many2one(
        'hr.employee', string='Employé affecté', tracking=True)
    department_id = fields.Many2one(
        'hr.department', string='Département', tracking=True)

    # ── État ───────────────────────────────────────────────────
    state = fields.Selection([
        ('brouillon', 'Brouillon'),
        ('affecte', 'Affecté'),
        ('maintenance', 'En maintenance'),
        ('retire', 'Retiré'),
    ], string='État', default='brouillon', tracking=True)

    # ── Relations ──────────────────────────────────────────────
    affectation_ids = fields.One2many(
        'it.affectation', 'equipement_id',
        string='Historique affectations')
    intervention_ids = fields.One2many(
        'it.intervention', 'equipement_id',
        string='Interventions')
    alerte_ids = fields.One2many(
        'it.alerte', 'equipement_id', string='Alertes')

    # ── Champs calculés ────────────────────────────────────────
    nb_interventions = fields.Integer(
        string='Nb interventions',
        compute='_compute_nb_interventions')
    cout_total_maintenance = fields.Float(
        string='Coût total maintenance (FCFA)',
        compute='_compute_cout_total', digits=(16, 0))
    garantie_expiree = fields.Boolean(
        string='Garantie expirée',
        compute='_compute_garantie', store=True)
    jours_avant_fin_garantie = fields.Integer(
        string='Jours avant fin garantie',
        compute='_compute_garantie', store=True)
    notes = fields.Text(string='Notes')
    image = fields.Image(
        string='Photo', max_width=256, max_height=256)

    # ── Séquence automatique ───────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', 'Nouveau') == 'Nouveau':
                vals['reference'] = self.env['ir.sequence'].next_by_code(
                    'it.equipement') or 'Nouveau'
        return super().create(vals_list)

    # ── Onchange : département auto depuis employé ─────────────
    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id:
            self.department_id = self.employee_id.department_id
            # Warning si équipement déjà affecté à quelqu'un d'autre
            if (self.state == 'affecte'
                    and self.employee_id != self._origin.employee_id
                    and self._origin.employee_id):
                return {
                    'warning': {
                        'title': 'Changement d\'affectation',
                        'message': (
                            f'Cet équipement est déjà affecté à '
                            f'{self._origin.employee_id.name}.\n'
                            f'Utilisez le bouton "Réaffecter" '
                            f'pour conserver l\'historique.'
                        )
                    }
                }
        else:
            self.department_id = False

    # ── Onchange : avertissement garantie à la saisie ──────────
    @api.onchange('date_fin_garantie')
    def _onchange_date_fin_garantie(self):
        if self.date_fin_garantie:
            delta = (self.date_fin_garantie - date.today()).days
            if delta < 0:
                return {
                    'warning': {
                        'title': 'Garantie expirée',
                        'message': (
                            f'La date de fin de garantie saisie est '
                            f'dépassée depuis {abs(delta)} jour(s).'
                        )
                    }
                }
            elif delta <= 30:
                return {
                    'warning': {
                        'title': 'Garantie bientôt expirée',
                        'message': (
                            f'La garantie expire dans {delta} jour(s). '
                            f'Pensez à anticiper le renouvellement.'
                        )
                    }
                }

    # ── Onchange : cohérence date achat / fin garantie ─────────
    @api.onchange('date_achat')
    def _onchange_date_achat(self):
        if self.date_achat and self.date_fin_garantie:
            if self.date_fin_garantie < self.date_achat:
                return {
                    'warning': {
                        'title': 'Dates incohérentes',
                        'message': (
                            'La date de fin de garantie est antérieure '
                            'à la date d\'achat.'
                        )
                    }
                }

    # ── Onchange : valeur d'achat négative ─────────────────────
    @api.onchange('valeur_achat')
    def _onchange_valeur_achat(self):
        if self.valeur_achat and self.valeur_achat < 0:
            return {
                'warning': {
                    'title': 'Valeur invalide',
                    'message': 'La valeur d\'achat ne peut pas être négative.'
                }
            }

    # ── Compute ────────────────────────────────────────────────
    @api.depends('intervention_ids')
    def _compute_nb_interventions(self):
        for rec in self:
            rec.nb_interventions = len(rec.intervention_ids)

    @api.depends('intervention_ids.cout')
    def _compute_cout_total(self):
        for rec in self:
            rec.cout_total_maintenance = sum(
                rec.intervention_ids.mapped('cout'))

    @api.depends('date_fin_garantie')
    def _compute_garantie(self):
        today = date.today()
        for rec in self:
            if rec.date_fin_garantie:
                delta = (rec.date_fin_garantie - today).days
                rec.jours_avant_fin_garantie = delta
                rec.garantie_expiree = delta < 0
            else:
                rec.jours_avant_fin_garantie = 0
                rec.garantie_expiree = False

    # ── Contraintes SQL ────────────────────────────────────────
    @api.constrains('numero_serie')
    def _check_numero_serie(self):
        for rec in self:
            if rec.numero_serie:
                doublon = self.search([
                    ('numero_serie', '=', rec.numero_serie),
                    ('id', '!=', rec.id),
                ])
                if doublon:
                    raise ValidationError(
                        f'Le numéro de série "{rec.numero_serie}" '
                        f'est déjà utilisé par "{doublon[0].name}".'
                    )

    @api.constrains('date_achat', 'date_fin_garantie')
    def _check_dates(self):
        for rec in self:
            if rec.date_achat and rec.date_fin_garantie:
                if rec.date_fin_garantie < rec.date_achat:
                    raise ValidationError(
                        'La date de fin de garantie doit être '
                        'postérieure à la date d\'achat.'
                    )

    @api.constrains('valeur_achat')
    def _check_valeur_achat(self):
        for rec in self:
            if rec.valeur_achat < 0:
                raise ValidationError(
                    'La valeur d\'achat ne peut pas être négative.'
                )

    # ── Workflow : gardes sur les transitions ──────────────────
    def action_affecter(self):
        for rec in self:
            if rec.state == 'retire':
                raise UserError(
                    f'L\'équipement "{rec.name}" est retiré '
                    f'et ne peut plus être affecté.'
                )
            if not rec.employee_id:
                raise UserError(
                    'Veuillez d\'abord affecter un employé '
                    'avant de changer l\'état.'
                )
        self.write({'state': 'affecte'})

    def action_maintenance(self):
        for rec in self:
            if rec.state == 'retire':
                raise UserError(
                    f'L\'équipement "{rec.name}" est retiré.'
                )
        self.write({'state': 'maintenance'})

    def action_retirer(self):
        for rec in self:
            interventions_actives = rec.intervention_ids.filtered(
                lambda i: i.state in ('planifie', 'en_cours')
            )
            if interventions_actives:
                raise UserError(
                    f'L\'équipement "{rec.name}" a des interventions '
                    f'en cours ou planifiées. Clôturez-les d\'abord.'
                )
        self.write({'state': 'retire'})

    def action_brouillon(self):
        for rec in self:
            if rec.state == 'retire':
                raise UserError(
                    'Un équipement retiré ne peut pas '
                    'revenir en brouillon.'
                )
        self.write({'state': 'brouillon'})

    def action_reaffecter(self):
        self.ensure_one()
        if self.state == 'retire':
            raise UserError(
                'Impossible de réaffecter un équipement retiré.'
            )
        return {
            'type': 'ir.actions.act_window',
            'name': 'Réaffecter l\'équipement',
            'res_model': 'wizard.reaffectation',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_equipement_id': self.id},
        }