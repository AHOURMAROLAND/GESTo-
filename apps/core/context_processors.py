def global_context(request):
    if not request.user.is_authenticated:
        return {}
    try:
        from apps.academic.models import AnneeScolaire, Periode
        annee = AnneeScolaire.active()
        periode = Periode.active(annee) if annee else None
    except Exception:
        annee = periode = None
    try:
        from apps.communication.models import Notification
        nb_notifs = Notification.objects.filter(
            destinataire=request.user, est_lue=False).count()
        notifs = Notification.objects.filter(
            destinataire=request.user).order_by('-created_at')[:8]
    except Exception:
        nb_notifs, notifs = 0, []
    try:
        from apps.grades.models import AutorisationSaisie
        taches = 0
        if request.user.role in ('SECRETAIRE', 'PROFESSEUR'):
            taches = AutorisationSaisie.objects.filter(
                saisie_par=request.user,
                est_autorisee=True,
                notes_saisies=False,
            ).count()
    except Exception:
        taches = 0
    return {
        'annee_active': annee,
        'periode_active': periode,
        'nb_notifs': nb_notifs,
        'notifs_recentes': notifs,
        'taches_en_attente': taches,
        'session_remaining': request.session.get('session_remaining', 9999),
        'session_warning': request.session.get('session_warning', False),
    }