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


    @api.model
    def _cron_maj_contrats_expires(self):
        """Passe automatiquement en 'expire' les contrats
    dont la date de fin est dépassée."""
        contrats = self.search([
        ('state', '=', 'actif'),
        ('date_fin', '<', date.today()),
        ])
        if contrats:
            contrats.write({'state': 'expire'})
    
    # ── Export Excel : Contrats expirant ──────────────────────────
def action_export_contrats_excel(self):
    import io
    import base64
    import xlsxwriter
    from datetime import datetime

    output = io.BytesIO()
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
        'font_size': 9, 'border': 1,
    })
    fmt_cell_center = workbook.add_format({
        'font_size': 9, 'border': 1, 'align': 'center',
    })
    fmt_money = workbook.add_format({
        'font_size': 9, 'border': 1,
        'num_format': '#,##0', 'align': 'right',
    })
    fmt_date = workbook.add_format({
        'font_size': 9, 'border': 1,
        'num_format': 'dd/mm/yyyy', 'align': 'center',
    })
    fmt_total = workbook.add_format({
        'bold': True, 'bg_color': '#D6E4F0',
        'border': 1, 'num_format': '#,##0',
        'align': 'right',
    })
    # Rouge : expire dans < 30j
    fmt_critique = workbook.add_format({
        'font_size': 9, 'border': 1,
        'bg_color': '#FFCCCC', 'font_color': '#C00000',
        'bold': True, 'align': 'center',
    })
    # Orange : expire dans 30-60j
    fmt_attention = workbook.add_format({
        'font_size': 9, 'border': 1,
        'bg_color': '#FCE4D6', 'font_color': '#833C00',
        'align': 'center',
    })
    # Vert : > 60j
    fmt_ok = workbook.add_format({
        'font_size': 9, 'border': 1,
        'bg_color': '#E2EFDA', 'font_color': '#375623',
        'align': 'center',
    })
    fmt_expire = workbook.add_format({
        'font_size': 9, 'border': 1,
        'bg_color': '#808080', 'font_color': '#FFFFFF',
        'align': 'center',
    })

    ws = workbook.add_worksheet('Contrats')
    ws.freeze_panes(2, 0)
    ws.set_zoom(90)

    ws.merge_range(
        'A1:I1',
        f'Suivi des contrats fournisseurs — '
        f'{datetime.now().strftime("%d/%m/%Y %H:%M")}',
        fmt_titre
    )
    ws.set_row(0, 24)

    headers = [
        'Référence', 'Intitulé', 'Type',
        'Fournisseur', 'Date début', 'Date fin',
        'Jours restants', 'Montant (FCFA)', 'État',
    ]
    col_widths = [14, 35, 16, 25, 12, 12, 14, 18, 14]
    for col, (h, w) in enumerate(zip(headers, col_widths)):
        ws.write(1, col, h, fmt_header)
        ws.set_column(col, col, w)
    ws.set_row(1, 28)

    # Trier par jours restants croissant
    contrats = self.sorted('jours_restants')
    for row, ct in enumerate(contrats, start=2):
        ws.write(row, 0, ct.reference, fmt_cell_center)
        ws.write(row, 1, ct.name, fmt_cell)
        ws.write(row, 2, ct.type_contrat, fmt_cell_center)
        ws.write(
            row, 3,
            ct.fournisseur_id.name
            if ct.fournisseur_id else '—',
            fmt_cell
        )
        if ct.date_debut:
            ws.write_datetime(
                row, 4,
                datetime.combine(
                    ct.date_debut, datetime.min.time()),
                fmt_date
            )
        if ct.date_fin:
            ws.write_datetime(
                row, 5,
                datetime.combine(
                    ct.date_fin, datetime.min.time()),
                fmt_date
            )

        # Coloration jours restants
        j = ct.jours_restants
        if ct.state in ('resilie', 'renouvele'):
            fmt_j = fmt_expire
        elif j < 0:
            fmt_j = fmt_expire
        elif j <= 30:
            fmt_j = fmt_critique
        elif j <= 60:
            fmt_j = fmt_attention
        else:
            fmt_j = fmt_ok

        ws.write(row, 6, j, fmt_j)
        ws.write(row, 7, ct.montant, fmt_money)

        # État coloré
        state_labels = {
            'actif': 'Actif',
            'expire': 'Expiré',
            'renouvele': 'Renouvelé',
            'resilie': 'Résilié',
        }
        state_fmts = {
            'actif': fmt_ok,
            'expire': fmt_critique,
            'renouvele': fmt_cell_center,
            'resilie': fmt_expire,
        }
        ws.write(
            row, 8,
            state_labels.get(ct.state, ct.state),
            state_fmts.get(ct.state, fmt_cell_center)
        )

    # Total montants
    last = 2 + len(contrats)
    ws.write(last, 6, 'TOTAL', fmt_total)
    ws.write(
        last, 7,
        sum(contrats.mapped('montant')),
        fmt_total
    )

    # ── Légende ────────────────────────────────────────────────
    ws.write(last + 2, 0, 'Légende :', fmt_header)
    ws.write(last + 3, 0, '≤ 30 jours', fmt_critique)
    ws.write(last + 3, 1, 'Critique — action immédiate', fmt_cell)
    ws.write(last + 4, 0, '31 à 60 jours', fmt_attention)
    ws.write(last + 4, 1, 'Attention — anticiper', fmt_cell)
    ws.write(last + 5, 0, '> 60 jours', fmt_ok)
    ws.write(last + 5, 1, 'OK', fmt_cell)
    ws.write(last + 6, 0, 'Expiré / Résilié', fmt_expire)
    ws.write(last + 6, 1, 'Inactif', fmt_cell)

    workbook.close()
    output.seek(0)

    nom_fichier = (
        f'suivi_contrats_'
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