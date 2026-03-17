"""
GESTo V3 — Script de peuplement
Complexe Scolaire Ste Bakhita — 500 eleves
"""
import random
from decimal import Decimal
from datetime import date, timedelta
from django.utils import timezone
from django.contrib.auth.hashers import make_password

from apps.authentication.models import CustomUser
from apps.academic.models import (
    AnneeScolaire, Periode, Niveau, GroupeMatiere,
    Matiere, SalleClasse, MatiereSalle
)
from apps.students.models import Eleve, Parent, EleveParent, Inscription
from apps.grades.models import Evaluation, AutorisationSaisie, Note
from apps.attendance.models import SeancePointage, Presence
from apps.finance.models import TypeFrais, TarifNiveau, FraisEleve, Paiement, Depense
from apps.discipline.models import TypeSanction, Sanction, DemandeExclusion
from apps.communication.models import Notification, Message, EvenementCalendrier, ReunionParent
from apps.devoirs.models import Devoir, SoumissionDevoir
from apps.preinscription.models import PreInscription
from apps.core.models import ConfigurationEcole

# ── DONNEES DE BASE ───────────────────────────────────────────────────────────

NOMS = [
    'KOFFI', 'AGBEKO', 'MENSAH', 'GNON', 'TOGBE', 'AFLA', 'DZIFA',
    'KUASSI', 'ABLO', 'KODZO', 'ATSU', 'EDEM', 'KWAMI', 'YAWO',
    'MAWULI', 'SENYO', 'DELA', 'KOKU', 'SENU', 'ABALO', 'KOMLA',
    'NUTEFE', 'GBATI', 'FIAGBE', 'KPODO', 'AMEDO', 'AYAO', 'KOSSI',
    'AFOLABI', 'SOUMAILA', 'IBRAHIM', 'MOUSSA', 'ALI', 'KOKOU', 'KOMI',
    'AMA', 'AFI', 'AKUA', 'ABLA', 'EFUA', 'ENYONAM', 'AKOSUA',
    'AKOFA', 'YAWA', 'MAWUNYO', 'SENA', 'DZIGBODI', 'AKPENE',
    'YAYRA', 'DELALI', 'KAFUI', 'MANSA', 'FATOUMATA', 'AMINATA',
]

PRENOMS_M = [
    'Jean', 'Pierre', 'Paul', 'Jacques', 'Henri', 'Louis', 'Marc',
    'André', 'Philippe', 'Nicolas', 'François', 'Claude', 'Emmanuel',
    'Kofi', 'Kwame', 'Edem', 'Mawuli', 'Yawo', 'Koku', 'Komla',
    'Ibrahim', 'Moussa', 'Ali', 'Yusuf', 'Abdoul', 'Kossi', 'Komi',
]

PRENOMS_F = [
    'Marie', 'Anne', 'Sophie', 'Claire', 'Julie', 'Laura', 'Emma',
    'Ama', 'Afi', 'Akua', 'Yawa', 'Sena', 'Mawunyo', 'Akpene',
    'Senam', 'Kafui', 'Fatoumata', 'Aminata', 'Mariama', 'Elom',
]

VILLES = [
    'Lomé', 'Kpalimé', 'Atakpamé', 'Sokodé', 'Kara', 'Tsévié',
    'Aného', 'Notse', 'Dapaong', 'Bassar', 'Vogan',
]

PROFESSIONS = [
    'Enseignant', 'Commerçant', 'Infirmier', 'Médecin', 'Ingénieur',
    'Comptable', 'Fonctionnaire', 'Agriculteur', 'Chauffeur', 'Artisan',
    'Mécanicien', 'Électricien', 'Policier', 'Militaire', 'Pharmacien',
]

MATIERES_COLLEGE = [
    ('Mathématiques', 4), ('Français', 4), ('Anglais', 3),
    ('Histoire-Géographie', 3), ('SVT', 3), ('Physique-Chimie', 3),
    ('EPS', 2), ('Arts Plastiques', 1), ('Informatique', 2),
    ('Éducation Civique', 2), ('Éducation Religieuse', 1),
]

