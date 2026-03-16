from django.shortcuts import render, redirect, get_object_or_404
from django.db import models
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from .models import Notification, Message, Communique
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
                    message=f"{f.eleve.nom_complet} a un solde de {f.solde} FCFA pour {f.type_frais.nom}.",
                    type='ALERTE',
                    lien=f'/finance/eleve/{f.eleve.pk}/'
                )
