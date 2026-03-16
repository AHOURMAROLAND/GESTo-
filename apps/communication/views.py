from django.shortcuts import render, redirect, get_object_or_404
from django.db import models
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from .models import Notification, Message, Communique, LogBot, EvenementCalendrier, ReunionParent
from apps.authentication.models import CustomUser


def role_requis(*roles):
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            if not (request.user.is_superuser or request.user.role in roles):
                messages.error(request, "Acces refuse.")
                return redirect('dashboard')
            return view_func(request, *args, **kwargs)
        wrapper.__name__ = view_func.__name__
        return wrapper
    return decorator


# ── NOTIFICATIONS ─────────────────────────────────────────────────────────────

@login_required
def liste_notifications(request):
    base_notifs = Notification.objects.filter(destinataire=request.user)
    notifs = base_notifs.order_by('-created_at')[:50]

    return render(request, 'communication/notifications.html', {
        'notifs': notifs,
        'nb_non_lues': base_notifs.filter(est_lue=False).count(),
    })


@login_required
def marquer_lue(request, pk):
    if request.method == 'POST':
        notif = get_object_or_404(
            Notification, pk=pk, destinataire=request.user
        )
        notif.est_lue = True
        notif.save()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'ok': True})
    return redirect('liste_notifications')


@login_required
def tout_marquer_lu(request):
    if request.method == 'POST':
        Notification.objects.filter(
            destinataire=request.user, est_lue=False
        ).update(est_lue=True)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'ok': True})
    return redirect('liste_notifications')


@login_required
def nb_notifications(request):
    """API endpoint pour le compteur temps reel."""
    nb = Notification.objects.filter(
        destinataire=request.user, est_lue=False
    ).count()
    return JsonResponse({'nb': nb})


# ── SESSION ───────────────────────────────────────────────────────────────────

@login_required
def prolonger_session(request):
    if request.method == 'POST':
        request.session['last_activity'] = timezone.now().timestamp()
        request.session.modified = True
        return JsonResponse({'ok': True})
    return JsonResponse({'ok': False})


# ── MESSAGES INTERNES ─────────────────────────────────────────────────────────

@login_required
def messagerie(request):
    base_recus = Message.objects.filter(destinataire=request.user)
    
    recus = base_recus.select_related('expediteur').order_by('-created_at')[:30]

    envoyes = Message.objects.filter(
        expediteur=request.user
    ).select_related('destinataire').order_by('-created_at')[:30]

    communiques = Communique.objects.all().order_by('-created_at')[:20]

    nb_non_lus = base_recus.filter(est_lu=False).count()

    return render(request, 'communication/messagerie.html', {
        'recus': recus,
        'envoyes': envoyes,
        'communiques': communiques,
        'nb_non_lus': nb_non_lus,
    })


@login_required
def nouveau_message(request):
    personnel = CustomUser.objects.filter(
        is_active=True
    ).exclude(pk=request.user.pk).order_by('last_name')

    if request.method == 'POST':
        destinataire_pk = request.POST.get('destinataire_id')
        sujet = request.POST.get('sujet', '').strip()
        contenu = request.POST.get('contenu', '').strip()
        en_reponse_pk = request.POST.get('en_reponse_a') or None

        if not all([destinataire_pk, sujet, contenu]):
            messages.error(request, "Tous les champs sont obligatoires.")
            return redirect('nouveau_message')

        msg = Message.objects.create(
            expediteur=request.user,
            destinataire_id=destinataire_pk,
            sujet=sujet,
            contenu=contenu,
            en_reponse_a_id=en_reponse_pk,
        )

        # Notifier le destinataire
        Notification.creer(
            destinataire_id=destinataire_pk,
            titre=f"Nouveau message de {request.user.nom_complet}",
            message=f"Sujet : {sujet}",
            type='INFO',
            lien=f'/messagerie/message/{msg.pk}/',
        )

        messages.success(request, "Message envoye.")
        return redirect('messagerie')

    en_reponse = None
    rep_pk = request.GET.get('reponse')
    if rep_pk:
        try:
            en_reponse = Message.objects.get(pk=rep_pk)
        except Message.DoesNotExist:
            pass

    return render(request, 'communication/nouveau_message.html', {
        'personnel': personnel,
        'en_reponse': en_reponse,
    })


