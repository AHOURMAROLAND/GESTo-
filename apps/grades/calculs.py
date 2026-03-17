from decimal import Decimal, ROUND_HALF_UP
from django.db.models import Avg, Count
from .models import (
    Note, NoteComposition, MoyenneMatiere, MoyenneGenerale,
    Evaluation
)
from apps.academic.models import MatiereSalle, SalleClasse, Periode
from apps.students.models import Inscription


def calculer_moyenne_matiere(eleve, matiere_salle, periode):
    """
    Calcule la moyenne d'un eleve pour une matiere sur une periode.
    Formule : (Moy.Devoirs + Note.Composition) / 2
    Si pas de composition : Moy.Devoirs uniquement
    """
    evals = Evaluation.objects.filter(
        matiere_salle=matiere_salle,
        periode=periode,
        statut='VALIDEE_FINALE',
        type__in=['DEVOIR', 'INTERROGATION', 'TP'],
    )

    notes_devoirs = Note.objects.filter(
        evaluation__in=evals,
        eleve=eleve,
        est_absent=False,
        valeur__isnull=False,
        est_validee=True,
    )

    moy_devoirs = None
    if notes_devoirs.exists():
        total = sum(
            n.valeur * Decimal('20') / n.evaluation.note_sur
            for n in notes_devoirs
        )
        moy_devoirs = total / notes_devoirs.count()

    # Note composition
    try:
        compo = NoteComposition.objects.get(
            matiere_salle=matiere_salle,
            periode=periode,
            eleve=eleve,
            est_absent=False,
        )
        # On ramene sur 20 si ce n'est pas dejà le cas (par defaut c'est sur 20)
        note_compo = compo.valeur * Decimal('20') / Decimal('20') if compo.valeur else None
    except NoteComposition.DoesNotExist:
        note_compo = None

    # Calcul moyenne finale
    if moy_devoirs is not None and note_compo is not None:
        moy_finale = (moy_devoirs + note_compo) / 2
    elif moy_devoirs is not None:
        moy_finale = moy_devoirs
    elif note_compo is not None:
        moy_finale = note_compo
    else:
        moy_finale = Decimal('0')

    moy_arrondie = moy_finale.quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP
    )

    return {
        'moyenne': moy_arrondie,
        'moy_devoirs': moy_devoirs.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if moy_devoirs else None,
        'note_compo': note_compo.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if note_compo else None,
        'points': (moy_arrondie * matiere_salle.coefficient).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
    }


def calculer_moyennes_salle(salle, periode):
    """
    Calcule et enregistre les moyennes de tous les eleves d'une salle
    pour une periode donnee.
    """
    inscrits = Inscription.objects.filter(
        salle=salle, annee=periode.annee, statut='ACTIVE'
    ).select_related('eleve')

    matieres = MatiereSalle.objects.filter(
        salle=salle
    ).select_related('matiere', 'groupe')

    resultats = {}

    for insc in inscrits:
        eleve = insc.eleve
        total_points = 0
        total_coeff = 0
        moyennes_matieres = []

        for ms in matieres:
            res = calculer_moyenne_matiere(eleve, ms, periode)
            moy, created = MoyenneMatiere.objects.update_or_create(
                eleve=eleve,
                matiere_salle=ms,
                periode=periode,
                defaults={
                    'moyenne_eleve': res['moyenne'],
                    'note_composition': res['note_compo'],
                    'points': res['points'],
                }
            )
            moyennes_matieres.append(moy)
            if not ms.est_facultative:
                total_points += res['points']
                total_coeff += ms.coefficient

        moy_gen = total_points / total_coeff if total_coeff > 0 else Decimal('0')
        moy_gen = moy_gen.quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )

        resultats[eleve.pk] = {
            'eleve': eleve,
            'moyenne': moy_gen,
            'matieres': moyennes_matieres,
        }

    # Calculer les moyennes de classe par matiere
    for ms in matieres:
        moys = MoyenneMatiere.objects.filter(
            matiere_salle=ms, periode=periode
        ).values_list('moyenne_eleve', flat=True)
        if moys:
            moy_classe = sum(moys) / len(moys)
            MoyenneMatiere.objects.filter(
                matiere_salle=ms, periode=periode
            ).update(moyenne_classe=moy_classe.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

    # Classement
    eleves_tries = sorted(
        resultats.values(),
        key=lambda x: x['moyenne'],
        reverse=True
    )

    moys_toutes = [r['moyenne'] for r in eleves_tries]
    moy_classe_gen = (
        sum(moys_toutes) / len(moys_toutes) if moys_toutes else Decimal('0')
    )
    moy_forte = max(moys_toutes) if moys_toutes else Decimal('0')
    moy_faible = min(moys_toutes) if moys_toutes else Decimal('0')
    effectif = len(eleves_tries)

    for rang, res in enumerate(eleves_tries, 1):
        eleve = res['eleve']
        moy = res['moyenne']

        mention = ''
        tableau_honneur = False
        if moy >= 16:
            mention = 'Excellent'
            tableau_honneur = True
        elif moy >= 14:
            mention = 'Tres Bien'
            tableau_honneur = True
        elif moy >= 12:
            mention = 'Bien'
        elif moy >= 10:
            mention = 'Assez Bien'
        elif moy >= 8:
            mention = 'Passable'
        else:
            mention = 'Insuffisant'

        # Absences et retards
        from apps.attendance.models import Presence
        nb_absences = Presence.objects.filter(
            eleve=eleve,
            seance__date__gte=periode.date_debut or periode.annee.date_debut,
            seance__date__lte=periode.date_fin or periode.annee.date_fin,
            statut__in=['ABSENT', 'ABSENT_JUSTIFIE'],
        ).count() if (periode.date_debut or periode.annee.date_debut) and (periode.date_fin or periode.annee.date_fin) else 0

        nb_retards = Presence.objects.filter(
            eleve=eleve,
            seance__date__gte=periode.date_debut or periode.annee.date_debut,
            seance__date__lte=periode.date_fin or periode.annee.date_fin,
            statut__in=['RETARD', 'RETARD_JUSTIFIE'],
        ).count() if (periode.date_debut or periode.annee.date_debut) and (periode.date_fin or periode.annee.date_fin) else 0

        MoyenneGenerale.objects.update_or_create(
            eleve=eleve,
            periode=periode,
            defaults={
                'moyenne': moy,
                'rang': rang,
                'effectif_classe': effectif,
                'moy_la_plus_forte': moy_forte,
                'moy_la_plus_faible': moy_faible,
                'moy_de_la_classe': moy_classe_gen.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                'mention_travail': mention,
                'tableau_honneur': tableau_honneur,
                'nb_absences': nb_absences,
                'nb_retards': nb_retards,
            }
        )

    return resultats


def calculer_toutes_salles(periode):
    """Lance le calcul pour toutes les salles actives de l'annee."""
    salles = SalleClasse.objects.filter(
        annee=periode.annee, est_active=True
    )
    for salle in salles:
        calculer_moyennes_salle(salle, periode)
    return salles.count()