MATIERES_LYCEE = [
    ('Mathématiques', 5), ('Français', 4), ('Anglais', 3),
    ('Philosophie', 3), ('Histoire-Géographie', 3), ('SVT', 4),
    ('Physique-Chimie', 4), ('EPS', 2), ('Informatique', 2),
    ('Économie', 2), ('Allemand', 2),
]

MOTIFS_SANCTION = [
    'Bavardage en classe', 'Retard répété',
    'Insolence envers un professeur', 'Perturbation du cours',
    'Absence injustifiée', 'Tricherie à un devoir',
    'Usage du téléphone en classe', 'Bagarre dans la cour',
]


def tel():
    prefixes = ['90', '91', '92', '93', '94', '96', '97', '98', '99', '70']
    return f"+228{random.choice(prefixes)}{random.randint(100000, 999999)}"


print("\n" + "="*60)
print("GESTo V3 — Peuplement Ste Bakhita")
print("="*60)


# ══════════════════════════════════════════════════════════════
# 1 — CONFIGURATION ECOLE
# ══════════════════════════════════════════════════════════════
print("\n[1/14] Configuration école...")
config = ConfigurationEcole.get()
config.nom = "Complexe Scolaire Ste Bakhita"
config.adresse = "Quartier Agbalépédogan, Lomé - Togo"
config.telephone = "+228 22 20 10 10"
config.email = "contact@stebakhita.tg"
config.devise = "Travail, Liberté, Patrie"
config.ministre_tutelle = "Ministère des Enseignements Primaire et Secondaire"
config.seuil_retards_consecutifs = 5
config.seuil_jours_periode = 10
config.save()
print("  ✓ Configuration sauvegardée")


# ══════════════════════════════════════════════════════════════
# 2 — PERSONNEL
# ══════════════════════════════════════════════════════════════
print("\n[2/14] Personnel...")

def creer_user(username, prenom, nom, role, pwd='bakhita2025'):
    u, _ = CustomUser.objects.get_or_create(
        username=username,
        defaults={
            'first_name': prenom, 'last_name': nom,
            'role': role, 'password': make_password(pwd),
            'telephone': tel(), 'telephone_wa': tel(),
            'is_active': True,
        }
    )
    return u

directeur  = creer_user('roland.directeur', 'Roland', 'AHOUMAROLAND', 'DIRECTEUR')
directeur2 = creer_user('marie.directeur',  'Marie',  'AGBEKO',       'DIRECTEUR')
censeur    = creer_user('paul.censeur',     'Paul',   'MENSAH',       'CENSEUR')

secretaires  = [
    creer_user('ama.secretaire',  'Ama',  'KPODO', 'SECRETAIRE'),
    creer_user('sena.secretaire', 'Sena', 'TOGBE', 'SECRETAIRE'),
]
comptables = [
    creer_user('kofi.comptable', 'Kofi', 'AMEDO', 'COMPTABLE'),
    creer_user('yawa.comptable', 'Yawa', 'GBATI', 'COMPTABLE'),
]
surveillants = [
    creer_user('komi.surveillant',  'Komi',  'FIAGBE',  'SURVEILLANT'),
    creer_user('akua.surveillant',  'Akua',  'NUTEFE',  'SURVEILLANT'),
    creer_user('edem.surveillant',  'Edem',  'GBOSSOU', 'SURVEILLANT'),
]

data_profs = [
    ('jean.koffi',      'Jean',      'KOFFI',    'Mathématiques'),
    ('marie.mensah',    'Marie',     'MENSAH',   'Français'),
    ('paul.agbeko',     'Paul',      'AGBEKO',   'Anglais'),
    ('sophie.gnon',     'Sophie',    'GNON',     'Histoire-Géographie'),
    ('pierre.togbe',    'Pierre',    'TOGBE',    'SVT'),
    ('anne.afla',       'Anne',      'AFLA',     'Physique-Chimie'),
    ('louis.dzifa',     'Louis',     'DZIFA',    'EPS'),
    ('henri.ablo',      'Henri',     'ABLO',     'Informatique'),
    ('julie.kodzo',     'Julie',     'KODZO',    'Éducation Civique'),
    ('marc.atsu',       'Marc',      'ATSU',     'Philosophie'),
    ('lea.edem',        'Léa',       'EDEM',     'Économie'),
    ('andre.kwami',     'André',     'KWAMI',    'Allemand'),
    ('emma.yawo',       'Emma',      'YAWO',     'Arts Plastiques'),
    ('nicolas.mawuli',  'Nicolas',   'MAWULI',   'Mathématiques'),
    ('claire.kuassi',   'Claire',    'KUASSI',   'Français'),
]

