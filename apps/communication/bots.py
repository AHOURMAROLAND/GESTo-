import requests
import re
from django.conf import settings
from django.utils import timezone
from .models import LogBot, Notification

# ── TEMPLATES 31 MESSAGES ────────────────────────────────────────────────────

PREFIXES = {
    'securite':       '[Ste Bakhita - Securite]',
    'notes':          '[Ste Bakhita - Notes]',
    'presences':      '[Ste Bakhita - Presences]',
    'finance':        '[Ste Bakhita - Finance]',
    'admin':          '[Ste Bakhita - Administration]',
    'discipline':     '[Ste Bakhita - Discipline]',
    'communication':  '[Ste Bakhita - Communication]',
    'devoirs':        '[Ste Bakhita - Devoirs]',
}

TEMPLATES = {
    # ── SECURITE ──────────────────────────────────────────────────────────────
    'B01': {
        'categorie': 'securite',
        'message': (
            "Connexion detectee sur votre compte GESTo\n"
            "Date : {date}\n"
            "Heure : {heure}\n"
            "Role : {role}\n"
            "Si ce n'est pas vous, changez votre mot de passe immediatement : {lien}"
        ),
    },
    'B02': {
        'categorie': 'securite',
        'message': (
            "Votre mot de passe GESTo vient d'etre modifie.\n"
            "Si vous n'etes pas a l'origine de ce changement, "
            "contactez l'administration."
        ),
    },
    'B03': {
        'categorie': 'securite',
        'message': (
            "Bienvenue sur GESTo - Ste Bakhita !\n"
            "Vos identifiants de connexion :\n"
            "Nom d'utilisateur : {username}\n"
            "Mot de passe : {password}\n"
            "Connectez-vous ici : {lien}\n"
            "Changez votre mot de passe a la premiere connexion."
        ),
    },

    # ── NOTES ─────────────────────────────────────────────────────────────────
    'B04': {
        'categorie': 'notes',
        'message': (
            "Bonjour {parent},\n"
            "Les notes de {eleve} ({classe}) sont disponibles "
            "pour la periode {periode}.\n"
            "Consultez l'espace parent : {lien}"
        ),
    },
    'B05': {
        'categorie': 'notes',
        'message': (
            "Bonjour {parent},\n"
            "Le bulletin de {eleve} ({classe}) pour {periode} "
            "est disponible.\n"
            "Connectez-vous pour le consulter : {lien}"
        ),
    },
    'B06': {
        'categorie': 'notes',
        'message': (
            "Bonjour {parent},\n"
            "Les resultats de l'examen '{examen}' de {eleve} "
            "sont disponibles.\n"
            "Consultez : {lien}"
        ),
    },
    'B07': {
        'categorie': 'notes',
        'message': (
            "Bonjour {parent},\n"
            "Une tache de saisie vous a ete assignee "
            "pour l'evaluation '{evaluation}' ({salle}).\n"
            "Connectez-vous : {lien}"
        ),
    },

    # ── PRESENCES ─────────────────────────────────────────────────────────────
    'B08': {
        'categorie': 'presences',
        'message': (
            "Bonjour {parent},\n"
            "{eleve} a ete signale(e) absent(e) le {date} "
            "au cours de {matiere}.\n"
            "Details : {lien}"
        ),
    },
    'B09': {
        'categorie': 'presences',
        'message': (
            "Bonjour {parent},\n"
            "{eleve} a ete signale(e) en retard le {date} "
            "(arrive(e) a {heure}).\n"
            "Details : {lien}"
        ),
    },
    'B10': {
        'categorie': 'presences',
        'message': (
            "Alerte : {eleve} a accumule {nb} retards consecutifs.\n"
            "Une convocation peut etre necessaire.\n"
            "Consulter le dossier : {lien}"
        ),
    },
    'B11': {
        'categorie': 'presences',
        'message': (
            "Alerte : {eleve} a depasse le seuil de {nb} absences "
            "cette periode.\n"
            "Consulter : {lien}"
        ),
    },
    'B12': {
        'categorie': 'presences',
        'message': (
            "Rapport presences du {date} - Ste Bakhita\n"
            "Presents : {presents}\n"
            "Absents : {absents}\n"
            "Retards : {retards}\n"
            "Taux : {taux}%\n"
            "Details : {lien}"
        ),
    },
    'B13': {
        'categorie': 'presences',
        'message': (
            "Rapport journalier presences - {date}\n"
            "Total presents : {presents}/{total}\n"
            "Total absents : {absents}\n"
            "Total retards : {retards}\n"
            "Taux global : {taux}%"
        ),
    },
    'B14': {
        'categorie': 'presences',
        'message': (
            "Absence de {eleve} justifiee.\n"
            "Motif : {motif}\n"
            "Date : {date}"
        ),
    },

    # ── FINANCE ───────────────────────────────────────────────────────────────
    'B15': {
        'categorie': 'finance',
        'message': (
            "Bonjour {parent},\n"
            "Paiement recu pour {eleve}.\n"
            "Montant : {montant} FCFA\n"
            "Recu N° : {numero_recu}\n"
            "Solde restant : {solde} FCFA"
        ),
    },
    'B16': {
        'categorie': 'finance',
        'message': (
            "Bonjour {parent},\n"
            "Rappel : {eleve} a un solde impaye de {solde} FCFA.\n"
            "Merci de regulariser au plus tot.\n"
            "Details : {lien}"
        ),
    },
    'B17': {
        'categorie': 'finance',
        'message': (
            "URGENT - Bonjour {parent},\n"
            "Le solde impaye de {eleve} est de {solde} FCFA "
            "depuis plus de 30 jours.\n"
            "Veuillez contacter l'administration.\n"
            "Details : {lien}"
        ),
    },
    'B18': {
        'categorie': 'finance',
        'message': (
            "ALERTE DIRECTION - {eleve} a un solde impaye de {solde} FCFA "
            "depuis plus de 45 jours.\n"
            "Action requise : {lien}"
        ),
    },
    'B19': {
        'categorie': 'finance',
        'message': (
            "Bonjour {parent},\n"
            "Nouvelle collecte : {nom} - Montant : {montant} FCFA.\n"
            "Concernant : {eleve} ({classe}).\n"
            "Details : {lien}"
        ),
    },

    # ── DISCIPLINE ────────────────────────────────────────────────────────────
    'B20': {
        'categorie': 'discipline',
        'message': (
            "Bonjour {parent},\n"
            "{eleve} a recu une sanction : {type_sanction}.\n"
            "Motif : {motif}\n"
            "Vous pouvez consulter le dossier : {lien}"
        ),
    },
    'B21': {
        'categorie': 'discipline',
        'message': (
            "CONVOCATION - Bonjour {parent},\n"
            "Vous etes convoque(e) a l'ecole pour {eleve}.\n"
            "Date : {date} a {heure}\n"
            "Motif : {motif}\n"
            "Merci de confirmer votre presence."
        ),
    },
    'B22': {
        'categorie': 'discipline',
        'message': (
            "Bonjour {parent},\n"
            "Une demande d'exclusion a ete soumise pour {eleve}.\n"
            "Vous serez contacte(e) par la direction.\n"
            "Details : {lien}"
        ),
    },

    # ── ADMINISTRATIF ─────────────────────────────────────────────────────────
    'B23': {
        'categorie': 'admin',
        'message': (
            "Bonjour {parent},\n"
            "Votre pre-inscription pour {eleve} a ete validee.\n"
            "Identifiants :\n"
            "Utilisateur : {username}\n"
            "Mot de passe : {password}\n"
            "Connexion : {lien}"
        ),
    },
    'B24': {
        'categorie': 'admin',
        'message': (
            "Communique de Ste Bakhita :\n"
            "{sujet}\n\n"
            "{contenu}\n\n"
            "Consultez votre espace : {lien}"
        ),
    },
    'B25': {
        'categorie': 'admin',
        'message': (
            "EDT publie : {salle}\n"
            "L'emploi du temps de {salle} est disponible.\n"
            "Consultez : {lien}"
        ),
    },
    'B26': {
        'categorie': 'admin',
        'message': (
            "Reunion parents-professeurs\n"
            "Date : {date} a {heure}\n"
            "Lieu : {lieu}\n"
            "Merci de confirmer votre presence."
        ),
    },
    'B27': {
        'categorie': 'admin',
        'message': (
            "Rapport matin - Ste Bakhita - {date}\n"
            "Eleves : {nb_eleves}\n"
            "Presents : {presents}\n"
            "Absents : {absents}\n"
            "Paiements hier : {paiements} FCFA\n"
            "Nouvelles inscriptions : {inscriptions}"
        ),
    },

    # ── DEVOIRS ───────────────────────────────────────────────────────────────
    'B28': {
        'categorie': 'devoirs',
        'message': (
            "Nouveau devoir publie : {titre}\n"
            "Matiere : {matiere} ({classe})\n"
            "Date limite : {date_limite}\n"
            "Consultez : {lien}"
        ),
    },
    'B29': {
        'categorie': 'devoirs',
        'message': (
            "Rappel : Le devoir '{titre}' ({matiere}) est a rendre "
            "avant le {date_limite}.\n"
            "Vous n'avez pas encore soumis votre travail."
        ),
    },

    # ── COMMUNICATION ─────────────────────────────────────────────────────────
    'B30': {
        'categorie': 'communication',
        'message': (
            "Bonjour {destinataire},\n"
            "Vous avez un nouveau message de {expediteur}.\n"
            "Sujet : {sujet}\n"
            "Connectez-vous pour lire : {lien}"
        ),
    },
    'B31': {
        'categorie': 'communication',
        'message': (
            "Bonjour,\n"
            "Votre certificat de scolarite est disponible.\n"
            "Vous pouvez le retirer a l'administration.\n"
            "N° : {numero}"
        ),
    },
}