@login_required
def detail_message(request, pk):
    msg = get_object_or_404(Message, pk=pk)

    if msg.destinataire == request.user and not msg.est_lu:
        msg.est_lu = True
        msg.date_lecture = timezone.now()
        msg.save()

    return render(request, 'communication/detail_message.html', {'msg': msg})


# ── COMMUNIQUES ───────────────────────────────────────────────────────────────

@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def nouveau_communique(request):
    if request.method == 'POST':
        sujet = request.POST.get('sujet', '').strip()
        contenu = request.POST.get('contenu', '').strip()
        cible = request.POST.get('cible', 'TOUS')

        if not all([sujet, contenu]):
            messages.error(request, "Sujet et contenu sont obligatoires.")
            return redirect('nouveau_communique')

        communique = Communique.objects.create(
            expediteur=request.user,
            sujet=sujet,
            contenu=contenu,
            cible=cible,
        )

        # Notifier selon la cible
        destinataires = _get_destinataires_communique(cible)
        for dest in destinataires:
            Notification.creer(
                destinataire=dest,
                titre=f"Communique : {sujet}",
                message=contenu[:100] + ('...' if len(contenu) > 100 else ''),
                type='INFO',
                lien='/messagerie/',
            )

        messages.success(
            request,
            f"Communique envoye a {len(destinataires)} personne(s)."
        )
        return redirect('messagerie')

    return render(request, 'communication/nouveau_communique.html', {
        'cibles': Communique.CIBLES,
    })


def _get_destinataires_communique(cible):
    if cible == 'TOUS':
        return list(CustomUser.objects.filter(is_active=True))
    elif cible == 'PROFESSEURS':
        return list(CustomUser.objects.filter(role='PROFESSEUR', is_active=True))
    elif cible == 'PARENTS':
        return list(CustomUser.objects.filter(role='PARENT', is_active=True))
    elif cible == 'ELEVES':
        return list(CustomUser.objects.filter(role='ELEVE', is_active=True))
    elif cible == 'PERSONNEL':
        return list(CustomUser.objects.filter(
            is_active=True
        ).exclude(role__in=['PARENT', 'ELEVE']))
    return []


# ── ALERTES AUTOMATIQUES ──────────────────────────────────────────────────────

def creer_alertes_presences():
    """
    Lance les verifications de seuils et cree les alertes.
    Appele par django-q en tache de fond.
    """
    from apps.academic.models import AnneeScolaire, Periode
    from apps.attendance.models import Presence
    from apps.students.models import Inscription
    from apps.core.models import ConfigurationEcole

    config = ConfigurationEcole.get()
    annee = AnneeScolaire.active()
    if not annee:
        return

    periode = Periode.active(annee)
    if not periode:
        return

    surveillants = CustomUser.objects.filter(
        role__in=['SURVEILLANT', 'CENSEUR', 'DIRECTEUR'], is_active=True
    )

    inscrits = Inscription.objects.filter(
        annee=annee, statut='ACTIVE'
    ).select_related('eleve')

    for insc in inscrits:
        eleve = insc.eleve

        # Seuil 1 — retards consecutifs
        derniers_retards = Presence.objects.filter(
            eleve=eleve,
            statut__in=['RETARD', 'RETARD_JUSTIFIE'],
        ).order_by('-seance__date')[
            :config.seuil_retards_consecutifs
        ]

        if derniers_retards.count() >= config.seuil_retards_consecutifs:
            msg_titre = (
                f"Alerte : {eleve.nom_complet} — "
                f"{config.seuil_retards_consecutifs} retards consecutifs"
            )
            for dest in surveillants:
                if not Notification.objects.filter(
                    destinataire=dest,
                    titre=msg_titre,
                    est_lue=False,
                ).exists():
                    Notification.creer(
                        destinataire=dest,
                        titre=msg_titre,
                        message=(
                            f"{eleve.nom_complet} a accumule "
                            f"{config.seuil_retards_consecutifs} retards consecutifs."
                        ),
                        type='ALERTE',
                        lien=f'/presences/eleve/{eleve.pk}/',
                    )

        # Seuil 2 — absences par periode
        if periode.date_debut and periode.date_fin:
            nb_absences = Presence.objects.filter(
                eleve=eleve,
                seance__date__gte=periode.date_debut,
                seance__date__lte=periode.date_fin,
                statut='ABSENT',
            ).count()

            if nb_absences >= config.seuil_jours_periode:
                msg_titre = (
                    f"Alerte : {eleve.nom_complet} — "
                    f"{nb_absences} absences cette periode"
                )
                for dest in surveillants:
                    if not Notification.objects.filter(
                        destinataire=dest,
                        titre=msg_titre,
                        est_lue=False,
                    ).exists():
                        Notification.creer(
                            destinataire=dest,
                            titre=msg_titre,
                            message=(
                                f"{eleve.nom_complet} a depasse le seuil de "
                                f"{config.seuil_jours_periode} absences."
                            ),
                            type='ALERTE',
                            lien=f'/presences/eleve/{eleve.pk}/',
                        )