professeurs = []
for username, prenom, nom, specialite in data_profs:
    p = creer_user(username, prenom, nom, 'PROFESSEUR')
    professeurs.append((p, specialite))

print(f"  ✓ {CustomUser.objects.exclude(role__in=['ELEVE','PARENT']).count()} membres du personnel")


# ══════════════════════════════════════════════════════════════
# 3 — ANNEE ET PERIODES
# ══════════════════════════════════════════════════════════════
print("\n[3/14] Année scolaire et périodes...")

annee, _ = AnneeScolaire.objects.get_or_create(
    nom='2025-2026', defaults={'est_active': True}
)
annee.est_active = True
annee.save()

periodes = []
for num, debut, fin, active in [
    (1, date(2025,10,1),  date(2025,12,20), True),
    (2, date(2026,1,5),   date(2026,3,28),  False),
    (3, date(2026,4,6),   date(2026,6,30),  False),
]:
    p, _ = Periode.objects.get_or_create(
        annee=annee, numero=num,
        defaults={
            'type': 'TRIMESTRE',
            'date_debut': debut,
            'date_fin': fin,
            'est_active': active,
        }
    )
    periodes.append(p)

periode_active = periodes[0]
print("  ✓ 3 trimestres créés")


# ══════════════════════════════════════════════════════════════
# 4 — NIVEAUX ET MATIERES
# ══════════════════════════════════════════════════════════════
print("\n[4/14] Niveaux et matières...")

niveaux_college = []
for i, nom in enumerate(['6ème','5ème','4ème','3ème'], 1):
    n, _ = Niveau.objects.get_or_create(
        nom=nom, defaults={'ordre': i, 'systeme': 'TRIMESTRIEL'}
    )
    niveaux_college.append(n)

niveaux_lycee = []
for i, nom in enumerate(['2nde','1ère','Terminale'], 5):
    n, _ = Niveau.objects.get_or_create(
        nom=nom, defaults={'ordre': i, 'systeme': 'TRIMESTRIEL'}
    )
    niveaux_lycee.append(n)

tous_niveaux = niveaux_college + niveaux_lycee

matieres_obj = {}
for nom_m, _ in MATIERES_COLLEGE + MATIERES_LYCEE:
    m, _ = Matiere.objects.get_or_create(nom=nom_m)
    matieres_obj[nom_m] = m

print(f"  ✓ {len(tous_niveaux)} niveaux, {len(matieres_obj)} matières")


# ══════════════════════════════════════════════════════════════
# 5 — SALLES ET ASSIGNATION MATIERES
# ══════════════════════════════════════════════════════════════
print("\n[5/14] Salles et matières assignées...")

salles_config = {
    '6ème': 3, '5ème': 3, '4ème': 2, '3ème': 2,
    '2nde': 2, '1ère': 2, 'Terminale': 2,
}

toutes_salles = []
prof_idx = 0

for niveau in tous_niveaux:
    nb = salles_config.get(niveau.nom, 2)
    matieres_niveau = (
        MATIERES_COLLEGE if niveau in niveaux_college else MATIERES_LYCEE
    )
    for j in range(1, nb + 1):
        salle, _ = SalleClasse.objects.get_or_create(
            niveau=niveau, annee=annee, nom=f"{niveau.nom}{j}",
            defaults={'capacite': random.randint(35, 45), 'est_active': True}
        )
        toutes_salles.append(salle)

        for nom_m, coef in matieres_niveau:
            if nom_m not in matieres_obj:
                continue
            prof_choisi = None
            for prof, spec in professeurs:
                if spec == nom_m:
                    prof_choisi = prof
                    break
            if not prof_choisi:
                prof_choisi = professeurs[prof_idx % len(professeurs)][0]
                prof_idx += 1

            MatiereSalle.objects.get_or_create(
                salle=salle, matiere=matieres_obj[nom_m],
                defaults={'coefficient': coef, 'professeur': prof_choisi}
            )

