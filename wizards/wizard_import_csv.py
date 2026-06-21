# -*- coding: utf-8 -*-
import base64
import csv
import io
from odoo import models, fields, api
from odoo.exceptions import UserError


class WizardImportCsv(models.TransientModel):
    _name = 'wizard.import.csv'
    _description = "Wizard d'import CSV d'équipements"

    fichier_csv = fields.Binary(
        string='Fichier CSV', required=True,
        help='Format : numero_serie, name, categorie, marque, '
             'modele, date_achat, valeur_achat, '
             'date_fin_garantie, site')
    nom_fichier = fields.Char(string='Nom du fichier')
    delimiteur = fields.Selection([
        (',', 'Virgule (,)'),
        (';', 'Point-virgule (;)'),
        ('\t', 'Tabulation'),
    ], string='Délimiteur', default=',', required=True)
    encodage = fields.Selection([
        ('utf-8', 'UTF-8'),
        ('latin-1', 'Latin-1 (ISO-8859-1)'),
    ], string='Encodage', default='utf-8', required=True)

    # ── Résultats ──────────────────────────────────────────────
    state = fields.Selection([
        ('draft', 'En attente'),
        ('done', 'Terminé'),
    ], default='draft')
    nb_crees = fields.Integer(string='Créés', readonly=True)
    nb_ignores = fields.Integer(string='Ignorés (doublons)', readonly=True)
    nb_erreurs = fields.Integer(string='Erreurs', readonly=True)
    rapport_texte = fields.Text(
        string='Détail du rapport', readonly=True)

    # ── Colonnes attendues ─────────────────────────────────────
    COLONNES_REQUISES = ['numero_serie', 'name', 'categorie']
    CATEGORIES_VALIDES = [
        'poste', 'serveur', 'imprimante',
        'reseau', 'telephone', 'autre'
    ]
    SITES_VALIDES = ['abidjan1', 'abidjan2', 'bouake']

    def action_importer(self):
        self.ensure_one()

        if not self.fichier_csv:
            raise UserError('Veuillez sélectionner un fichier CSV.')

        # Décoder le fichier
        try:
            contenu = base64.b64decode(self.fichier_csv)
            texte = contenu.decode(self.encodage)
        except Exception as e:
            raise UserError(
                f'Impossible de lire le fichier : {str(e)}\n'
                f'Vérifiez l\'encodage sélectionné.'
            )

        # Parser le CSV
        try:
            reader = csv.DictReader(
                io.StringIO(texte),
                delimiter=self.delimiteur
            )
            lignes = list(reader)
        except Exception as e:
            raise UserError(f'Erreur de parsing CSV : {str(e)}')

        if not lignes:
            raise UserError('Le fichier CSV est vide.')

        # Vérifier les colonnes requises
        colonnes_presentes = lignes[0].keys() if lignes else []
        manquantes = [
            c for c in self.COLONNES_REQUISES
            if c not in colonnes_presentes
        ]
        if manquantes:
            raise UserError(
                f'Colonnes manquantes dans le CSV : '
                f'{", ".join(manquantes)}\n'
                f'Colonnes requises : '
                f'{", ".join(self.COLONNES_REQUISES)}'
            )

        # Traitement ligne par ligne
        nb_crees = 0
        nb_ignores = 0
        nb_erreurs = 0
        rapport = []

        for i, ligne in enumerate(lignes, start=2):
            num_serie = ligne.get('numero_serie', '').strip()
            nom = ligne.get('name', '').strip()
            categorie = ligne.get('categorie', '').strip()

            # ── Validation champs requis ───────────────────────
            if not num_serie or not nom or not categorie:
                nb_erreurs += 1
                rapport.append(
                    f'Ligne {i} — ERREUR : '
                    f'Champs requis manquants '
                    f'(numero_serie, name, categorie).'
                )
                continue

            # ── Validation catégorie ───────────────────────────
            if categorie not in self.CATEGORIES_VALIDES:
                nb_erreurs += 1
                rapport.append(
                    f'Ligne {i} — ERREUR : '
                    f'Catégorie "{categorie}" invalide. '
                    f'Valeurs acceptées : '
                    f'{", ".join(self.CATEGORIES_VALIDES)}.'
                )
                continue

            # ── Vérification doublon ───────────────────────────
            existant = self.env['it.equipement'].search([
                ('numero_serie', '=', num_serie)
            ], limit=1)
            if existant:
                nb_ignores += 1
                rapport.append(
                    f'Ligne {i} — IGNORÉ : '
                    f'Numéro de série "{num_serie}" '
                    f'déjà existant ({existant.name}).'
                )
                continue

            # ── Validation site ────────────────────────────────
            site = ligne.get('site', '').strip()
            if site and site not in self.SITES_VALIDES:
                nb_erreurs += 1
                rapport.append(
                    f'Ligne {i} — ERREUR : '
                    f'Site "{site}" invalide. '
                    f'Valeurs acceptées : '
                    f'{", ".join(self.SITES_VALIDES)}.'
                )
                continue

            # ── Validation dates ───────────────────────────────
            date_achat = self._parse_date(
                ligne.get('date_achat', ''), i, rapport)
            date_garantie = self._parse_date(
                ligne.get('date_fin_garantie', ''), i, rapport)

            # ── Validation valeur achat ────────────────────────
            valeur_achat = 0.0
            valeur_str = ligne.get('valeur_achat', '').strip()
            if valeur_str:
                try:
                    valeur_achat = float(valeur_str)
                    if valeur_achat < 0:
                        raise ValueError()
                except ValueError:
                    nb_erreurs += 1
                    rapport.append(
                        f'Ligne {i} — ERREUR : '
                        f'Valeur d\'achat invalide : "{valeur_str}".'
                    )
                    continue

            # ── Création de l'équipement ───────────────────────
            try:
                vals = {
                    'name': nom,
                    'numero_serie': num_serie,
                    'categorie': categorie,
                    'marque': ligne.get('marque', '').strip(),
                    'modele': ligne.get('modele', '').strip(),
                    'site': site or False,
                    'valeur_achat': valeur_achat,
                }
                if date_achat:
                    vals['date_achat'] = date_achat
                if date_garantie:
                    vals['date_fin_garantie'] = date_garantie

                self.env['it.equipement'].create(vals)
                nb_crees += 1
                rapport.append(
                    f'Ligne {i} — CRÉÉ : "{nom}" ({num_serie}).'
                )
            except Exception as e:
                nb_erreurs += 1
                rapport.append(
                    f'Ligne {i} — ERREUR création : {str(e)}'
                )

        # ── Mise à jour du rapport ─────────────────────────────
        self.write({
            'state': 'done',
            'nb_crees': nb_crees,
            'nb_ignores': nb_ignores,
            'nb_erreurs': nb_erreurs,
            'rapport_texte': '\n'.join(rapport),
        })

        # Rester sur le wizard pour afficher le rapport
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _parse_date(self, valeur, num_ligne, rapport):
        """Parse une date au format YYYY-MM-DD."""
        if not valeur or not valeur.strip():
            return False
        from datetime import datetime
        try:
            return datetime.strptime(
                valeur.strip(), '%Y-%m-%d').date()
        except ValueError:
            rapport.append(
                f'Ligne {num_ligne} — AVERTISSEMENT : '
                f'Date "{valeur}" invalide (format attendu : '
                f'YYYY-MM-DD). Champ ignoré.'
            )
            return False