# ── FONCTION CENTRALE ─────────────────────────────────────────────────────────

def envoyer_bot(code_bot, contexte, destinataire_user=None, numero=None):
    """
    Fonction centrale pour envoyer un message WhatsApp.

    Args:
        code_bot: ex 'B01', 'B04'...
        contexte: dict avec les variables du template
        destinataire_user: instance CustomUser (pour recuperer le numero WA)
        numero: numero direct si pas de user (ex: +22890000000)

    Returns:
        True si envoye, False sinon
    """
    if code_bot not in TEMPLATES:
        return False

    template = TEMPLATES[code_bot]
    categorie = template['categorie']
    prefix = PREFIXES.get(categorie, '[Ste Bakhita]')

    # Construire le message
    try:
        message_body = template['message'].format(**contexte)
    except KeyError:
        message_body = template['message']

    message_complet = f"{prefix}\n{message_body}"

    # Determiner le numero destinataire
    tel = numero
    if not tel and destinataire_user:
        tel = getattr(destinataire_user, 'telephone_wa', '') or ''

    if not tel:
        _log_bot(code_bot, destinataire_user, 'SKIP',
                 message_complet, 'Pas de numero WA')
        return False

    # Anti-spam : 1 meme message par user par heure
    if destinataire_user and _est_spam(code_bot, destinataire_user):
        _log_bot(code_bot, destinataire_user, 'SKIP',
                 message_complet, 'Anti-spam')
        return False

    # Mode dev : affichage console si pas de cle API
    wa_key = getattr(settings, 'WA_API_KEY', '')
    if not wa_key:
        print(f"\n[BOT WA DEV] {code_bot} → {tel}")
        print(message_complet)
        print("─" * 40)
        _log_bot(code_bot, destinataire_user, 'ENVOYE',
                 message_complet, 'Mode dev (console)')
        return True

    # Envoi reel via WASenderAPI
    try:
        wa_url = getattr(settings, 'WA_BASE_URL', 'https://api.wasenderapi.com')
        r = requests.post(
            f"{wa_url}/api/send-message",
            json={
                'phoneNumber': tel,
                'message': message_complet,
            },
            headers={
                'Authorization': f'Bearer {wa_key}',
                'Content-Type': 'application/json',
            },
            timeout=10,
        )
        if r.status_code == 200:
            _log_bot(code_bot, destinataire_user, 'ENVOYE', message_complet)
            return True
        else:
            _log_bot(code_bot, destinataire_user, 'ECHEC',
                     message_complet, f"HTTP {r.status_code}")
            return False
    except Exception as e:
        _log_bot(code_bot, destinataire_user, 'ECHEC',
                 message_complet, str(e))
        return False