print(f"  ✓ {len(toutes_salles)} salles créées")


# ══════════════════════════════════════════════════════════════
# 6 — TYPES DE FRAIS ET TARIFS
# ══════════════════════════════════════════════════════════════
print("\n[6/14] Frais et tarifs...")

tf_insc, _ = TypeFrais.objects.get_or_create(
    nom="Frais d'inscription", defaults={'est_obligatoire': True}
)
tf_scol, _ = TypeFrais.objects.get_or_create(
    nom="Frais de scolarité", defaults={'est_obligatoire': True}
)
tf_exam, _ = TypeFrais.objects.get_or_create(
    nom="Frais d'examen", defaults={'est_obligatoire': True}
)

tarifs_config = {
    '6ème':      (25000, 120000, 15000),
    '5ème':      (25000, 120000, 15000),
    '4ème':      (30000, 130000, 20000),
    '3ème':      (30000, 140000, 25000),
    '2nde':      (35000, 150000, 25000),
    '1ère':      (35000, 160000, 30000),
    'Terminale': (35000, 170000, 35000),
}

for niveau in tous_niveaux:
    insc, scol, exam = tarifs_config.get(niveau.nom, (25000, 120000, 15000))
    TarifNiveau.objects.get_or_create(
        niveau=niveau, annee=annee,
        defaults={
            'frais_inscription': insc,
            'frais_scolarite': scol,
            'frais_examen': exam,
        }
    )
print(f"  ✓ Tarifs définis pour {len(tous_niveaux)} niveaux")


# ══════════════════════════════════════════════════════════════
# 7 — ELEVES ET PARENTS (500)
# ══════════════════════════════════════════════════════════════
print("\n[7/14] Création de 500 élèves et parents...")

distribution = {
    '6ème': 40, '5ème': 38, '4ème': 35, '3ème': 33,
    '2nde': 30, '1ère': 28, 'Terminale': 25,
}

eleves_crees = []
eleve_counter = 1

for niveau in tous_niveaux:
    salles_niveau = [s for s in toutes_salles if s.niveau == niveau]
    nb_niveau = distribution.get(niveau.nom, 30)
    nb_par_salle = nb_niveau // len(salles_niveau)

    for salle in salles_niveau:
        for _ in range(nb_par_salle):
            sexe = random.choice(['M', 'F'])
            nom = random.choice(NOMS)
            prenom = random.choice(PRENOMS_M if sexe == 'M' else PRENOMS_F)
            matricule = f"BKT-2025-{eleve_counter:04d}"
            username_e = f"e{eleve_counter:04d}"

            user_e, _ = CustomUser.objects.get_or_create(
                username=username_e,
                defaults={
                    'first_name': prenom, 'last_name': nom,
                    'role': 'ELEVE', 'password': make_password('eleve2025'),
                    'is_active': True,
                }
            )
            eleve, _ = Eleve.objects.get_or_create(
                matricule=matricule,
                defaults={
                    'user': user_e, 'nom': nom, 'prenom': prenom,
                    'sexe': sexe,
                    'date_naissance': date(
                        random.randint(2005, 2015),
                        random.randint(1, 12),
                        random.randint(1, 28)
                    ),
                    'lieu_naissance': random.choice(VILLES),
                    'redoublant': random.random() < 0.12,
                    'statut': 'ACTIF',
                    'contact_urgence': f"{random.choice(PRENOMS_M)} {nom}",
                    'telephone_urgence': tel(),
                }
            )
            Inscription.objects.get_or_create(
                eleve=eleve, annee=annee,
                defaults={'salle': salle, 'statut': 'ACTIVE'}
            )

            # Parent
            nom_p = nom
            prenom_p = random.choice(PRENOMS_F)
            lien = random.choice(['PERE', 'MERE'])
            tel_p = tel()
            username_p = f"p{eleve_counter:04d}"

            user_p, _ = CustomUser.objects.get_or_create(
                username=username_p,
                defaults={
                    'first_name': prenom_p, 'last_name': nom_p,
                    'role': 'PARENT', 'password': make_password('parent2025'),
                    'telephone': tel_p, 'telephone_wa': tel_p,
                    'is_active': True,
                }
            )
            parent, _ = Parent.objects.get_or_create(
                user=user_p,
                defaults={
                    'nom': nom_p, 'prenom': prenom_p,
                    'telephone': tel_p,
                    'profession': random.choice(PROFESSIONS),
                    'adresse': f"Quartier {random.choice(VILLES)}",
                }
            )
            EleveParent.objects.get_or_create(
                eleve=eleve, parent=parent,
                defaults={'lien': lien, 'est_contact_principal': True}
            )

            # Frais avec scénarios paiement
            tarif = TarifNiveau.objects.filter(
                niveau=niveau, annee=annee
            ).first()
            if tarif:
                scenario = random.random()
                for tf, montant in [
                    (tf_insc, tarif.frais_inscription),
                    (tf_scol, tarif.frais_scolarite),
                    (tf_exam, tarif.frais_examen),
                ]:
                    frais, _ = FraisEleve.objects.get_or_create(
                        eleve=eleve, type_frais=tf, annee=annee,
                        defaults={'montant': montant}
                    )
                    if scenario < 0.60:
                        frais.montant_paye = montant
                    elif scenario < 0.85:
                        frais.montant_paye = Decimal(
                            str(int(float(montant) * random.uniform(0.3, 0.8)))
                        )
                    frais.save()

            eleves_crees.append(eleve)
            eleve_counter += 1