def creer_alertes_evaluations():
    """Alertes pour les evaluations en attente de validation (pour le censeur)."""
    from apps.grades.models import Evaluation
    
    evals = Evaluation.objects.filter(statut='NOTES_SAISIES')
    censeurs = CustomUser.objects.filter(role='CENSEUR', is_active=True)
    
    for ev in evals:
        titre = f"Validation requise : {ev.titre}"
        for c in censeurs:
            if not Notification.objects.filter(destinataire=c, titre=titre, est_lue=False).exists():
                Notification.creer(
                    destinataire=c,
                    titre=titre,
                    message=f"L'evaluation '{ev.titre}' ({ev.matiere_salle.salle.nom}) attend votre validation.",
                    type='AVERTISSEMENT',
                    lien=f'/notes/evaluations/{ev.pk}/'
                )


def creer_alertes_finances():
    """Alertes pour les impayes (Directeur et Comptable)."""
    from apps.finance.models import FraisEleve
    
    impayes = FraisEleve.objects.filter(montant_paye__lt=models.F('montant'))
    destinataires = CustomUser.objects.filter(role__in=['DIRECTEUR', 'COMPTABLE'], is_active=True)
    
    # On pourrait grouper par eleve pour eviter trop de notifications
    for f in impayes:
        titre = f"Impaye : {f.eleve.nom_complet}"
        for dest in destinataires:
            if not Notification.objects.filter(destinataire=dest, titre=titre, est_lue=False).exists():
                Notification.creer(
                    destinataire=dest,
                    titre=titre,
                    message=f"{f.eleve.nom_complet} a un solde de {f.solde} FCFA for {f.type_frais.nom}.",
                    type='ALERTE',
                    lien=f'/finance/eleve/{f.eleve.pk}/'
                )


@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def logs_bots(request):
    logs = LogBot.objects.select_related(
        'destinataire'
    ).order_by('-created_at')[:100]

    stats = {
        'envoyes': LogBot.objects.filter(statut='ENVOYE').count(),
        'echecs': LogBot.objects.filter(statut='ECHEC').count(),
        'skips': LogBot.objects.filter(statut='SKIP').count(),
    }

    return render(request, 'communication/logs_bots.html', {
        'logs': logs,
        'stats': stats,
    })


@login_required
def verifier_wa_view(request):
    from django.http import JsonResponse
    from .bots import valider_numero_wa, verifier_numero_wa_api
    numero = request.GET.get('numero', '')
    if not numero:
        return JsonResponse({'valide': False, 'message': 'Numero vide'})
    valide, numero_formate, msg_format = valider_numero_wa(numero)
    if not valide:
        return JsonResponse({'valide': False, 'message': msg_format})
    existe, msg_api = verifier_numero_wa_api(numero_formate)
    return JsonResponse({
        'valide': existe,
        'numero_formate': numero_formate,
        'message': msg_api,
    })


# ── CALENDRIER SCOLAIRE ───────────────────────────────────────────────────────

@login_required
def calendrier(request):
    from apps.academic.models import AnneeScolaire
    annee = AnneeScolaire.active()
    mois_f = request.GET.get('mois', '')
    type_f = request.GET.get('type', '')

    evenements = EvenementCalendrier.objects.filter(
        annee=annee
    ).order_by('date_debut') if annee else []

    if type_f:
        evenements = evenements.filter(type=type_f)

    # Grouper par mois
    from itertools import groupby
    import calendar
    from django.utils import timezone

    today = timezone.now().date()

    return render(request, 'communication/calendrier.html', {
        'evenements': evenements,
        'types': EvenementCalendrier.TYPES,
        'type_filtre': type_f,
        'annee': annee,
        'today': today,
    })


