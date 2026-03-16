from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from .models import (
    Evaluation, AutorisationSaisie, Note
)
from apps.academic.models import (
    AnneeScolaire, Periode, SalleClasse, MatiereSalle
)
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


STATUT_COLORS = {
    'BROUILLON': 'badge-gray',
    'VALIDEE': 'badge-info',
    'EN_SAISIE': 'badge-warning',
    'NOTES_SAISIES': 'badge-primary',
    'VALIDEE_FINALE': 'badge-success',
    'REJETEE': 'badge-danger',
}


# ── EVALUATIONS ───────────────────────────────────────────────────────────────

@login_required
def liste_evaluations(request):
    annee = AnneeScolaire.active()
    periode = Periode.active(annee) if annee else None

    q = request.GET.get('q', '')
    statut_f = request.GET.get('statut', '')
    salle_f = request.GET.get('salle', '')
    periode_f = request.GET.get('periode', '')

    user = request.user

    if user.role in ('DIRECTEUR', 'CENSEUR'):
        evals = Evaluation.objects.select_related(
            'matiere_salle__salle', 'matiere_salle__matiere',
            'matiere_salle__professeur', 'periode', 'creee_par'
        ).filter(
            matiere_salle__salle__annee=annee
        ) if annee else []

    elif user.role == 'PROFESSEUR':
        evals = Evaluation.objects.select_related(
            'matiere_salle__salle', 'matiere_salle__matiere',
            'matiere_salle__professeur', 'periode', 'creee_par'
        ).filter(
            matiere_salle__professeur=user,
            matiere_salle__salle__annee=annee
        ) if annee else []

    elif user.role == 'SECRETAIRE':
        evals_assignees = AutorisationSaisie.objects.filter(
            saisie_par=user, est_autorisee=True
        ).values_list('evaluation_id', flat=True)
        evals = Evaluation.objects.filter(
            pk__in=evals_assignees
        ).select_related(
            'matiere_salle__salle', 'matiere_salle__matiere',
            'matiere_salle__professeur', 'periode'
        )
    else:
        evals = []

    if hasattr(evals, 'filter'):
        if statut_f:
            evals = evals.filter(statut=statut_f)
        if salle_f:
            evals = evals.filter(matiere_salle__salle__pk=salle_f)
        if periode_f:
            evals = evals.filter(periode__pk=periode_f)
        if q:
            evals = evals.filter(
                Q(titre__icontains=q) |
                Q(matiere_salle__matiere__nom__icontains=q)
            )
        evals = evals.order_by('-date')

    salles = SalleClasse.objects.filter(
        annee=annee, est_active=True
    ).order_by('niveau__ordre', 'nom') if annee else []

    periodes = Periode.objects.filter(
        annee=annee
    ).order_by('numero') if annee else []

    return render(request, 'grades/liste_evaluations.html', {
        'evaluations': evals,
        'annee': annee,
        'periode': periode,
        'salles': salles,
        'periodes': periodes,
        'statuts': Evaluation.STATUTS,
        'statut_colors': STATUT_COLORS,
        'q': q,
        'statut_filtre': statut_f,
        'salle_filtre': salle_f,
        'total': evals.count() if hasattr(evals, 'count') else 0,
    })


@login_required
@role_requis('DIRECTEUR', 'CENSEUR', 'PROFESSEUR', 'SECRETAIRE')
def nouvelle_evaluation(request):
    annee = AnneeScolaire.active()
    if not annee:
        messages.error(request, "Aucune annee active.")
        return redirect('liste_evaluations')

    user = request.user
    periode = Periode.active(annee)

    if user.role == 'PROFESSEUR':
        matieres_salle = MatiereSalle.objects.filter(
            professeur=user, salle__annee=annee, salle__est_active=True
        ).select_related('matiere', 'salle', 'salle__niveau')
    else:
        matieres_salle = MatiereSalle.objects.filter(
            salle__annee=annee, salle__est_active=True
        ).select_related('matiere', 'salle', 'salle__niveau')

    periodes = Periode.objects.filter(annee=annee).order_by('numero')

    if request.method == 'POST':
        titre = request.POST.get('titre', '').strip()
        type_eval = request.POST.get('type', 'DEVOIR')
        date = request.POST.get('date')
        note_sur = request.POST.get('note_sur', '20')
        matiere_salle_pk = request.POST.get('matiere_salle_id')
        periode_pk = request.POST.get('periode_id')

        if not all([titre, date, matiere_salle_pk, periode_pk]):
            messages.error(request, "Tous les champs sont obligatoires.")
            return render(request, 'grades/nouvelle_evaluation.html', {
                'matieres_salle': matieres_salle,
                'periodes': periodes,
                'types': Evaluation.TYPES,
                'annee': annee,
            })

        eval_obj = Evaluation.objects.create(
            titre=titre,
            type=type_eval,
            date=date,
            note_sur=float(note_sur),
            matiere_salle_id=matiere_salle_pk,
            periode_id=periode_pk,
            statut='BROUILLON',
            creee_par=user,
        )
        messages.success(
            request,
            f"Evaluation '{titre}' creee en brouillon. "
            f"Le censeur doit la valider avant la saisie."
        )
        return redirect('detail_evaluation', pk=eval_obj.pk)

    return render(request, 'grades/nouvelle_evaluation.html', {
        'matieres_salle': matieres_salle,
        'periodes': periodes,
        'types': Evaluation.TYPES,
        'annee': annee,
        'periode_active': periode,
    })


