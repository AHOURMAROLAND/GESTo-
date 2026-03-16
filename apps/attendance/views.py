from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Count
from .models import SeancePointage, Presence
from apps.academic.models import (
    AnneeScolaire, SalleClasse, MatiereSalle, CreneauType
)
from apps.students.models import Inscription
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


# ── LISTE SEANCES ─────────────────────────────────────────────────────────────

@login_required
def liste_seances(request):
    annee = AnneeScolaire.active()
    user = request.user
    date_f = request.GET.get('date', timezone.now().date().isoformat())
    salle_f = request.GET.get('salle', '')

    if user.role == 'PROFESSEUR':
        seances = SeancePointage.objects.filter(
            matiere_salle__professeur=user,
            date=date_f,
        ).select_related(
            'matiere_salle__salle', 'matiere_salle__matiere',
            'matiere_salle__professeur', 'creneau'
        )
    elif user.role in ('DIRECTEUR', 'CENSEUR', 'SURVEILLANT', 'SECRETAIRE'):
        seances = SeancePointage.objects.filter(
            date=date_f,
        ).select_related(
            'matiere_salle__salle', 'matiere_salle__matiere',
            'matiere_salle__professeur', 'creneau'
        )
        if salle_f:
            seances = seances.filter(matiere_salle__salle__pk=salle_f)
    else:
        seances = []

    salles = SalleClasse.objects.filter(
        annee=annee, est_active=True
    ).order_by('niveau__ordre', 'nom') if annee else []

    return render(request, 'attendance/liste_seances.html', {
        'seances': seances,
        'date_filtre': date_f,
        'salle_filtre': salle_f,
        'salles': salles,
        'annee': annee,
        'aujourd_hui': timezone.now().date().isoformat(),
    })


@login_required
@role_requis('DIRECTEUR', 'CENSEUR', 'PROFESSEUR', 'SURVEILLANT')
def nouvelle_seance(request):
    annee = AnneeScolaire.active()
    user = request.user

    if user.role == 'PROFESSEUR':
        matieres_salle = MatiereSalle.objects.filter(
            professeur=user,
            salle__annee=annee,
            salle__est_active=True,
        ).select_related('salle', 'matiere', 'salle__niveau')
    else:
        matieres_salle = MatiereSalle.objects.filter(
            salle__annee=annee,
            salle__est_active=True,
        ).select_related('salle', 'matiere', 'salle__niveau')

    if request.method == 'POST':
        ms_pk = request.POST.get('matiere_salle_id')
        date = request.POST.get('date')
        creneau_pk = request.POST.get('creneau_id') or None

        if not all([ms_pk, date]):
            messages.error(request, "Tous les champs sont obligatoires.")
            return redirect('nouvelle_seance')

        ms = get_object_or_404(MatiereSalle, pk=ms_pk)

        if SeancePointage.objects.filter(
            matiere_salle=ms, date=date, creneau_id=creneau_pk
        ).exists():
            messages.error(
                request, "Une seance existe deja pour ce creneau."
            )
            return redirect('liste_seances')

        from datetime import date as dt_date
        jour = dt_date.fromisoformat(date).strftime('%A').upper()
        jours_fr = {
            'MONDAY': 'LUNDI', 'TUESDAY': 'MARDI',
            'WEDNESDAY': 'MERCREDI', 'THURSDAY': 'JEUDI',
            'FRIDAY': 'VENDREDI', 'SATURDAY': 'SAMEDI',
        }
        jour_fr = jours_fr.get(jour, jour)

        seance = SeancePointage.objects.create(
            matiere_salle=ms,
            date=date,
            jour=jour_fr,
            creneau_id=creneau_pk,
            statut='EN_COURS',
        )
        messages.success(request, "Seance creee. Pointez les eleves.")
        return redirect('pointer_presence', pk=seance.pk)

    # Creneaux disponibles selon la salle
    creneaux = {}
    for ms in matieres_salle:
        try:
            from apps.academic.models import NiveauHoraire
            grille = NiveauHoraire.objects.get(
                niveau=ms.salle.niveau, annee=annee
            )
            creneaux[ms.pk] = list(
                CreneauType.objects.filter(
                    niveau_horaire=grille, type='COURS'
                ).values('pk', 'numero', 'heure_debut', 'heure_fin')
            )
        except Exception:
            creneaux[ms.pk] = []

    import json
    return render(request, 'attendance/nouvelle_seance.html', {
        'matieres_salle': matieres_salle,
        'creneaux_json': json.dumps(creneaux),
        'aujourd_hui': timezone.now().date().isoformat(),
        'annee': annee,
    })