def envoyer_bot_groupe(code_bot, contexte, users_qs):
    """Envoie un bot a un groupe d'utilisateurs."""
    nb = 0
    for user in users_qs:
        if envoyer_bot(code_bot, contexte, destinataire_user=user):
            nb += 1
    return nb


def _est_spam(code_bot, user):
    """Verifie si le meme bot a deja ete envoye a cet user dans la derniere heure."""
    une_heure = timezone.now() - timezone.timedelta(hours=1)
    return LogBot.objects.filter(
        code_bot=code_bot,
        destinataire=user,
        statut='ENVOYE',
        created_at__gte=une_heure,
    ).exists()


def _log_bot(code_bot, user, statut, message='', erreur=''):
    """Enregistre chaque tentative d'envoi dans LogBot."""
    try:
        LogBot.objects.create(
            code_bot=code_bot,
            destinataire=user,
            canal='WA',
            statut=statut,
            message=message[:500],
            erreur=erreur[:300],
        )
    except Exception:
        pass


# ── VALIDATION NUMERO WA ──────────────────────────────────────────────────────

def valider_numero_wa(numero):
    """
    Valide et formate un numero WhatsApp.
    Retourne (valide: bool, numero_formate: str, message: str)
    """
    numero = numero.strip().replace(' ', '').replace('-', '').replace('.', '')

    if not numero.startswith('+'):
        if numero.startswith('00'):
            numero = '+' + numero[2:]
        elif numero.startswith('0') and len(numero) == 9:
            numero = '+228' + numero[1:]
        else:
            numero = '+' + numero

    if not re.match(r'^\+\d{8,15}$', numero):
        return False, numero, "Format invalide. Utilisez +228XXXXXXXX"

    return True, numero, "Format valide"