@login_required
def detail_evaluation(request, pk):
    eval_obj = get_object_or_404(Evaluation, pk=pk)
    notes = Note.objects.filter(
        evaluation=eval_obj
    ).select_related('eleve').order_by('eleve__nom')

    try:
        autorisation = eval_obj.autorisation
    except AutorisationSaisie.DoesNotExist:
        autorisation = None

    secretaires = CustomUser.objects.filter(
        role='SECRETAIRE', is_active=True
    )

    inscrits = eval_obj.matiere_salle.salle.inscriptions.filter(
        statut='ACTIVE'
    ).select_related('eleve').order_by('eleve__nom')

    return render(request, 'grades/detail_evaluation.html', {
        'eval': eval_obj,
        'notes': notes,
        'autorisation': autorisation,
        'secretaires': secretaires,
        'inscrits': inscrits,
        'statut_color': STATUT_COLORS.get(eval_obj.statut, 'badge-gray'),
        'nb_notes': notes.filter(valeur__isnull=False).count(),
        'nb_absents': notes.filter(est_absent=True).count(),
        'total_inscrits': inscrits.count(),
    })


@login_required
@role_requis('CENSEUR', 'DIRECTEUR')
def valider_evaluation(request, pk):
    if request.method == 'POST':
        eval_obj = get_object_or_404(Evaluation, pk=pk)
        action = request.POST.get('action')

        if action == 'valider':
            eval_obj.statut = 'VALIDEE'
            eval_obj.validee_par = request.user
            eval_obj.save()
            messages.success(
                request,
                f"Evaluation '{eval_obj.titre}' validee. "
                f"Assignez maintenant un saisisseur."
            )
        elif action == 'rejeter':
            motif = request.POST.get('motif', '').strip()
            eval_obj.statut = 'REJETEE'
            eval_obj.commentaire_rejet = motif
            eval_obj.save()
            messages.warning(request, f"Evaluation rejetee.")

    return redirect('detail_evaluation', pk=pk)


@login_required
@role_requis('CENSEUR', 'DIRECTEUR')
def assigner_saisisseur(request, pk):
    if request.method == 'POST':
        eval_obj = get_object_or_404(Evaluation, pk=pk)

        if eval_obj.statut not in ('VALIDEE', 'EN_SAISIE'):
            messages.error(
                request,
                "L'evaluation doit etre validee avant d'assigner un saisisseur."
            )
            return redirect('detail_evaluation', pk=pk)

        saisisseur_pk = request.POST.get('saisisseur_id') or None

        autorisation, created = AutorisationSaisie.objects.get_or_create(
            evaluation=eval_obj,
            defaults={
                'autorise_par': request.user,
                'saisie_par_id': saisisseur_pk,
                'est_autorisee': True,
                'notes_saisies': False,
            }
        )

        if not created:
            autorisation.saisie_par_id = saisisseur_pk
            autorisation.est_autorisee = True
            autorisation.autorise_par = request.user
            autorisation.save()

        eval_obj.statut = 'EN_SAISIE'
        eval_obj.save()

        saisisseur = autorisation.saisisseur_effectif
        nom = saisisseur.nom_complet if saisisseur else "Professeur de la matiere"
        messages.success(
            request,
            f"Saisie assignee a {nom}."
        )

    return redirect('detail_evaluation', pk=pk)