print(f"  ✓ {len(eleves_crees)} élèves créés")


# ══════════════════════════════════════════════════════════════
# 8 — PAIEMENTS
# ══════════════════════════════════════════════════════════════
print("\n[8/14] Paiements...")

paiement_counter = 1
for eleve in eleves_crees:
    for frais in FraisEleve.objects.filter(eleve=eleve, annee=annee):
        if float(frais.montant_paye) > 0:
            numero = f"REC-2025-{paiement_counter:04d}"
            Paiement.objects.get_or_create(
                numero_recu=numero,
                defaults={
                    'eleve': eleve, 'frais': frais,
                    'montant': frais.montant_paye,
                    'moyen': random.choice(['ESPECES','MOBILE_MONEY','VIREMENT']),
                    'recu_par': random.choice(comptables),
                    'date_paiement': date(2025, random.randint(9,12), random.randint(1,28)),
                }
            )
            paiement_counter += 1

print(f"  ✓ {paiement_counter - 1} paiements")


# ══════════════════════════════════════════════════════════════
# 9 — EVALUATIONS ET NOTES
# ══════════════════════════════════════════════════════════════
print("\n[9/14] Évaluations et notes...")

nb_evals = 0
nb_notes = 0
today = timezone.now().date()

for salle in toutes_salles[:10]:
    inscrits = list(Inscription.objects.filter(
        salle=salle, annee=annee, statut='ACTIVE'
    ).select_related('eleve'))

    for ms in MatiereSalle.objects.filter(salle=salle)[:4]:
        for num in range(1, 3):
            ev, created = Evaluation.objects.get_or_create(
                matiere_salle=ms, periode=periode_active,
                titre=f"Devoir {num} — {ms.matiere.nom}",
                defaults={
                    'type': random.choice(['DEVOIR','INTERROGATION']),
                    'date': date(2025, random.randint(10,12), random.randint(1,28)),
                    'note_sur': 20,
                    'statut': 'VALIDEE_FINALE',
                    'creee_par': ms.professeur,
                    'validee_par': censeur,
                }
            )
            nb_evals += 1
            if created:
                for insc in inscrits:
                    absent = random.random() < 0.05
                    Note.objects.get_or_create(
                        evaluation=ev, eleve=insc.eleve,
                        defaults={
                            'valeur': None if absent else Decimal(
                                str(round(random.uniform(4, 20), 2))
                            ),
                            'est_absent': absent,
                            'saisie_par': ms.professeur,
                        }
                    )
                    nb_notes += 1