def verifier_numero_wa_api(numero):
    """
    Verifie si un numero a WhatsApp via WASenderAPI.
    Retourne (existe: bool, message: str)
    """
    wa_key = getattr(settings, 'WA_API_KEY', '')
    if not wa_key:
        return True, "Non verifie (API non configuree)"

    valide, numero_formate, msg = valider_numero_wa(numero)
    if not valide:
        return False, msg

    try:
        wa_url = getattr(settings, 'WA_BASE_URL', 'https://api.wasenderapi.com')
        r = requests.post(
            f"{wa_url}/api/check-number",
            json={'phoneNumber': numero_formate},
            headers={
                'Authorization': f'Bearer {wa_key}',
                'Content-Type': 'application/json',
            },
            timeout=5,
        )
        if r.status_code == 200:
            data = r.json()
            existe = data.get('exists', data.get('existsWhatsapp', False))
            return existe, (
                "Numero WhatsApp verifie" if existe
                else "Ce numero n'a pas WhatsApp"
            )
        return True, "Non verifie (erreur API)"
    except Exception:
        return True, "Non verifie (hors ligne)"


# ── BOTS AUTOMATIQUES ─────────────────────────────────────────────────────────

def bot_connexion(user):
    """B01 — Alerte connexion pour les 8 roles."""
    if not getattr(user, 'telephone_wa', ''):
        return
    now = timezone.now()
    envoyer_bot('B01', {
        'date': now.strftime('%d/%m/%Y'),
        'heure': now.strftime('%H:%M'),
        'role': user.get_role_display(),
        'lien': '/profil/',
    }, destinataire_user=user)


def bot_identifiants(user, password_clair):
    """B03 — Envoi identifiants a la creation de compte."""
    envoyer_bot('B03', {
        'username': user.username,
        'password': password_clair,
        'lien': '/login/',
    }, destinataire_user=user)


def bot_notes_disponibles(eleve, periode):
    """B04 — Alerte notes disponibles aux parents."""
    from apps.students.models import EleveParent
    parents = EleveParent.objects.filter(
        eleve=eleve
    ).select_related('parent__user')

    for ep in parents:
        if ep.parent.user:
            envoyer_bot('B04', {
                'parent': ep.parent.nom_complet,
                'eleve': eleve.nom_complet,
                'classe': eleve.salle_active.nom if eleve.salle_active else '',
                'periode': str(periode),
                'lien': '/login/',
            }, destinataire_user=ep.parent.user)


