def verrouiller_seance(seance_pk):
    """Tache async — verrouille une seance apres 10 minutes."""
    try:
        from apps.attendance.models import SeancePointage
        seance = SeancePointage.objects.get(pk=seance_pk)
        if seance.statut == 'SOUMIS':
            seance.statut = 'VERROUILLE'
            seance.date_verrou = __import__(
                'django.utils.timezone', fromlist=['now']
            ).now()
            seance.save()
    except Exception:
        pass