print(f"  ✓ {nb_evals} évaluations, {nb_notes} notes")


# ══════════════════════════════════════════════════════════════
# 10 — PRESENCES
# ══════════════════════════════════════════════════════════════
print("\n[10/14] Présences...")

nb_seances = 0
for salle in toutes_salles[:8]:
    inscrits = list(Inscription.objects.filter(
        salle=salle, annee=annee, statut='ACTIVE'
    ).select_related('eleve'))

    for ms in MatiereSalle.objects.filter(salle=salle)[:3]:
        for j in range(1, 8):
            jour = today - timedelta(days=j)
            if jour.weekday() >= 5:
                continue
            seance, created = SeancePointage.objects.get_or_create(
                matiere_salle=ms, date=jour,
                defaults={'statut': 'SOUMIS'}
            )
            nb_seances += 1
            if created:
                for insc in inscrits:
                    r = random.random()
                    statut = (
                        'PRESENT' if r < 0.85 else
                        'ABSENT' if r < 0.92 else
                        'RETARD' if r < 0.96 else
                        'ABSENT_JUSTIFIE'
                    )
                    Presence.objects.get_or_create(
                        eleve=insc.eleve, seance=seance,
                        defaults={'statut': statut, 'pointe_par': ms.professeur}
                    )

print(f"  ✓ {nb_seances} séances")


# ══════════════════════════════════════════════════════════════
# 11 — DISCIPLINE
# ══════════════════════════════════════════════════════════════
print("\n[11/14] Discipline...")

types_sanctions = []
for nom_s, gravite in [
    ('Avertissement oral', 1), ('Avertissement écrit', 1),
    ('Blâme', 2), ('Retenue', 2),
    ('Exclusion temporaire 1 jour', 2), ('Exclusion temporaire 3 jours', 3),
    ('Convocation parent', 1), ('Exclusion définitive', 3),
]:
    ts, _ = TypeSanction.objects.get_or_create(
        nom=nom_s, defaults={'gravite': gravite}
    )
    types_sanctions.append(ts)

for eleve in random.sample(eleves_crees, min(35, len(eleves_crees))):
    statut_s = random.choice(['EN_ATTENTE','APPROUVEE','APPROUVEE','REJETEE','LEVEE'])
    Sanction.objects.create(
        eleve=eleve,
        type_sanction=random.choice(types_sanctions),
        motif=random.choice(MOTIFS_SANCTION),
        date_faits=date(2025, random.randint(10,12), random.randint(1,28)),
        statut=statut_s,
        signale_par=random.choice(surveillants),
        approuve_par=censeur if statut_s != 'EN_ATTENTE' else None,
    )

for eleve in random.sample(eleves_crees, 3):
    DemandeExclusion.objects.create(
        eleve=eleve,
        motif=random.choice(MOTIFS_SANCTION),
        statut=random.choice(['EN_ATTENTE','APPROUVEE','REJETEE']),
        demandee_par=random.choice(surveillants),
    )

print("  ✓ 35 sanctions, 3 demandes d'exclusion")


# ══════════════════════════════════════════════════════════════
# 12 — COMMUNICATION ET CALENDRIER
# ══════════════════════════════════════════════════════════════
print("\n[12/14] Communication et calendrier...")

for user in list(CustomUser.objects.filter(is_active=True).exclude(
    role__in=['ELEVE','PARENT']
))[:15]:
    for _ in range(random.randint(2, 5)):
        Notification.objects.create(
            destinataire=user,
            titre=random.choice([
                'Nouveau bulletin disponible',
                'Paiement reçu', 'Absence signalée',
                'Nouveau communiqué', 'Devoir publié',
            ]),
            message='Cliquez pour voir les détails.',
            type=random.choice(['INFO','ALERTE','SUCCES','AVERTISSEMENT']),
            est_lue=random.random() < 0.5,
        )

