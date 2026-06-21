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
    
    # ── Export Excel : Coûts de maintenance ───────────────────────
def action_export_couts_excel(self):
    import io
    import base64
    import xlsxwriter
    from datetime import datetime
    from collections import defaultdict

    output = io.BytesIO()
    workbook = xlsxwriter.Workbook({'in_memory': True})
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})

    # ── Formats ────────────────────────────────────────────────
    fmt_titre = workbook.add_format({
        'bold': True, 'font_size': 14,
        'font_color': '#FFFFFF', 'bg_color': '#1F4E79',
        'align': 'center', 'valign': 'vcenter',
    })
    fmt_header = workbook.add_format({
        'bold': True, 'font_color': '#FFFFFF',
        'bg_color': '#2E75B6', 'border': 1,
        'align': 'center', 'valign': 'vcenter',
        'text_wrap': True,
    })
    fmt_cell = workbook.add_format({
        'font_size': 9, 'border': 1, 'valign': 'vcenter',
    })
    fmt_cell_center = workbook.add_format({
        'font_size': 9, 'border': 1,
        'align': 'center', 'valign': 'vcenter',
    })
    fmt_money = workbook.add_format({
        'font_size': 9, 'border': 1,
        'num_format': '#,##0', 'align': 'right',
    })
    fmt_total = workbook.add_format({
        'bold': True, 'bg_color': '#D6E4F0',
        'border': 1, 'num_format': '#,##0',
        'align': 'right',
    })
    fmt_mois_header = workbook.add_format({
        'bold': True, 'bg_color': '#BDD7EE',
        'border': 1, 'align': 'center',
    })

    # ── Onglet 1 : Détail interventions ───────────────────────
    ws = workbook.add_worksheet('Détail interventions')
    ws.freeze_panes(2, 0)
    ws.set_zoom(85)

    ws.merge_range(
        'A1:J1',
        f'Coûts de maintenance — '
        f'{datetime.now().strftime("%d/%m/%Y %H:%M")}',
        fmt_titre
    )
    ws.set_row(0, 24)

    headers = [
        'Référence', 'Titre', 'Équipement',
        'Type', 'Technicien', 'Date début',
        'Date fin', 'Durée (h)', 'État', 'Coût (FCFA)',
    ]
    col_widths = [14, 35, 30, 14, 22, 16, 16, 10, 12, 16]
    for col, (h, w) in enumerate(zip(headers, col_widths)):
        ws.write(1, col, h, fmt_header)
        ws.set_column(col, col, w)
    ws.set_row(1, 28)

    interventions = self.sorted('date_debut', reverse=True)
    for row, inv in enumerate(interventions, start=2):
        ws.write(row, 0, inv.reference, fmt_cell_center)
        ws.write(row, 1, inv.name, fmt_cell)
        ws.write(
            row, 2, inv.equipement_id.name, fmt_cell)
        ws.write(
            row, 3, inv.type_intervention, fmt_cell_center)
        ws.write(
            row, 4,
            inv.technicien_id.name
            if inv.technicien_id else '—',
            fmt_cell
        )
        if inv.date_debut:
            ws.write(
                row, 5,
                inv.date_debut.strftime('%d/%m/%Y %H:%M'),
                fmt_cell_center
            )
        if inv.date_fin:
            ws.write(
                row, 6,
                inv.date_fin.strftime('%d/%m/%Y %H:%M'),
                fmt_cell_center
            )
        else:
            ws.write(row, 6, '—', fmt_cell_center)
        ws.write(
            row, 7,
            round(inv.duree_heures, 1),
            fmt_cell_center
        )
        ws.write(row, 8, inv.state, fmt_cell_center)
        ws.write(row, 9, inv.cout, fmt_money)

    last = 2 + len(interventions)
    ws.write(last, 7, 'TOTAL', fmt_total)
    ws.write(
        last, 8,
        round(sum(interventions.mapped('duree_heures')), 1),
        fmt_total
    )
    ws.write(
        last, 9,
        sum(interventions.mapped('cout')),
        fmt_total
    )

    # ── Onglet 2 : Tableau croisé par mois ────────────────────
    ws2 = workbook.add_worksheet('Coûts par mois')
    ws2.set_zoom(85)

    ws2.merge_range(
        'A1:F1',
        'Tableau des coûts de maintenance par mois',
        fmt_titre
    )
    ws2.set_row(0, 24)

    # Construire le tableau croisé mois x équipement
    data_mois = defaultdict(
        lambda: defaultdict(float))
    mois_set = set()
    eq_set = set()

    for inv in interventions:
        if inv.date_debut and inv.cout:
            mois = inv.date_debut.strftime('%Y-%m')
            eq_name = inv.equipement_id.name
            data_mois[mois][eq_name] += inv.cout
            mois_set.add(mois)
            eq_set.add(eq_name)

    mois_list = sorted(mois_set)
    eq_list = sorted(eq_set)

    # En-têtes
    ws2.write(1, 0, 'Équipement', fmt_header)
    ws2.set_column(0, 0, 35)
    for col, mois in enumerate(mois_list, start=1):
        # Formater le mois en "Jan 2026"
        from datetime import datetime as dt
        mois_fmt = dt.strptime(mois, '%Y-%m').strftime('%b %Y')
        ws2.write(1, col, mois_fmt, fmt_mois_header)
        ws2.set_column(col, col, 14)
    ws2.write(
        1, len(mois_list) + 1, 'TOTAL', fmt_header)
    ws2.set_row(1, 28)

    # Données
    for row, eq_name in enumerate(eq_list, start=2):
        ws2.write(row, 0, eq_name, fmt_cell)
        total_eq = 0
        for col, mois in enumerate(mois_list, start=1):
            val = data_mois[mois].get(eq_name, 0)
            total_eq += val
            if val:
                ws2.write(row, col, val, fmt_money)
            else:
                ws2.write(row, col, '—', fmt_cell_center)
        ws2.write(
            row, len(mois_list) + 1, total_eq, fmt_total)

    # Ligne totaux par mois
    last2 = 2 + len(eq_list)
    ws2.write(last2, 0, 'TOTAL', fmt_total)
    for col, mois in enumerate(mois_list, start=1):
        ws2.write(
            last2, col,
            sum(data_mois[mois].values()),
            fmt_total
        )
    ws2.write(
        last2, len(mois_list) + 1,
        sum(inv.cout for inv in interventions),
        fmt_total
    )

    workbook.close()
    output.seek(0)

    nom_fichier = (
        f'couts_maintenance_'
        f'{datetime.now().strftime("%Y%m%d_%H%M")}.xlsx'
    )
    attachment = self.env['ir.attachment'].create({
        'name': nom_fichier,
        'type': 'binary',
        'datas': base64.b64encode(output.read()),
        'mimetype': (
            'application/vnd.openxmlformats-'
            'officedocument.spreadsheetml.sheet'
        ),
    })
    return {
        'type': 'ir.actions.act_url',
        'url': f'/web/content/{attachment.id}?download=true',
        'target': 'self',
    }