def bot_absence(presence):
    """B08 — Alerte absence aux parents."""
    from apps.students.models import EleveParent
    eleve = presence.eleve
    parents = EleveParent.objects.filter(
        eleve=eleve
    ).select_related('parent__user')

    for ep in parents:
        if ep.parent.user:
            envoyer_bot('B08', {
                'parent': ep.parent.nom_complet,
                'eleve': eleve.nom_complet,
                'date': presence.seance.date.strftime('%d/%m/%Y'),
                'matiere': presence.seance.matiere_salle.matiere.nom,
                'lien': '/login/',
            }, destinataire_user=ep.parent.user)


def bot_paiement_confirme(paiement):
    """B15 — Confirmation paiement au parent."""
    from apps.students.models import EleveParent
    eleve = paiement.eleve
    parents = EleveParent.objects.filter(
        eleve=eleve
    ).select_related('parent__user')

    for ep in parents:
        if ep.parent.user:
            envoyer_bot('B15', {
                'parent': ep.parent.nom_complet,
                'eleve': eleve.nom_complet,
                'montant': f"{float(paiement.montant):,.0f}",
                'numero_recu': paiement.numero_recu,
                'solde': f"{float(paiement.frais.solde):,.0f}",
            }, destinataire_user=ep.parent.user)


def bot_rappel_impaye(frais_eleve, niveau_escalade=1):
    """
    B16/B17/B18 — Escalade dette 3 niveaux.
    niveau_escalade: 1=15j, 2=30j, 3=45j
    """
    from apps.students.models import EleveParent
    eleve = frais_eleve.eleve
    solde = float(frais_eleve.solde)

    if solde <= 0:
        return

    code = {1: 'B16', 2: 'B17', 3: 'B18'}.get(niveau_escalade, 'B16')

    parents = EleveParent.objects.filter(
        eleve=eleve
    ).select_related('parent__user')

    for ep in parents:
        if ep.parent.user:
            envoyer_bot(code, {
                'parent': ep.parent.nom_complet,
                'eleve': eleve.nom_complet,
                'solde': f"{solde:,.0f}",
                'lien': '/login/',
            }, destinataire_user=ep.parent.user)

    # Niveau 3 : notifier aussi le directeur
    if niveau_escalade == 3:
        from apps.authentication.models import CustomUser
        directeurs = CustomUser.objects.filter(
            role='DIRECTEUR', is_active=True
        )
        for d in directeurs:
            envoyer_bot('B18', {
                'eleve': eleve.nom_complet,
                'solde': f"{solde:,.0f}",
                'lien': '/finance/',
            }, destinataire_user=d)


def bot_rapport_matin(directeur):
    """B27 — Rapport automatique matin pour le directeur."""
    from apps.academic.models import AnneeScolaire
    from apps.attendance.models import Presence
    from apps.finance.models import Paiement
    from apps.students.models import Inscription
    from django.db.models import Sum

    annee = AnneeScolaire.active()
    today = timezone.now().date()
    yesterday = today - timezone.timedelta(days=1)

    nb_eleves = Inscription.objects.filter(
        annee=annee, statut='ACTIVE'
    ).count() if annee else 0

    presents = Presence.objects.filter(
        seance__date=yesterday, statut='PRESENT'
    ).count()

    absents = Presence.objects.filter(
        seance__date=yesterday,
        statut__in=['ABSENT', 'ABSENT_JUSTIFIE']
    ).count()

    paiements = Paiement.objects.filter(
        date_paiement=yesterday
    ).aggregate(t=Sum('montant'))['t'] or 0

    inscriptions = Inscription.objects.filter(
        date_inscription=yesterday
    ).count()

    envoyer_bot('B27', {
        'date': yesterday.strftime('%d/%m/%Y'),
        'nb_eleves': nb_eleves,
        'presents': presents,
        'absents': absents,
        'paiements': f"{float(paiements):,.0f}",
        'inscriptions': inscriptions,
    }, destinataire_user=directeur)