for _ in range(10):
    Message.objects.create(
        expediteur=random.choice([directeur, censeur] + surveillants),
        destinataire=random.choice(secretaires + comptables),
        sujet=random.choice([
            'Réunion pédagogique vendredi',
            'Rappel saisie notes T1',
            'Absence élève à traiter',
        ]),
        contenu='Bonjour, merci de prendre en compte cette information.',
        est_lu=random.random() < 0.6,
    )

for titre, type_ev, debut, fin in [
    ('Rentrée scolaire 2025-2026',   'EVENEMENT', date(2025,10,1),  None),
    ('Toussaint',                    'FERIE',     date(2025,11,1),  None),
    ('Vacances de Noël',             'VACANCES',  date(2025,12,20), date(2026,1,4)),
    ('Reprise T2',                   'EVENEMENT', date(2026,1,5),   None),
    ('Examens T1',                   'EXAMEN',    date(2025,12,10), date(2025,12,19)),
    ('Fête Nationale',               'FERIE',     date(2026,4,27),  None),
    ('Vacances de Pâques',           'VACANCES',  date(2026,3,29),  date(2026,4,5)),
    ('Examens finaux BEPC',          'EXAMEN',    date(2026,6,1),   date(2026,6,15)),
    ('Remise des bulletins T1',      'EVENEMENT', date(2025,12,22), None),
    ('Journée portes ouvertes',      'EVENEMENT', date(2026,2,14),  None),
]:
    EvenementCalendrier.objects.get_or_create(
        titre=titre, annee=annee,
        defaults={'type': type_ev, 'date_debut': debut, 'date_fin': fin, 'creee_par': directeur}
    )

ReunionParent.objects.get_or_create(
    titre='Réunion parents T1 — Remise bulletins',
    defaults={
        'date': date(2025,12,22), 'heure': '09:00',
        'lieu': 'Salle polyvalente Ste Bakhita',
        'statut': 'PLANIFIEE', 'organisee_par': directeur, 'annee': annee,
    }
)
print("  ✓ Notifications, messages, calendrier créés")


# ══════════════════════════════════════════════════════════════
# 13 — DEVOIRS
# ══════════════════════════════════════════════════════════════
print("\n[13/14] Devoirs...")

nb_devoirs = 0
for salle in toutes_salles[:8]:
    inscrits = list(Inscription.objects.filter(
        salle=salle, annee=annee, statut='ACTIVE'
    ).select_related('eleve'))

    for ms in MatiereSalle.objects.filter(salle=salle)[:3]:
        # Devoir clos avec soumissions et corrections
        d_clos, created = Devoir.objects.get_or_create(
            matiere_salle=ms, titre=f"DM1 — {ms.matiere.nom}",
            defaults={
                'type': 'DEVOIR',
                'description': f"Devoir maison N°1 de {ms.matiere.nom}.",
                'date_limite': date(2025,11,30),
                'note_sur': 20, 'statut': 'CLOS',
                'publie_par': ms.professeur,
            }
        )
        nb_devoirs += 1
        if created:
            for insc in random.sample(inscrits, int(len(inscrits) * 0.75)):
                SoumissionDevoir.objects.get_or_create(
                    devoir=d_clos, eleve=insc.eleve,
                    defaults={
                        'contenu_texte': f"Mon travail pour {ms.matiere.nom}.",
                        'statut': 'CORRIGE',
                        'note': Decimal(str(round(random.uniform(8, 20), 1))),
                        'commentaire_prof': random.choice([
                            'Bon travail', 'Peut mieux faire',
                            'Excellent', 'Effort à fournir',
                        ]),
                        'corrige_par': ms.professeur,
                        'date_correction': timezone.now() - timedelta(days=random.randint(1,10)),
                    }
                )

        # Devoir actif en cours
        Devoir.objects.get_or_create(
            matiere_salle=ms, titre=f"DM2 — {ms.matiere.nom}",
            defaults={
                'type': 'DEVOIR',
                'description': f"Devoir maison N°2 de {ms.matiere.nom}.",
                'date_limite': today + timedelta(days=random.randint(3,14)),
                'note_sur': 20, 'statut': 'PUBLIE',
                'publie_par': ms.professeur,
            }
        )
        nb_devoirs += 1