@login_required
def pointer_presence(request, pk):
    seance = get_object_or_404(SeancePointage, pk=pk)
    user = request.user

    # Verifier autorisation
    est_proprio = seance.matiere_salle.professeur == user
    est_admin = user.role in ('DIRECTEUR', 'CENSEUR', 'SURVEILLANT')

    if not est_proprio and not est_admin and not user.is_superuser:
        messages.error(request, "Acces refuse.")
        return redirect('liste_seances')

    # Verrou 10 minutes
    peut_modifier = seance.est_modifiable_par_prof
    if not peut_modifier and not est_admin:
        messages.warning(
            request,
            "Cette seance est verrouillee (10 minutes ecoules). "
            "Contactez un administrateur pour modification."
        )
        return redirect('liste_seances')

    inscrits = seance.matiere_salle.salle.inscriptions.filter(
        statut='ACTIVE'
    ).select_related('eleve').order_by('eleve__nom')

    presences_existantes = {
        p.eleve_id: p
        for p in Presence.objects.filter(seance=seance)
    }

    if request.method == 'POST':
        action = request.POST.get('action', 'sauvegarder')
        nb_absents = 0
        nb_retards = 0

        for insc in inscrits:
            eleve = insc.eleve
            statut = request.POST.get(
                f'statut_{eleve.pk}', 'PRESENT'
            )
            heure_arrivee = request.POST.get(
                f'heure_{eleve.pk}', ''
            ) or None
            motif = request.POST.get(f'motif_{eleve.pk}', '').strip()

            presence, created = Presence.objects.get_or_create(
                eleve=eleve,
                seance=seance,
                defaults={'pointe_par': user}
            )
            presence.statut = statut
            presence.heure_arrivee = heure_arrivee
            presence.motif = motif
            presence.pointe_par = user
            presence.save()

            if statut in ('ABSENT', 'ABSENT_JUSTIFIE'):
                nb_absents += 1
            elif statut in ('RETARD', 'RETARD_JUSTIFIE'):
                nb_retards += 1

        if action == 'soumettre':
            seance.statut = 'SOUMIS'
            seance.soumis_par = user
            seance.date_soumission = timezone.now()
            seance.save()

            # Verrou automatique apres 10 minutes
            from django_q.tasks import schedule
            try:
                schedule(
                    'apps.attendance.tasks.verrouiller_seance',
                    seance.pk,
                    schedule_type='O',
                    next_run=timezone.now() + timezone.timedelta(minutes=10),
                )
            except Exception:
                pass

            messages.success(
                request,
                f"Pointage soumis — {nb_absents} absent(s), "
                f"{nb_retards} retard(s). "
                f"Modifiable pendant 10 minutes."
            )
        else:
            messages.success(request, "Pointage sauvegarde.")

        return redirect('detail_seance', pk=pk)

    return render(request, 'attendance/pointer_presence.html', {
        'seance': seance,
        'inscrits': inscrits,
        'presences': presences_existantes,
        'peut_modifier': peut_modifier,
        'statuts': Presence.STATUTS,
    })


@login_required
def detail_seance(request, pk):
    seance = get_object_or_404(SeancePointage, pk=pk)
    presences = Presence.objects.filter(
        seance=seance
    ).select_related('eleve', 'pointe_par').order_by('eleve__nom')

    stats = {
        'presents': presences.filter(statut='PRESENT').count(),
        'absents': presences.filter(
            statut__in=['ABSENT', 'ABSENT_JUSTIFIE']
        ).count(),
        'retards': presences.filter(
            statut__in=['RETARD', 'RETARD_JUSTIFIE']
        ).count(),
        'total': presences.count(),
    }

    user = request.user
    est_proprio = seance.matiere_salle.professeur == user
    peut_modifier = seance.est_modifiable_par_prof

    return render(request, 'attendance/detail_seance.html', {
        'seance': seance,
        'presences': presences,
        'stats': stats,
        'est_proprio': est_proprio,
        'peut_modifier': peut_modifier,
    })


# ── JUSTIFICATIONS ────────────────────────────────────────────────────────────

