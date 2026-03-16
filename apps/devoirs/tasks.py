def notifier_nouveau_devoir(devoir_pk):
    """Notifie les eleves et parents d'un nouveau devoir publié."""
    try:
        from apps.devoirs.models import Devoir
        from apps.communication.bots import envoyer_bot
        from apps.communication.models import Notification
        from apps.students.models import EleveParent

        devoir = Devoir.objects.select_related(
            'matiere_salle__salle',
            'matiere_salle__matiere',
        ).get(pk=devoir_pk)

        inscrits = devoir.matiere_salle.salle.inscriptions.filter(
            statut='ACTIVE'
        ).select_related('eleve__user')

        lien = f'/devoirs/{devoir_pk}/'

        for insc in inscrits:
            eleve = insc.eleve

            # Notification in-app eleve
            if eleve.user:
                Notification.creer(
                    destinataire=eleve.user,
                    titre=f"Nouveau devoir : {devoir.titre}",
                    message=(
                        f"{devoir.matiere_salle.matiere.nom} — "
                        f"A rendre avant le "
                        f"{devoir.date_limite.strftime('%d/%m/%Y')}"
                    ),
                    type='INFO',
                    lien=lien,
                )

            # Bot B28 aux parents
            parents = EleveParent.objects.filter(
                eleve=eleve
            ).select_related('parent__user')

            for ep in parents:
                if ep.parent.user:
                    envoyer_bot('B28', {
                        'titre': devoir.titre,
                        'matiere': devoir.matiere_salle.matiere.nom,
                        'classe': devoir.matiere_salle.salle.nom,
                        'date_limite': devoir.date_limite.strftime('%d/%m/%Y'),
                        'lien': lien,
                    }, destinataire_user=ep.parent.user)

    except Exception as e:
        print(f"[devoirs.tasks] Erreur notifier_nouveau_devoir: {e}")


def rappels_devoirs():
    """
    Tache django-q quotidienne :
    envoie un rappel B29 pour les devoirs dont la limite est demain.
    """
    try:
        from django.utils import timezone
        from apps.devoirs.models import Devoir, SoumissionDevoir
        from apps.communication.bots import envoyer_bot

        demain = timezone.now().date() + timezone.timedelta(days=1)

        devoirs = Devoir.objects.filter(
            date_limite=demain,
            statut='PUBLIE',
        ).select_related(
            'matiere_salle__salle',
            'matiere_salle__matiere',
        )

        for devoir in devoirs:
            inscrits = devoir.matiere_salle.salle.inscriptions.filter(
                statut='ACTIVE'
            ).select_related('eleve__user')

            soumis_ids = set(
                SoumissionDevoir.objects.filter(
                    devoir=devoir
                ).values_list('eleve_id', flat=True)
            )

            for insc in inscrits:
                eleve = insc.eleve
                if eleve.pk in soumis_ids:
                    continue

                if eleve.user:
                    envoyer_bot('B29', {
                        'titre': devoir.titre,
                        'matiere': devoir.matiere_salle.matiere.nom,
                        'date_limite': devoir.date_limite.strftime('%d/%m/%Y'),
                    }, destinataire_user=eleve.user)

    except Exception as e:
        print(f"[devoirs.tasks] Erreur rappels_devoirs: {e}")