print(f"  ✓ {nb_devoirs} devoirs")


# ══════════════════════════════════════════════════════════════
# 14 — PRE-INSCRIPTIONS ET DEPENSES
# ══════════════════════════════════════════════════════════════
print("\n[14/14] Pré-inscriptions et dépenses...")

for i in range(10):
    sexe = random.choice(['M', 'F'])
    nom = random.choice(NOMS)
    prenom = random.choice(PRENOMS_M if sexe == 'M' else PRENOMS_F)
    statut_pi = random.choice(['EN_ATTENTE','EN_ATTENTE','VALIDEE','REJETEE'])
    PreInscription.objects.create(
        nom_eleve=nom, prenom_eleve=prenom, sexe_eleve=sexe,
        niveau_souhaite=random.choice([n.nom for n in tous_niveaux]),
        nom_parent=nom, prenom_parent=random.choice(PRENOMS_F),
        telephone_parent=tel(), telephone_wa_parent=tel(),
        statut=statut_pi,
        traitee_par=secretaires[0] if statut_pi in ['VALIDEE','REJETEE'] else None,
        date_traitement=timezone.now() if statut_pi in ['VALIDEE','REJETEE'] else None,
    )

for libelle, type_d, montant, date_d in [
    ('Achat fournitures scolaires', 'FOURNITURES', 85000,  date(2025,10,5)),
    ('Réparation tableau',          'MAINTENANCE',  45000,  date(2025,10,15)),
    ('Achat matériel informatique', 'EQUIPEMENT',  350000, date(2025,11,2)),
    ('Facture électricité',         'CHARGES',      75000,  date(2025,11,30)),
    ('Achat papier et cartouches',  'FOURNITURES',  35000,  date(2025,12,5)),
    ('Réparation plomberie',        'MAINTENANCE',  55000,  date(2025,12,10)),
    ('Salaires agents octobre',     'SALAIRES',    850000, date(2025,10,30)),
    ('Salaires agents novembre',    'SALAIRES',    850000, date(2025,11,30)),
    ('Internet et téléphone',       'CHARGES',      45000,  date(2025,10,31)),
    ('Achat mobilier',              'EQUIPEMENT',  280000, date(2025,10,20)),
]:
    Depense.objects.get_or_create(
        libelle=libelle, date=date_d,
        defaults={'type': type_d, 'montant': montant, 'enregistre_par': random.choice(comptables)}
    )

print("  ✓ 10 pré-inscriptions, 10 dépenses")


# ══════════════════════════════════════════════════════════════
# RESUME
# ══════════════════════════════════════════════════════════════
print("\n" + "="*60)
print("RÉSUMÉ")
print("="*60)
print(f"  Personnel    : {CustomUser.objects.exclude(role__in=['ELEVE','PARENT']).count()}")
print(f"  Élèves       : {Eleve.objects.count()}")
print(f"  Parents      : {CustomUser.objects.filter(role='PARENT').count()}")
print(f"  Salles       : {SalleClasse.objects.filter(annee=annee).count()}")
print(f"  Évaluations  : {Evaluation.objects.count()}")
print(f"  Notes        : {Note.objects.count()}")
print(f"  Paiements    : {Paiement.objects.count()}")
print(f"  Sanctions    : {Sanction.objects.count()}")
print(f"  Devoirs      : {Devoir.objects.count()}")
print("="*60)
print("\nCOMPTES DE CONNEXION")
print("="*60)
print("  DIRECTEUR   : roland.directeur  / bakhita2025")
print("  DIRECTEUR   : marie.directeur   / bakhita2025")
print("  CENSEUR     : paul.censeur      / bakhita2025")
print("  SECRETAIRE  : ama.secretaire    / bakhita2025")
print("  COMPTABLE   : kofi.comptable    / bakhita2025")
print("  SURVEILLANT : komi.surveillant  / bakhita2025")
print("  PROFESSEUR  : jean.koffi        / bakhita2025")
print("  PARENT      : p0001             / parent2025")
print("  ELEVE       : e0001             / eleve2025")
print("="*60)
print("\n✅ Peuplement terminé !")