@login_required
def saisir_notes(request, pk):
    eval_obj = get_object_or_404(Evaluation, pk=pk)
    user = request.user

    # Verifier autorisation
    try:
        autorisation = eval_obj.autorisation
        saisisseur = autorisation.saisisseur_effectif
        if user != saisisseur and not user.has_role('DIRECTEUR', 'CENSEUR'):
            messages.error(request, "Vous n'etes pas autorise a saisir ces notes.")
            return redirect('detail_evaluation', pk=pk)
    except AutorisationSaisie.DoesNotExist:
        if not user.has_role('DIRECTEUR', 'CENSEUR'):
            messages.error(request, "Aucune autorisation de saisie.")
            return redirect('detail_evaluation', pk=pk)
        autorisation = None

    if eval_obj.statut not in ('EN_SAISIE', 'NOTES_SAISIES', 'VALIDEE'):
        messages.error(request, "La saisie n'est pas autorisee pour cette evaluation.")
        return redirect('detail_evaluation', pk=pk)

    inscrits = eval_obj.matiere_salle.salle.inscriptions.filter(
        statut='ACTIVE'
    ).select_related('eleve').order_by('eleve__nom')

    notes_existantes = {
        n.eleve_id: n
        for n in Note.objects.filter(evaluation=eval_obj)
    }

    if request.method == 'POST':
        nb_saisies = 0
        for insc in inscrits:
            eleve = insc.eleve
            valeur_str = request.POST.get(f'note_{eleve.pk}', '').strip()
            absent = request.POST.get(f'absent_{eleve.pk}') == '1'

            note, created = Note.objects.get_or_create(
                evaluation=eval_obj,
                eleve=eleve,
                defaults={'saisie_par': user}
            )

            if absent:
                note.est_absent = True
                note.valeur = None
            elif valeur_str:
                try:
                    val = float(valeur_str.replace(',', '.'))
                    if 0 <= val <= float(eval_obj.note_sur):
                        note.valeur = val
                        note.est_absent = False
                        nb_saisies += 1
                    else:
                        messages.warning(
                            request,
                            f"Note de {eleve.nom_complet} hors limites "
                            f"(0 a {eval_obj.note_sur})."
                        )
                        continue
                except ValueError:
                    continue

            note.saisie_par = user
            note.save()

        eval_obj.statut = 'NOTES_SAISIES'
        eval_obj.save()

        if autorisation:
            autorisation.notes_saisies = True
            autorisation.save()

        messages.success(
            request,
            f"{nb_saisies} note(s) saisie(s). "
            f"En attente de validation par le censeur."
        )
        return redirect('detail_evaluation', pk=pk)

    return render(request, 'grades/saisir_notes.html', {
        'eval': eval_obj,
        'inscrits': inscrits,
        'notes': notes_existantes,
        'autorisation': autorisation,
    })


@login_required
@role_requis('CENSEUR', 'DIRECTEUR')
def valider_notes(request, pk):
    if request.method == 'POST':
        eval_obj = get_object_or_404(Evaluation, pk=pk)
        action = request.POST.get('action')

        if action == 'valider':
            Note.objects.filter(evaluation=eval_obj).update(est_validee=True)
            eval_obj.statut = 'VALIDEE_FINALE'
            eval_obj.save()
            messages.success(
                request,
                f"Notes de '{eval_obj.titre}' validees definitivement."
            )
        elif action == 'rejeter':
            eval_obj.statut = 'EN_SAISIE'
            eval_obj.save()
            messages.warning(
                request,
                "Notes rejetees — le saisisseur doit les corriger."
            )

    return redirect('detail_evaluation', pk=pk)


@login_required
@role_requis('DIRECTEUR', 'CENSEUR', 'PROFESSEUR')
def supprimer_evaluation(request, pk):
    if request.method == 'POST':
        eval_obj = get_object_or_404(Evaluation, pk=pk)
        if eval_obj.statut not in ('BROUILLON', 'REJETEE'):
            messages.error(
                request,
                "Impossible de supprimer une evaluation validee ou en cours."
            )
            return redirect('detail_evaluation', pk=pk)
        if eval_obj.creee_par != request.user and not request.user.has_role(
            'DIRECTEUR', 'CENSEUR'
        ):
            messages.error(request, "Acces refuse.")
            return redirect('liste_evaluations')
        titre = eval_obj.titre
        eval_obj.delete()
        messages.success(request, f"Evaluation '{titre}' supprimee.")
    return redirect('liste_evaluations')