@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def nouvel_evenement(request):
    from apps.academic.models import AnneeScolaire
    annee = AnneeScolaire.active()

    if request.method == 'POST':
        titre = request.POST.get('titre', '').strip()
        type_ev = request.POST.get('type', 'EVENEMENT')
        date_debut = request.POST.get('date_debut')
        date_fin = request.POST.get('date_fin') or None
        description = request.POST.get('description', '').strip()

        if not titre or not date_debut:
            messages.error(request, "Titre et date de debut obligatoires.")
            return redirect('calendrier')

        EvenementCalendrier.objects.create(
            titre=titre,
            type=type_ev,
            date_debut=date_debut,
            date_fin=date_fin,
            description=description,
            annee=annee,
            creee_par=request.user,
        )

        # Notifier tout le personnel
        from apps.authentication.models import CustomUser
        personnel = CustomUser.objects.filter(
            is_active=True
        ).exclude(role__in=['PARENT', 'ELEVE'])

        for p in personnel:
            Notification.creer(
                destinataire=p,
                titre=f"Calendrier : {titre}",
                message=f"{dict(EvenementCalendrier.TYPES).get(type_ev, '')} — {date_debut}",
                type='INFO',
                lien='/messagerie/calendrier/',
            )

        messages.success(request, f"Evenement '{titre}' ajoute au calendrier.")
        return redirect('calendrier')

    return render(request, 'communication/nouvel_evenement.html', {
        'types': EvenementCalendrier.TYPES,
        'annee': annee,
    })


@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def supprimer_evenement(request, pk):
    if request.method == 'POST':
        ev = get_object_or_404(EvenementCalendrier, pk=pk)
        titre = ev.titre
        ev.delete()
        messages.success(request, f"'{titre}' supprime.")
    return redirect('calendrier')


# ── REUNIONS PARENTS ──────────────────────────────────────────────────────────

@login_required
def liste_reunions(request):
    from apps.academic.models import AnneeScolaire
    annee = AnneeScolaire.active()
    reunions = ReunionParent.objects.filter(
        annee=annee
    ).select_related('organisee_par') if annee else []

    return render(request, 'communication/reunions.html', {
        'reunions': reunions,
        'annee': annee,
    })


@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def nouvelle_reunion(request):
    from apps.academic.models import AnneeScolaire
    annee = AnneeScolaire.active()

    if request.method == 'POST':
        titre = request.POST.get('titre', '').strip()
        date = request.POST.get('date')
        heure = request.POST.get('heure')
        lieu = request.POST.get('lieu', 'Salle de conference').strip()
        description = request.POST.get('description', '').strip()
        envoyer_convocations = request.POST.get('envoyer_convocations') == '1'

        if not all([titre, date, heure]):
            messages.error(request, "Titre, date et heure obligatoires.")
            return redirect('liste_reunions')

        reunion = ReunionParent.objects.create(
            titre=titre,
            date=date,
            heure=heure,
            lieu=lieu,
            description=description,
            statut='PLANIFIEE',
            organisee_par=request.user,
            annee=annee,
        )

        nb_conv = 0
        if envoyer_convocations:
            from apps.authentication.models import CustomUser
            from .bots import envoyer_bot
            parents = CustomUser.objects.filter(
                role='PARENT', is_active=True
            )
            for parent in parents:
                # Notification in-app
                Notification.creer(
                    destinataire=parent,
                    titre=f"Reunion : {titre}",
                    message=f"Le {date} a {heure} — {lieu}",
                    type='INFO',
                    lien='/messagerie/reunions/',
                )
                # Bot WhatsApp
                envoyer_bot('B26', {
                    'date': date,
                    'heure': heure,
                    'lieu': lieu,
                }, destinataire_user=parent)
                nb_conv += 1

            reunion.nb_convocations_envoyees = nb_conv
            reunion.save()

        messages.success(
            request,
            f"Reunion planifiee. {nb_conv} convocation(s) envoyee(s)."
        )
        return redirect('liste_reunions')

    return render(request, 'communication/nouvelle_reunion.html', {
        'annee': annee,
    })


@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def changer_statut_reunion(request, pk):
    if request.method == 'POST':
        reunion = get_object_or_404(ReunionParent, pk=pk)
        nouveau_statut = request.POST.get('statut')
        if nouveau_statut in dict(ReunionParent.STATUTS):
            reunion.statut = nouveau_statut
            reunion.save()
            messages.success(request, "Statut mis a jour.")
    return redirect('liste_reunions')
