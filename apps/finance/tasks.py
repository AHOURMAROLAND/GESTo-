from django.db import models
from django.utils import timezone
from apps.finance.models import FraisEleve
from apps.academic.models import AnneeScolaire
from apps.communication.bots import bot_rappel_impaye

def verifier_impayes():
    """
    Tache django-q : verifie les impayes et declenche les bots d'escalade.
    A planifier quotidiennement.
    """
    annee = AnneeScolaire.active()
    if not annee:
        return

    today = timezone.now().date()
    frais_impayes = FraisEleve.objects.filter(
        annee=annee,
        montant_paye__lt=models.F('montant'),
    ).select_related('eleve')

    for frais in frais_impayes:
        solde = float(frais.solde)
        if solde <= 0:
            continue

        jours = (today - frais.created_at.date()).days

        if jours >= 45:
            bot_rappel_impaye(frais, niveau_escalade=3)
        elif jours >= 30:
            bot_rappel_impaye(frais, niveau_escalade=2)
        elif jours >= 15:
            bot_rappel_impaye(frais, niveau_escalade=1)
