# IT Parc — Gestion de parc informatique

Module Odoo 18 développé pour **TECHPARK CI** permettant la gestion complète d'un parc informatique : inventaire des équipements, affectations, interventions, contrats fournisseurs, alertes automatiques, rapports et tableau de bord.

---

## Table des matières

- [Présentation](#présentation)
- [Architecture](#architecture)
- [Installation](#installation)
- [Configuration initiale](#configuration-initiale)
- [Fonctionnalités](#fonctionnalités)
- [Structure du code](#structure-du-code)
- [Sécurité et droits d'accès](#sécurité-et-droits-daccès)
- [Tâches planifiées](#tâches-planifiées)
- [Rapports et exports](#rapports-et-exports)
- [Dashboard OWL](#dashboard-owl)
- [Dépannage](#dépannage)

---

## Présentation

Le module `it_parc` répond aux besoins métier de gestion d'un parc informatique multi-sites. Il permet de :

- Centraliser l'inventaire de tous les équipements informatiques
- Suivre les affectations aux employés avec historique complet
- Planifier et tracer les interventions de maintenance
- Gérer les contrats fournisseurs avec alertes d'expiration
- Générer des rapports PDF et des exports Excel
- Visualiser l'activité du parc via un tableau de bord interactif

**Cible** : Direction des Systèmes d'Information de TECHPARK CI, techniciens IT, managers IT.

**Sites couverts** : Abidjan (Site 1 et 2), Bouaké.

**Devise** : FCFA (XOF).

---

## Architecture

### Stack technique

| Composant | Technologie |
|-----------|-------------|
| Framework | Odoo 18.0 |
| Backend | Python 3.11+ |
| Base de données | PostgreSQL 14+ |
| Frontend (Dashboard) | OWL 2 (JavaScript) |
| Graphiques | Chart.js |
| Export Excel | xlsxwriter |
| Rapports PDF | QWeb + wkhtmltopdf |
| Cron | Tâches Odoo natives |

### Modèles métier

Le module comprend **5 modèles principaux** :

```
it.equipement      ← Cœur du module (équipements)
    │
    ├── it.affectation     ← Historique des affectations aux employés
    ├── it.intervention    ← Maintenances et interventions
    ├── it.contrat         ← Contrats fournisseurs (Many2many)
    └── it.alerte          ← Alertes garanties / contrats
```

Tous les modèles héritent de `mail.thread` et `mail.activity.mixin` pour bénéficier du chatter et des activités planifiées Odoo.

### Dépendances Odoo

```python
'depends': [
    'base', 'mail', 'hr', 'contacts',
    'stock', 'purchase', 'account',
    'maintenance', 'web',
]
```

---

## Installation

### Prérequis

- Odoo 18.0 installé et fonctionnel
- PostgreSQL 14 ou supérieur
- Python 3.11+
- Package Python `xlsxwriter` : `pip install xlsxwriter`

### Étape 1 — Copier le module

Placer le dossier `it_parc/` dans votre répertoire `custom_addons` :

```bash
cp -r it_parc /chemin/vers/odoo-18.0/custom_addons/
```

### Étape 2 — Vérifier la configuration

S'assurer que `custom_addons` figure dans le `addons_path` de votre fichier `odoo.conf` :

```ini
[options]
addons_path = addons,custom_addons
```

### Étape 3 — Installer le module

Activer l'environnement virtuel et lancer Odoo avec l'option d'installation :

```bash
source venv/bin/activate
python odoo-bin -c odoo.conf -d techpark_db -i it_parc
```

Ou via l'interface web :

1. Se connecter à Odoo en tant qu'administrateur
2. Activer le mode développeur (`Paramètres → Activer le mode développeur`)
3. Aller dans **Applications**
4. Cliquer sur **Mettre à jour la liste des applications**
5. Rechercher **IT Parc** et cliquer sur **Installer**

### Étape 4 — Vérifier l'installation

Un nouveau menu **IT Parc** doit apparaître dans la barre principale d'Odoo.

---

## Configuration initiale

### Affecter les utilisateurs aux groupes

Après installation, assigner les utilisateurs aux groupes appropriés via **Paramètres → Utilisateurs et entreprises → Utilisateurs** :

- **IT Technicien** : lecture des équipements, gestion des interventions
- **IT Manager** : accès complet à tous les modèles

### Lier les techniciens à leurs employés HR

Chaque technicien doit avoir une fiche `hr.employee` liée à son `res.users` pour que les règles de sécurité fonctionnent correctement.

### Paramétrer le délai d'alerte

Le délai d'anticipation des alertes (par défaut 30 jours) peut être modifié via les paramètres système :

```
Paramètres → Technique → Paramètres → it_parc.delai_alerte
```

---

## Fonctionnalités

### 1. Gestion des équipements

Chaque équipement dispose d'une fiche complète avec :

- Référence automatique au format `EQ/YYYY/NNNN`
- Identification (nom, numéro de série unique, catégorie)
- Caractéristiques techniques (processeur, RAM, OS, IP, MAC)
- Informations d'achat (date, valeur, fournisseur, garantie)
- Localisation (site, bureau)
- Affectation courante (employé, département)
- Photo de l'équipement

**6 catégories disponibles** : poste de travail, serveur, imprimante, équipement réseau, téléphone IP, autre.

**Workflow d'état** :

```
Brouillon → Affecté → En maintenance → Retiré
```

### 2. Affectations aux employés

- Une seule affectation active à la fois par équipement (contrainte métier)
- Historique complet conservé (affectations clôturées visibles)
- Wizard de réaffectation qui clôture automatiquement l'ancienne affectation
- Calcul automatique de la durée d'affectation
- Motif obligatoire (minimum 10 caractères)

### 3. Suivi des interventions

- Référence automatique au format `INT/YYYY/NNNN`
- Type **corrective** ou **préventive**
- Vue calendrier pour la planification
- Workflow : Planifié → En cours → Terminé (ou Annulé)
- Mise à jour automatique de l'état de l'équipement
- Calcul automatique de la durée en heures
- Rapport d'intervention obligatoire avant clôture
- Suivi des coûts en FCFA

### 4. Contrats fournisseurs

- Référence automatique au format `CT/YYYY/NNNN`
- 4 types : maintenance, licence logicielle, support technique, autre
- Lien Many2many vers les équipements couverts
- Calcul automatique des jours restants
- Indicateur visuel "expire bientôt" (≤ 60 jours)
- Wizard de renouvellement qui crée le nouveau contrat et archive l'ancien
- Passage automatique en "Expiré" quand la date est dépassée

### 5. Alertes automatiques

Deux sources d'alertes :

| Source | Déclencheur |
|--------|-------------|
| Garantie équipement | `date_fin_garantie` proche |
| Expiration contrat | `date_fin` proche |

**Niveau d'urgence calculé** :

- **Critique** : ≤ 7 jours
- **Haute** : ≤ 30 jours
- **Normale** : > 30 jours

Génération quotidienne automatique via cron, avec déduplication (pas de doublons sur une alerte active existante).

### 6. Import CSV en masse

Wizard d'import permettant de créer plusieurs équipements depuis un fichier CSV.

**Format attendu** :

```csv
numero_serie,name,categorie,marque,modele,date_achat,valeur_achat,date_fin_garantie,site
SN001,Dell Latitude 5520,poste,Dell,Latitude 5520,2024-01-15,850000,2027-01-15,abidjan1
```

**Options configurables** :

- Délimiteur : virgule, point-virgule, tabulation
- Encodage : UTF-8 ou Latin-1

**Rapport de traitement** affichant le nombre d'équipements créés, ignorés (doublons) et en erreur avec détail ligne par ligne.

### 7. Scan manuel des alertes

Wizard permettant de déclencher manuellement le scan des alertes sans attendre le cron quotidien. Paramètres :

- Délai d'anticipation personnalisable
- Choix des types à scanner (garanties et/ou contrats)
- Rapport détaillé après exécution

---

## Structure du code

```
it_parc/
├── __init__.py
├── __manifest__.py
├── README.md
│
├── controllers/
│   ├── __init__.py
│   └── dashboard.py              # Endpoint /it_parc/dashboard_data
│
├── data/
│   ├── ir_sequence.xml           # Séquences EQ/INT/CT
│   ├── ir_cron.xml               # Tâches planifiées
│   └── it_parc_demo.xml          # Données de démonstration
│
├── models/
│   ├── __init__.py
│   ├── it_equipement.py          # Modèle principal + export Excel
│   ├── it_affectation.py
│   ├── it_intervention.py        # + export Excel coûts
│   ├── it_contrat.py             # + export Excel contrats
│   └── it_alerte.py              # + méthode cron
│
├── report/
│   ├── report_actions.xml        # Déclaration des actions PDF
│   ├── report_fiche_equipement.xml
│   ├── report_inventaire.xml
│   └── report_maintenance.xml
│
├── security/
│   ├── security_groups.xml       # IT Technicien / IT Manager
│   ├── ir.model.access.csv       # Droits CRUD par modèle
│   └── ir_rules.xml              # Règles de visibilité
│
├── static/src/components/
│   ├── ItParcDashboard.js        # Composant OWL
│   ├── ItParcDashboard.xml       # Template
│   └── dashboard.scss            # Styles
│
├── views/
│   ├── menus.xml                 # Navigation
│   ├── dashboard_action.xml      # Action client OWL
│   ├── equipement_views.xml      # Liste, formulaire, kanban, recherche
│   ├── affectation_views.xml
│   ├── intervention_views.xml    # Inclut vue calendrier
│   ├── contrat_views.xml
│   └── alerte_views.xml
│
└── wizards/
    ├── __init__.py
    ├── wizard_reaffectation.py + views
    ├── wizard_import_csv.py + views
    ├── wizard_scan_alerte.py + views
    └── wizard_renouvellement.py + views
```

---

## Sécurité et droits d'accès

### Groupes

| Groupe | Permissions |
|--------|-------------|
| **IT Technicien** | Lecture sur tous les équipements et affectations. Création et modification de ses propres interventions. |
| **IT Manager** | Accès complet (CRUD) sur tous les modèles du module. Hérite automatiquement des droits IT Technicien. |

### Règles d'accès (ir.rule)

- **Équipements** : tous les groupes voient tous les équipements
- **Interventions** : un technicien ne voit et modifie que les interventions où il est désigné comme technicien
- **Contrats et alertes** : visibles uniquement par les IT Managers

---

## Tâches planifiées

Deux crons sont créés à l'installation :

| Cron | Fréquence | Action |
|------|-----------|--------|
| Génération alertes | Quotidien à 8h | Scan des garanties et contrats expirant dans les 30 prochains jours |
| Mise à jour contrats expirés | Quotidien à 7h | Passage automatique en état "Expiré" des contrats dépassés |

Les crons sont accessibles via **Paramètres → Technique → Actions planifiées**.

---

## Rapports et exports

### Rapports PDF (QWeb)

Trois rapports sont disponibles via le bouton **Imprimer** :

1. **Fiche équipement** : fiche détaillée d'un équipement avec historique des affectations et interventions
2. **Inventaire complet** : liste de tous les équipements avec résumé par catégorie
3. **Historique des maintenances** : interventions sur une période avec statistiques

### Exports Excel (xlsxwriter)

Trois exports Excel téléchargeables depuis les formulaires :

1. **Inventaire complet** : un onglet par catégorie + résumé global, coloration par état
2. **Coûts de maintenance** : détail des interventions + tableau croisé mois × équipement
3. **Suivi des contrats** : tableau coloré (rouge ≤ 30j, orange ≤ 60j, vert > 60j)

Les fichiers Excel utilisent le format de devise FCFA avec séparateur de milliers.

---

## Dashboard OWL

Tableau de bord interactif accessible via le menu **IT Parc → Tableau de bord**.

### Contenu

**4 KPIs cliquables** redirigeant vers les vues filtrées :

- Total équipements actifs
- Équipements en maintenance
- Alertes actives
- Coût de maintenance du mois en cours

**Graphique** : interventions correctives et préventives sur les 6 derniers mois (barres).

**Panneau alertes urgentes** : les 10 alertes les plus proches de l'échéance, cliquables pour navigation rapide.

**Tableau de répartition** : équipements par catégorie avec valeur totale.

### Technique

- Composant OWL 2 (`ItParcDashboard.js`)
- Données chargées via contrôleur HTTP dédié (`/it_parc/dashboard_data`)
- Graphique généré avec Chart.js
- Rafraîchissement automatique toutes les 5 minutes
- Bouton "Actualiser" pour rafraîchissement manuel

---

## Dépannage

### Le module ne s'installe pas

Vérifier que toutes les dépendances Odoo sont installées :

```bash
python odoo-bin -c odoo.conf -d techpark_db -i hr,contacts,stock,purchase,account,maintenance
```

Puis relancer l'installation de `it_parc`.

### Erreur "Unallowed to fetch files from addon website_payment"

Cette erreur survient si le module `website` est installé mais pas `website_payment`. Solution : ne pas installer `website` sur la même base, ou installer `website_payment` :

```bash
python odoo-bin -c odoo.conf -d techpark_db -i website_payment
```

### Le dashboard ne s'affiche pas

Vérifier dans la console du navigateur (F12) qu'il n'y a pas d'erreur réseau sur `/it_parc/dashboard_data`. Si erreur 404, redémarrer Odoo avec mise à jour :

```bash
python odoo-bin -c odoo.conf -d techpark_db -u it_parc
```

### Les alertes ne sont pas générées

Vérifier que les crons sont activés dans **Paramètres → Technique → Actions planifiées**. Pour tester manuellement, utiliser le menu **IT Parc → Configuration → Scanner les alertes**.

### Erreur xlsxwriter manquant

Installer le package Python :

```bash
pip install xlsxwriter
```

---

## Contact

Pour toute question ou contribution, contacter l'équipe DSI de TECHPARK CI.

**Version actuelle** : 18.0.1.0.0
```