@login_required
@role_requis('DIRECTEUR', 'CENSEUR', 'SURVEILLANT', 'SECRETAIRE')
def liste_absences(request):
    annee = AnneeScolaire.active()
    date_debut = request.GET.get('date_debut', '')
    date_fin = request.GET.get('date_fin', '')
    salle_f = request.GET.get('salle', '')
    statut_f = request.GET.get('statut', 'ABSENT')

    presences = Presence.objects.filter(
        statut__in=['ABSENT', 'RETARD', 'ABSENT_JUSTIFIE', 'RETARD_JUSTIFIE'],
        seance__matiere_salle__salle__annee=annee,
    ).select_related(
        'eleve', 'seance__matiere_salle__salle',
        'seance__matiere_salle__matiere', 'seance'
    ).order_by('-seance__date', 'eleve__nom')

    if statut_f:
        presences = presences.filter(statut=statut_f)
    if salle_f:
        presences = presences.filter(
            seance__matiere_salle__salle__pk=salle_f
        )
    if date_debut:
        presences = presences.filter(seance__date__gte=date_debut)
    if date_fin:
        presences = presences.filter(seance__date__lte=date_fin)

    salles = SalleClasse.objects.filter(
        annee=annee, est_active=True
    ).order_by('niveau__ordre', 'nom') if annee else []

    return render(request, 'attendance/liste_absences.html', {
        'presences': presences,
        'salles': salles,
        'annee': annee,
        'date_debut': date_debut,
        'date_fin': date_fin,
        'salle_filtre': salle_f,
        'statut_filtre': statut_f,
        'statuts': Presence.STATUTS,
        'total': presences.count(),
    })


@login_required
@role_requis('DIRECTEUR', 'CENSEUR', 'SURVEILLANT')
def justifier_absence(request, pk):
    if request.method == 'POST':
        presence = get_object_or_404(Presence, pk=pk)
        motif = request.POST.get('motif', '').strip()
        if presence.statut == 'ABSENT':
            presence.statut = 'ABSENT_JUSTIFIE'
        elif presence.statut == 'RETARD':
            presence.statut = 'RETARD_JUSTIFIE'
        presence.motif = motif
        presence.est_justifiee = True
        presence.modifie_par_surveillant = True
        presence.save()
        messages.success(
            request,
            f"Absence de {presence.eleve.nom_complet} justifiee."
        )
    return redirect('liste_absences')


# ── ABSENCES PAR ELEVE ────────────────────────────────────────────────────────

@login_required
def absences_eleve(request, eleve_pk):
    from apps.students.models import Eleve
    eleve = get_object_or_404(Eleve, pk=eleve_pk)
    annee = AnneeScolaire.active()

    presences = Presence.objects.filter(
        eleve=eleve,
        seance__matiere_salle__salle__annee=annee,
        statut__in=['ABSENT', 'RETARD', 'ABSENT_JUSTIFIE', 'RETARD_JUSTIFIE'],
    ).select_related(
        'seance__matiere_salle__matiere',
        'seance__matiere_salle__salle',
        'seance',
    ).order_by('-seance__date')

    stats = {
        'absences': presences.filter(statut='ABSENT').count(),
        'absences_justifiees': presences.filter(
            statut='ABSENT_JUSTIFIE'
        ).count(),
        'retards': presences.filter(statut='RETARD').count(),
        'retards_justifies': presences.filter(
            statut='RETARD_JUSTIFIE'
        ).count(),
    }

    return render(request, 'attendance/absences_eleve.html', {
        'eleve': eleve,
        'presences': presences,
        'stats': stats,
        'annee': annee,
    })


# ── RAPPORT JOURNALIER ────────────────────────────────────────────────────────

@login_required
@role_requis('DIRECTEUR', 'CENSEUR', 'SURVEILLANT')
def rapport_journalier(request):
    annee = AnneeScolaire.active()
    date_f = request.GET.get(
        'date', timezone.now().date().isoformat()
    )

    seances = SeancePointage.objects.filter(
        date=date_f,
        matiere_salle__salle__annee=annee,
    ).select_related(
        'matiere_salle__salle',
        'matiere_salle__salle__niveau',
        'matiere_salle__matiere',
        'matiere_salle__professeur',
    )

    rapport = []
    total_absents = 0
    total_retards = 0
    total_eleves = 0

    for seance in seances:
        presences = Presence.objects.filter(seance=seance)
        nb_absents = presences.filter(
            statut__in=['ABSENT', 'ABSENT_JUSTIFIE']
        ).count()
        nb_retards = presences.filter(
            statut__in=['RETARD', 'RETARD_JUSTIFIE']
        ).count()
        nb_total = presences.count()

        total_absents += nb_absents
        total_retards += nb_retards
        total_eleves += nb_total

        rapport.append({
            'seance': seance,
            'nb_absents': nb_absents,
            'nb_retards': nb_retards,
            'nb_presents': nb_total - nb_absents - nb_retards,
            'nb_total': nb_total,
            'taux': round(
                (nb_total - nb_absents) / nb_total * 100, 1
            ) if nb_total > 0 else 0,
        })

    return render(request, 'attendance/rapport_journalier.html', {
        'rapport': rapport,
        'date_filtre': date_f,
        'total_absents': total_absents,
        'total_retards': total_retards,
        'total_eleves': total_eleves,
        'taux_global': round(
            (total_eleves - total_absents) / total_eleves * 100, 1
        ) if total_eleves > 0 else 0,
        'annee': annee,
        'aujourd_hui': timezone.now().date().isoformat(),
    })
