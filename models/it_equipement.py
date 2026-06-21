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
    systeme_exploitation = fields.Char(
        string="Système d'exploitation")
    adresse_ip = fields.Char(string='Adresse IP')
    adresse_mac = fields.Char(string='Adresse MAC')

    # ── Achat et garantie ──────────────────────────────────────
    date_achat = fields.Date(
        string="Date d'achat", tracking=True)
    valeur_achat = fields.Float(
        string="Valeur d'achat (FCFA)", digits=(16, 0))
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

    # ── Onchange ───────────────────────────────────────────────
    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id:
            self.department_id = self.employee_id.department_id
            if (self.state == 'affecte'
                    and self.employee_id != self._origin.employee_id
                    and self._origin.employee_id):
                return {
                    'warning': {
                        'title': "Changement d'affectation",
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

    @api.onchange('date_achat')
    def _onchange_date_achat(self):
        if self.date_achat and self.date_fin_garantie:
            if self.date_fin_garantie < self.date_achat:
                return {
                    'warning': {
                        'title': 'Dates incohérentes',
                        'message': (
                            "La date de fin de garantie est antérieure "
                            "à la date d'achat."
                        )
                    }
                }

    @api.onchange('valeur_achat')
    def _onchange_valeur_achat(self):
        if self.valeur_achat and self.valeur_achat < 0:
            return {
                'warning': {
                    'title': 'Valeur invalide',
                    'message': "La valeur d'achat ne peut pas être négative."
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

    # ── Contraintes ────────────────────────────────────────────
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
                        "La date de fin de garantie doit être "
                        "postérieure à la date d'achat."
                    )

    @api.constrains('valeur_achat')
    def _check_valeur_achat(self):
        for rec in self:
            if rec.valeur_achat < 0:
                raise ValidationError(
                    "La valeur d'achat ne peut pas être négative."
                )

    # ── Workflow ───────────────────────────────────────────────
    def action_affecter(self):
        for rec in self:
            if rec.state == 'retire':
                raise UserError(
                    f'L\'équipement "{rec.name}" est retiré '
                    f'et ne peut plus être affecté.'
                )
            if not rec.employee_id:
                raise UserError(
                    "Veuillez d'abord affecter un employé "
                    "avant de changer l'état."
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
                    "Un équipement retiré ne peut pas "
                    "revenir en brouillon."
                )
        self.write({'state': 'brouillon'})

    def action_reaffecter(self):
        self.ensure_one()
        if self.state == 'retire':
            raise UserError(
                "Impossible de réaffecter un équipement retiré."
            )
        return {
            'type': 'ir.actions.act_window',
            'name': "Réaffecter l'équipement",
            'res_model': 'wizard.reaffectation',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_equipement_id': self.id},
        }

    # ── Export Excel : Inventaire complet ──────────────────────
    def action_export_inventaire_excel(self):
        import io
        import base64
        import xlsxwriter
        from datetime import datetime

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})

        fmt_titre = workbook.add_format({
            'bold': True, 'font_size': 14,
            'font_color': '#FFFFFF', 'bg_color': '#1F4E79',
            'align': 'center', 'valign': 'vcenter',
        })
        fmt_header = workbook.add_format({
            'bold': True, 'font_size': 10,
            'font_color': '#FFFFFF', 'bg_color': '#2E75B6',
            'align': 'center', 'valign': 'vcenter',
            'border': 1, 'text_wrap': True,
        })
        fmt_cell = workbook.add_format({
            'font_size': 9, 'border': 1,
            'valign': 'vcenter',
        })
        fmt_cell_center = workbook.add_format({
            'font_size': 9, 'border': 1,
            'align': 'center', 'valign': 'vcenter',
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
            'bold': True, 'font_size': 10,
            'bg_color': '#D6E4F0', 'border': 1,
            'num_format': '#,##0', 'align': 'right',
        })
        fmt_rouge = workbook.add_format({
            'font_size': 9, 'border': 1,
            'font_color': '#C00000', 'bold': True,
            'align': 'center',
        })
        fmt_vert = workbook.add_format({
            'font_size': 9, 'border': 1,
            'font_color': '#375623', 'bg_color': '#E2EFDA',
            'align': 'center',
        })
        fmt_orange = workbook.add_format({
            'font_size': 9, 'border': 1,
            'font_color': '#833C00', 'bg_color': '#FCE4D6',
            'align': 'center',
        })

        categories = [
            ('poste', 'Postes de travail'),
            ('serveur', 'Serveurs'),
            ('imprimante', 'Imprimantes'),
            ('reseau', 'Équipements réseau'),
            ('telephone', 'Téléphones IP'),
            ('autre', 'Autres'),
        ]

        for code_cat, label_cat in categories:
            equipements = self.filtered(
                lambda e: e.categorie == code_cat
            ).sorted('name')

            if not equipements:
                continue

            ws = workbook.add_worksheet(label_cat[:31])
            ws.set_zoom(85)
            ws.freeze_panes(3, 0)

            ws.merge_range(
                'A1:N1',
                f'Inventaire — {label_cat} — '
                f'Généré le {datetime.now().strftime("%d/%m/%Y %H:%M")}',
                fmt_titre
            )
            ws.set_row(0, 24)

            headers = [
                'Référence', 'Nom', 'Marque', 'Modèle',
                'N° Série', 'Site', 'Localisation',
                'Employé affecté', 'Date achat',
                'Fin garantie', 'Valeur achat (FCFA)',
                'Coût maintenance (FCFA)', 'Nb interventions',
                'État',
            ]
            col_widths = [
                14, 35, 12, 18, 18, 14, 20,
                22, 12, 12, 18, 20, 15, 14,
            ]
            for col, (h, w) in enumerate(zip(headers, col_widths)):
                ws.write(1, col, h, fmt_header)
                ws.set_column(col, col, w)
            ws.set_row(1, 30)

            for row, eq in enumerate(equipements, start=2):
                ws.write(row, 0, eq.reference, fmt_cell_center)
                ws.write(row, 1, eq.name, fmt_cell)
                ws.write(row, 2, eq.marque or '', fmt_cell)
                ws.write(row, 3, eq.modele or '', fmt_cell)
                ws.write(row, 4, eq.numero_serie or '', fmt_cell_center)
                ws.write(row, 5, eq.site or '', fmt_cell_center)
                ws.write(row, 6, eq.localisation or '', fmt_cell)
                ws.write(
                    row, 7,
                    eq.employee_id.name if eq.employee_id else '—',
                    fmt_cell
                )
                if eq.date_achat:
                    ws.write_datetime(
                        row, 8,
                        datetime.combine(
                            eq.date_achat, datetime.min.time()),
                        fmt_date
                    )
                else:
                    ws.write(row, 8, '—', fmt_cell_center)

                if eq.date_fin_garantie:
                    fmt_g = fmt_rouge if eq.garantie_expiree \
                        else fmt_date
                    ws.write_datetime(
                        row, 9,
                        datetime.combine(
                            eq.date_fin_garantie,
                            datetime.min.time()),
                        fmt_g
                    )
                else:
                    ws.write(row, 9, '—', fmt_cell_center)

                ws.write(row, 10, eq.valeur_achat or 0, fmt_money)
                ws.write(row, 11, eq.cout_total_maintenance, fmt_money)
                ws.write(row, 12, eq.nb_interventions, fmt_cell_center)

                state_labels = {
                    'brouillon': 'Brouillon',
                    'affecte': 'Affecté',
                    'maintenance': 'En maintenance',
                    'retire': 'Retiré',
                }
                state_fmts = {
                    'brouillon': fmt_cell_center,
                    'affecte': fmt_vert,
                    'maintenance': fmt_orange,
                    'retire': fmt_rouge,
                }
                ws.write(
                    row, 13,
                    state_labels.get(eq.state, eq.state),
                    state_fmts.get(eq.state, fmt_cell_center)
                )

            last_row = 2 + len(equipements)
            ws.write(last_row, 9, 'TOTAL', fmt_total)
            ws.write(
                last_row, 10,
                sum(equipements.mapped('valeur_achat')),
                fmt_total
            )
            ws.write(
                last_row, 11,
                sum(equipements.mapped('cout_total_maintenance')),
                fmt_total
            )

        # ── Onglet résumé global ───────────────────────────────
        ws_resume = workbook.add_worksheet('Résumé global')
        ws_resume.set_zoom(90)

        ws_resume.merge_range(
            'A1:G1',
            f'Inventaire global du parc informatique — '
            f'{datetime.now().strftime("%d/%m/%Y")}',
            fmt_titre
        )
        ws_resume.set_row(0, 24)

        headers_resume = [
            'Catégorie', 'Total', 'Affectés',
            'En maintenance', 'Retirés',
            'Valeur totale (FCFA)', 'Coût maintenance (FCFA)',
        ]
        col_widths_resume = [25, 10, 12, 16, 10, 22, 22]
        for col, (h, w) in enumerate(
                zip(headers_resume, col_widths_resume)):
            ws_resume.write(1, col, h, fmt_header)
            ws_resume.set_column(col, col, w)
        ws_resume.set_row(1, 28)

        total_eq = len(self)
        total_val = 0
        total_cout = 0
        row = 2
        for code_cat, label_cat in categories:
            eqs_cat = self.filtered(
                lambda e: e.categorie == code_cat)
            if not eqs_cat:
                continue
            val = sum(eqs_cat.mapped('valeur_achat'))
            cout = sum(eqs_cat.mapped('cout_total_maintenance'))
            total_val += val
            total_cout += cout
            ws_resume.write(row, 0, label_cat, fmt_cell)
            ws_resume.write(row, 1, len(eqs_cat), fmt_cell_center)
            ws_resume.write(
                row, 2,
                len(eqs_cat.filtered(
                    lambda e: e.state == 'affecte')),
                fmt_vert
            )
            ws_resume.write(
                row, 3,
                len(eqs_cat.filtered(
                    lambda e: e.state == 'maintenance')),
                fmt_orange
            )
            ws_resume.write(
                row, 4,
                len(eqs_cat.filtered(
                    lambda e: e.state == 'retire')),
                fmt_rouge
            )
            ws_resume.write(row, 5, val, fmt_money)
            ws_resume.write(row, 6, cout, fmt_money)
            row += 1

        ws_resume.write(row, 0, 'TOTAL GÉNÉRAL', fmt_total)
        ws_resume.write(row, 1, total_eq, fmt_total)
        ws_resume.write(row, 5, total_val, fmt_total)
        ws_resume.write(row, 6, total_cout, fmt_total)

        workbook.close()
        output.seek(0)

        nom_fichier = (
            f'inventaire_it_parc_'
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