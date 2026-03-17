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

    peut_voir_notes = (
        request.user.is_superuser or
        request.user.role in ('DIRECTEUR', 'CENSEUR', 'SECRETAIRE') or
        (request.user.role == 'PROFESSEUR' and
         eval_obj.statut == 'VALIDEE_FINALE') or
        (request.user.role == 'PROFESSEUR' and
         eval_obj.matiere_salle.professeur == request.user)
    )

    peut_saisir = (
        eval_obj.statut == 'EN_SAISIE' and
        AutorisationSaisie.objects.filter(
            evaluation=eval_obj,
            saisie_par=request.user,
            est_autorisee=True,
            notes_saisies=False,
        ).exists()
    )

    est_lecture_seule = (
        request.user.role == 'PROFESSEUR' and
        eval_obj.statut == 'VALIDEE_FINALE'
    )

    return render(request, 'grades/detail_evaluation.html', {
        'eval': eval_obj,
        'notes': notes,
        'autorisation': autorisation,
        'secretaires': secretaires,
        'inscrits': inscrits,
        'peut_voir_notes': peut_voir_notes,
        'peut_saisir': peut_saisir,
        'est_lecture_seule': est_lecture_seule,
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

    # Droits en lecture seule pour prof après validation finale
    est_lecture_seule = (
        eval_obj.statut == 'VALIDEE_FINALE' or
        (user.role == 'PROFESSEUR' and eval_obj.statut != 'EN_SAISIE' and eval_obj.matiere_salle.professeur == user)
    )

    # Verifier autorisation pour la saisie
    peut_saisir = False
    if eval_obj.statut in ('EN_SAISIE', 'NOTES_SAISIES', 'VALIDEE'):
        try:
            autorisation = eval_obj.autorisation
            saisisseur = autorisation.saisisseur_effectif
            if user == saisisseur or user.has_role('DIRECTEUR', 'CENSEUR'):
                peut_saisir = True
        except AutorisationSaisie.DoesNotExist:
            if user.has_role('DIRECTEUR', 'CENSEUR'):
                peut_saisir = True
            autorisation = None
    else:
        try:
            autorisation = eval_obj.autorisation
        except AutorisationSaisie.DoesNotExist:
            autorisation = None

    if not peut_saisir and not est_lecture_seule and not user.has_role('DIRECTEUR', 'CENSEUR', 'SECRETAIRE'):
        messages.error(request, "Accès refusé. Vous n'êtes pas autorisé à voir ou saisir ces notes.")
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
        'est_lecture_seule': est_lecture_seule,
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

    return redirect('liste_evaluations')


@login_required
@role_requis('DIRECTEUR', 'CENSEUR', 'SECRETAIRE', 'PROFESSEUR')
def mes_taches_saisie(request):
    user = request.user
    
    # Les secrétaires voient les tâches explicitement assignées
    if user.role == 'SECRETAIRE':
        taches = AutorisationSaisie.objects.filter(
            saisie_par=user, 
            est_autorisee=True
        ).select_related(
            'evaluation', 'evaluation__matiere_salle__salle', 
            'evaluation__matiere_salle__matiere', 'evaluation__periode', 
            'autorise_par'
        )
    
    # Les professeurs voient :
    # 1. Les évaluations dont ils sont titulaires ET où aucun secrétaire n'est assigné
    # 2. Les évaluations où ils sont explicitement assignés
    elif user.role == 'PROFESSEUR':
        taches = AutorisationSaisie.objects.filter(
            (Q(evaluation__matiere_salle__professeur=user) & Q(saisie_par__isnull=True)) |
            Q(saisie_par=user),
            est_autorisee=True
        ).select_related(
            'evaluation', 'evaluation__matiere_salle__salle', 
            'evaluation__matiere_salle__matiere', 'evaluation__periode', 
            'autorise_par'
        )
    
    # Dir/Censeur voient tout ce qui est en cours de saisie
    else:
        taches = AutorisationSaisie.objects.filter(
            est_autorisee=True
        ).select_related(
            'evaluation', 'evaluation__matiere_salle__salle', 
            'evaluation__matiere_salle__matiere', 'evaluation__periode', 
            'autorise_par'
        )

    return render(request, 'grades/mes_taches_saisie.html', {
        'taches': taches,
        'nb_en_attente': taches.filter(notes_saisies=False).count(),
        'nb_terminees': taches.filter(notes_saisies=True).count(),
    })
@login_required
@role_requis('DIRECTEUR', 'CENSEUR', 'SECRETAIRE', 'PROFESSEUR', 'PARENT', 'ELEVE')
def bulletins_salle(request):
    annee = AnneeScolaire.active()
    user = request.user

    salles = SalleClasse.objects.filter(
        annee=annee, est_active=True
    ).order_by('niveau__ordre', 'nom') if annee else []

    periodes = Periode.objects.filter(
        annee=annee
    ).order_by('numero') if annee else []

    salle_pk = request.GET.get('salle', '')
    periode_pk = request.GET.get('periode', '')

    # Restriction prof — ne voit que ses salles
    if user.role == 'PROFESSEUR':
        from apps.academic.models import MatiereSalle
        salles_prof = MatiereSalle.objects.filter(
            professeur=user, salle__annee=annee
        ).values_list('salle_id', flat=True)
        salles = salles.filter(pk__in=salles_prof)

    # Restriction parent — ne voit que la salle de son enfant
    if user.role == 'PARENT':
        try:
            parent = user.profil_parent
            salles_enfants = []
            for ep in parent.enfants.all():
                insc = ep.eleve.inscription_active
                if insc:
                    salles_enfants.append(insc.salle_id)
            salles = salles.filter(pk__in=salles_enfants)
        except Exception:
            salles = SalleClasse.objects.none()

    # Restriction eleve — ne voit que sa salle
    if user.role == 'ELEVE':
        try:
            eleve = user.profil_eleve
            insc = eleve.inscription_active
            if insc:
                salles = salles.filter(pk=insc.salle_id)
                salle_pk = str(insc.salle_id)
            else:
                salles = SalleClasse.objects.none()
        except Exception:
            salles = SalleClasse.objects.none()

    bulletins = []
    salle_selectionnee = None
    periode_selectionnee = None
    stats_classe = None

    if salle_pk and periode_pk:
        try:
            salle_selectionnee = SalleClasse.objects.get(pk=salle_pk)
            periode_selectionnee = Periode.objects.get(pk=periode_pk)

            inscrits = Inscription.objects.filter(
                salle=salle_selectionnee,
                annee=annee,
                statut='ACTIVE',
            ).select_related('eleve').order_by('eleve__nom')

            matieres_salle = MatiereSalle.objects.filter(
                salle=salle_selectionnee
            ).select_related('matiere').order_by('matiere__nom')

            for insc in inscrits:
                eleve = insc.eleve

                # Moyennes par matiere
                moy_matieres = MoyenneMatiere.objects.filter(
                    eleve=eleve,
                    periode=periode_selectionnee,
                    matiere_salle__salle=salle_selectionnee,
                ).select_related(
                    'matiere_salle__matiere'
                ).order_by('matiere_salle__matiere__nom')

                # Moyenne generale
                moy_gen = MoyenneGenerale.objects.filter(
                    eleve=eleve,
                    periode=periode_selectionnee,
                ).first()

                # Si pas de moyenne calculée, calculer à la volée
                if not moy_gen:
                    moy_gen = _calculer_moyenne_generale(
                        eleve, salle_selectionnee,
                        periode_selectionnee
                    )

                bulletins.append({
                    'eleve': eleve,
                    'moy_matieres': moy_matieres,
                    'moy_gen': moy_gen,
                })

            # Trier par moyenne décroissante
            bulletins.sort(
                key=lambda x: float(x['moy_gen'].moyenne)
                if x['moy_gen'] else 0,
                reverse=True
            )

            # Calculer rang
            for i, b in enumerate(bulletins, 1):
                if b['moy_gen']:
                    b['rang'] = i

            # Stats classe
            moyennes = [
                float(b['moy_gen'].moyenne)
                for b in bulletins
                if b['moy_gen']
            ]
            if moyennes:
                stats_classe = {
                    'nb_eleves': len(bulletins),
                    'moyenne_classe': round(
                        sum(moyennes) / len(moyennes), 2
                    ),
                    'moy_max': max(moyennes),
                    'moy_min': min(moyennes),
                    'nb_admis': sum(1 for m in moyennes if m >= 10),
                    'taux_reussite': round(
                        sum(1 for m in moyennes if m >= 10)
                        / len(moyennes) * 100, 1
                    ),
                }

        except Exception as e:
            messages.error(request, f"Erreur : {e}")

    return render(request, 'grades/bulletins_salle.html', {
        'salles': salles,
        'periodes': periodes,
        'salle_selectionnee': salle_selectionnee,
        'periode_selectionnee': periode_selectionnee,
        'bulletins': bulletins,
        'stats_classe': stats_classe,
        'salle_pk': salle_pk,
        'periode_pk': periode_pk,
    })


def _calculer_moyenne_generale(eleve, salle, periode):
    """Calcule la moyenne générale à la volée si pas encore enregistrée."""
    from apps.academic.models import MatiereSalle
    from .models import MoyenneMatiere
    matieres = MatiereSalle.objects.filter(salle=salle)
    total_points = 0
    total_coef = 0

    for ms in matieres:
        moy = MoyenneMatiere.objects.filter(
            eleve=eleve, matiere_salle=ms, periode=periode
        ).first()
        if moy and moy.moyenne_eleve:
            total_points += float(moy.moyenne_eleve) * ms.coefficient
            total_coef += ms.coefficient

    if total_coef == 0:
        return None

    from apps.grades.models import MoyenneGenerale
    mg = MoyenneGenerale.__new__(MoyenneGenerale)
    mg.moyenne = round(total_points / total_coef, 2)
    mg.rang = 0
    mg.effectif_classe = 0
    return mg


@login_required
@role_requis('DIRECTEUR', 'CENSEUR', 'SECRETAIRE')
def bulletin_pdf(request, eleve_pk, periode_pk):
    """Génère le bulletin PDF d'un élève."""
    from apps.core.models import ConfigurationEcole
    from apps.students.models import Eleve, Inscription
    from .models import MoyenneMatiere, MoyenneGenerale

    eleve = get_object_or_404(Eleve, pk=eleve_pk)
    periode = get_object_or_404(Periode, pk=periode_pk)
    annee = AnneeScolaire.active()
    config = ConfigurationEcole.get()

    inscription = eleve.inscriptions.filter(
        annee=annee, statut='ACTIVE'
    ).select_related('salle__niveau').first()

    if not inscription:
        messages.error(request, "Élève non inscrit cette année.")
        return redirect('bulletins_salle')

    salle = inscription.salle

    moy_matieres = MoyenneMatiere.objects.filter(
        eleve=eleve,
        periode=periode,
        matiere_salle__salle=salle,
    ).select_related(
        'matiere_salle__matiere',
        'matiere_salle__professeur',
    ).order_by('matiere_salle__matiere__nom')

    moy_gen = MoyenneGenerale.objects.filter(
        eleve=eleve, periode=periode
    ).first()

    # Stats classe pour ce bulletin
    inscrits = Inscription.objects.filter(
        salle=salle, annee=annee, statut='ACTIVE'
    ).count()

    from django.http import HttpResponse # Ensure HttpResponse is available
    return _generer_bulletin_pdf(
        eleve, periode, salle, annee,
        moy_matieres, moy_gen, inscrits, config
    )


@login_required
@role_requis('DIRECTEUR', 'CENSEUR', 'SECRETAIRE')
def bulletins_salle_pdf(request, salle_pk, periode_pk):
    """Génère tous les bulletins d'une salle en un seul PDF."""
    from apps.core.models import ConfigurationEcole
    from reportlab.platypus import PageBreak
    from apps.students.models import Inscription
    from .models import MoyenneMatiere, MoyenneGenerale
    from django.http import HttpResponse

    salle = get_object_or_404(SalleClasse, pk=salle_pk)
    periode = get_object_or_404(Periode, pk=periode_pk)
    annee = AnneeScolaire.active()
    config = ConfigurationEcole.get()

    inscrits = Inscription.objects.filter(
        salle=salle, annee=annee, statut='ACTIVE'
    ).select_related('eleve').order_by('eleve__nom')

    import io
    buffer = io.BytesIO()

    from reportlab.platypus import SimpleDocTemplate
    from reportlab.lib.pagesizes import A4

    elements = []
    nb_inscrits = inscrits.count()

    for i, insc in enumerate(inscrits):
        eleve = insc.eleve
        moy_matieres = MoyenneMatiere.objects.filter(
            eleve=eleve, periode=periode,
            matiere_salle__salle=salle,
        ).select_related('matiere_salle__matiere')

        moy_gen = MoyenneGenerale.objects.filter(
            eleve=eleve, periode=periode
        ).first()

        els = _elements_bulletin(
            eleve, periode, salle, annee,
            moy_matieres, moy_gen, nb_inscrits, config
        )
        elements.extend(els)
        if i < nb_inscrits - 1:
            elements.append(PageBreak())

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.5*72/2.54,
        rightMargin=1.5*72/2.54,
        topMargin=1.5*72/2.54,
        bottomMargin=1.5*72/2.54,
    )
    doc.build(elements)
    buffer.seek(0)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="bulletins_{salle.nom}_{periode}.pdf"'
    )
    response.write(buffer.getvalue())
    return response


def _elements_bulletin(eleve, periode, salle, annee, moy_matieres,
                        moy_gen, nb_inscrits, config):
    """Retourne les éléments ReportLab pour un bulletin."""
    import io
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import (
        Paragraph, Spacer, Table, TableStyle, HRFlowable
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

    BLEU = colors.HexColor('#1E3A8A')
    BLEU_CLAIR = colors.HexColor('#DBEAFE')
    GRIS = colors.HexColor('#F8FAFC')
    VERT = colors.HexColor('#16A34A')
    ROUGE = colors.HexColor('#DC2626')
    OR = colors.HexColor('#D97706')

    styles = getSampleStyleSheet()

    def style(name, **kwargs):
        s = ParagraphStyle(name, parent=styles['Normal'], **kwargs)
        return s

    elements = []

    # ── EN-TETE ───────────────────────────────────────────────────────────────
    entete_data = [[
        Paragraph(
            f"République Togolaise<br/>"
            f"<b>Travail – Liberté – Patrie</b><br/>"
            f"Ministère des Enseignements",
            style('e1', fontSize=8, alignment=TA_CENTER)
        ),
        Paragraph(
            f"<b style='font-size:13px;color:#1E3A8A'>{config.nom}</b><br/>"
            f"<font size=8>{config.adresse or ''}</font><br/>"
            f"<font size=8>Tél : {config.telephone or ''}</font>",
            style('e2', fontSize=9, alignment=TA_CENTER)
        ),
        Paragraph(
            f"Année scolaire<br/><b>{annee.nom}</b><br/>"
            f"{periode}",
            style('e3', fontSize=8, alignment=TA_CENTER)
        ),
    ]]
    entete_table = Table(entete_data, colWidths=[5.5*cm, 8*cm, 5.5*cm])
    entete_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LINEBELOW', (0,0), (-1,-1), 1.5, BLEU),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(entete_table)
    elements.append(Spacer(1, 0.3*cm))

    # Titre BULLETIN
    titre_table = Table(
        [[Paragraph(
            "BULLETIN DE NOTES",
            style('titre', fontSize=14, fontName='Helvetica-Bold',
                  textColor=colors.white, alignment=TA_CENTER)
        )]],
        colWidths=[19*cm]
    )
    titre_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), BLEU),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('ROUNDEDCORNERS', [4]),
    ]))
    elements.append(titre_table)
    elements.append(Spacer(1, 0.3*cm))

    # ── INFOS ELEVE ───────────────────────────────────────────────────────────
    info_data = [
        [
            Paragraph('<b>Nom et prénoms :</b>', style('il', fontSize=9)),
            Paragraph(
                f'<b>{eleve.nom_complet}</b>',
                style('iv', fontSize=10, fontName='Helvetica-Bold')
            ),
            Paragraph('<b>Matricule :</b>', style('il', fontSize=9)),
            Paragraph(eleve.matricule, style('iv', fontSize=9)),
        ],
        [
            Paragraph('<b>Classe :</b>', style('il', fontSize=9)),
            Paragraph(salle.nom, style('iv', fontSize=9)),
            Paragraph('<b>Niveau :</b>', style('il', fontSize=9)),
            Paragraph(salle.niveau.nom, style('iv', fontSize=9)),
        ],
        [
            Paragraph('<b>Date de naissance :</b>', style('il', fontSize=9)),
            Paragraph(
                eleve.date_naissance.strftime('%d/%m/%Y')
                if eleve.date_naissance else '—',
                style('iv', fontSize=9)
            ),
            Paragraph('<b>Sexe :</b>', style('il', fontSize=9)),
            Paragraph(
                eleve.get_sexe_display(),
                style('iv', fontSize=9)
            ),
        ],
    ]
    info_table = Table(info_data, colWidths=[4*cm, 6*cm, 3.5*cm, 5.5*cm])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), GRIS),
        ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('BACKGROUND', (0,0), (0,-1), BLEU_CLAIR),
        ('BACKGROUND', (2,0), (2,-1), BLEU_CLAIR),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 0.3*cm))

    # ── TABLEAU NOTES ─────────────────────────────────────────────────────────
    header = [
        Paragraph('<b>Matière</b>', style('th', fontSize=8,
                  fontName='Helvetica-Bold', textColor=colors.white,
                  alignment=TA_CENTER)),
        Paragraph('<b>Coef</b>', style('th', fontSize=8,
                  fontName='Helvetica-Bold', textColor=colors.white,
                  alignment=TA_CENTER)),
        Paragraph('<b>Moy. élève</b>', style('th', fontSize=8,
                  fontName='Helvetica-Bold', textColor=colors.white,
                  alignment=TA_CENTER)),
        Paragraph('<b>Moy. classe</b>', style('th', fontSize=8,
                  fontName='Helvetica-Bold', textColor=colors.white,
                  alignment=TA_CENTER)),
        Paragraph('<b>Points</b>', style('th', fontSize=8,
                  fontName='Helvetica-Bold', textColor=colors.white,
                  alignment=TA_CENTER)),
        Paragraph('<b>Appréciation</b>', style('th', fontSize=8,
                  fontName='Helvetica-Bold', textColor=colors.white,
                  alignment=TA_CENTER)),
    ]

    data = [header]
    total_points = 0
    total_coef = 0

    for mm in moy_matieres:
        moy = float(mm.moyenne_eleve) if mm.moyenne_eleve else 0
        coef = mm.matiere_salle.coefficient
        points = moy * coef
        total_points += points
        total_coef += coef

        couleur_moy = (
            VERT if moy >= 14 else
            OR if moy >= 10 else
            ROUGE
        )

        data.append([
            Paragraph(
                mm.matiere_salle.matiere.nom,
                style('td', fontSize=8)
            ),
            Paragraph(
                str(coef),
                style('tdc', fontSize=8, alignment=TA_CENTER)
            ),
            Paragraph(
                f'<b><font color="{"#16A34A" if moy >= 10 else "#DC2626"}">'
                f'{moy:.2f}</font></b>',
                style('tdc', fontSize=9, alignment=TA_CENTER)
            ),
            Paragraph(
                f'{float(mm.moyenne_classe):.2f}'
                if mm.moyenne_classe else '—',
                style('tdc', fontSize=8, alignment=TA_CENTER)
            ),
            Paragraph(
                f'{points:.2f}',
                style('tdc', fontSize=8, alignment=TA_CENTER)
            ),
            Paragraph(
                mm.appreciation or '—',
                style('tda', fontSize=8)
            ),
        ])

    notes_table = Table(
        data,
        colWidths=[5*cm, 1.5*cm, 2.5*cm, 2.5*cm, 2*cm, 5.5*cm]
    )
    notes_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), BLEU),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [
            colors.white, colors.HexColor('#F8FAFC')
        ]),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    elements.append(notes_table)
    elements.append(Spacer(1, 0.3*cm))

    # ── RECAP MOYENNE GENERALE ────────────────────────────────────────────────
    moy_finale = (
        round(total_points / total_coef, 2) if total_coef > 0 else 0
    )
    if moy_gen and moy_gen.moyenne:
        moy_finale = float(moy_gen.moyenne)

    mention = (
        'Très Bien' if moy_finale >= 16 else
        'Bien' if moy_finale >= 14 else
        'Assez Bien' if moy_finale >= 12 else
        'Passable' if moy_finale >= 10 else
        'Insuffisant' if moy_finale >= 8 else
        'Très Insuffisant'
    )

    couleur_mention = (
        '#16A34A' if moy_finale >= 10 else '#DC2626'
    )

    rang = getattr(moy_gen, 'rang', '—') if moy_gen else '—'

    recap_data = [[
        Paragraph(
            f'Moyenne générale : '
            f'<b><font color="{couleur_mention}" size=14>'
            f'{moy_finale:.2f}/20</font></b>',
            style('rc', fontSize=10, alignment=TA_CENTER)
        ),
        Paragraph(
            f'Rang : <b>{rang}/{nb_inscrits}</b>',
            style('rc', fontSize=10, alignment=TA_CENTER)
        ),
        Paragraph(
            f'Mention : <b><font color="{couleur_mention}">'
            f'{mention}</font></b>',
            style('rc', fontSize=10, alignment=TA_CENTER)
        ),
    ]]
    recap_table = Table(recap_data, colWidths=[6.5*cm, 6*cm, 6.5*cm])
    recap_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), BLEU_CLAIR),
        ('GRID', (0,0), (-1,-1), 0.5, BLEU),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    elements.append(recap_table)
    elements.append(Spacer(1, 0.4*cm))

    # ── SIGNATURES ────────────────────────────────────────────────────────────
    from django.utils import timezone
    date_str = timezone.now().strftime('%d/%m/%Y')

    sig_data = [[
        Paragraph(
            f"Fait à Lomé, le {date_str}<br/><br/>"
            "Le Directeur<br/><br/><br/>",
            style('sig', fontSize=9, alignment=TA_CENTER)
        ),
        Paragraph(
            "Appréciation du conseil de classe :<br/><br/>"
            "_________________________________<br/>"
            "_________________________________",
            style('sig', fontSize=9, alignment=TA_LEFT)
        ),
        Paragraph(
            "Signature des parents :<br/><br/><br/><br/>",
            style('sig', fontSize=9, alignment=TA_CENTER)
        ),
    ]]
    sig_table = Table(sig_data, colWidths=[5.5*cm, 8*cm, 5.5*cm])
    sig_table.setStyle(TableStyle([
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOX', (0,0), (0,-1), 0.3, colors.grey),
        ('BOX', (1,0), (1,-1), 0.3, colors.grey),
        ('BOX', (2,0), (2,-1), 0.3, colors.grey),
    ]))
    elements.append(sig_table)

    return elements


def _generer_bulletin_pdf(eleve, periode, salle, annee,
                           moy_matieres, moy_gen, nb_inscrits, config):
    import io
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate
    from django.http import HttpResponse

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=1.5*72/2.54,
        rightMargin=1.5*72/2.54,
        topMargin=1.5*72/2.54,
        bottomMargin=1.5*72/2.54,
    )

    elements = _elements_bulletin(
        eleve, periode, salle, annee,
        moy_matieres, moy_gen, nb_inscrits, config
    )
    doc.build(elements)
    buffer.seek(0)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="bulletin_{eleve.matricule}_{periode}.pdf"'
    )
    response.write(buffer.getvalue())
    return response


@login_required
@role_requis('DIRECTEUR', 'CENSEUR', 'SECRETAIRE')
def proclamation(request):
    annee = AnneeScolaire.active()
    salle_pk = request.GET.get('salle', '')
    periode_pk = request.GET.get('periode', '')

    salles = SalleClasse.objects.filter(
        annee=annee, est_active=True
    ).order_by('niveau__ordre', 'nom') if annee else []

    periodes = Periode.objects.filter(
        annee=annee
    ).order_by('numero') if annee else []

    resultats = []
    salle_selectionnee = None
    periode_selectionnee = None
    stats = None

    if salle_pk and periode_pk:
        try:
            salle_selectionnee = SalleClasse.objects.get(pk=salle_pk)
            periode_selectionnee = Periode.objects.get(pk=periode_pk)

            inscrits = Inscription.objects.filter(
                salle=salle_selectionnee,
                annee=annee,
                statut='ACTIVE',
            ).select_related('eleve').order_by('eleve__nom')

            for i, insc in enumerate(inscrits):
                eleve = insc.eleve
                moy_gen = MoyenneGenerale.objects.filter(
                    eleve=eleve,
                    periode=periode_selectionnee,
                ).first()

                if not moy_gen:
                    moy_gen = _calculer_moyenne_generale(
                        eleve, salle_selectionnee,
                        periode_selectionnee
                    )

                moy_val = float(moy_gen.moyenne) if moy_gen else 0

                mention = (
                    'Très Bien' if moy_val >= 16 else
                    'Bien' if moy_val >= 14 else
                    'Assez Bien' if moy_val >= 12 else
                    'Passable' if moy_val >= 10 else
                    'Insuffisant' if moy_val >= 8 else
                    'Très Insuffisant'
                )

                decision = 'ADMIS' if moy_val >= 10 else 'ECHOUE'

                resultats.append({
                    'eleve': eleve,
                    'moyenne': moy_val,
                    'mention': mention,
                    'decision': decision,
                })

            # Trier par moyenne décroissante
            resultats.sort(key=lambda x: x['moyenne'], reverse=True)

            # Ajouter rang
            for i, r in enumerate(resultats, 1):
                r['rang'] = i

            # Stats
            moyennes = [r['moyenne'] for r in resultats]
            nb_admis = sum(1 for r in resultats if r['decision'] == 'ADMIS')
            stats = {
                'nb_total': len(resultats),
                'nb_admis': nb_admis,
                'nb_echec': len(resultats) - nb_admis,
                'taux_reussite': round(
                    nb_admis / len(resultats) * 100, 1
                ) if resultats else 0,
                'moy_classe': round(
                    sum(moyennes) / len(moyennes), 2
                ) if moyennes else 0,
                'moy_max': max(moyennes) if moyennes else 0,
                'moy_min': min(moyennes) if moyennes else 0,
                'premier': resultats[0] if resultats else None,
                'dernier': resultats[-1] if resultats else None,
            }

        except Exception as e:
            messages.error(request, f"Erreur : {e}")

    return render(request, 'grades/proclamation.html', {
        'salles': salles,
        'periodes': periodes,
        'salle_selectionnee': salle_selectionnee,
        'periode_selectionnee': periode_selectionnee,
        'resultats': resultats,
        'stats': stats,
        'salle_pk': salle_pk,
        'periode_pk': periode_pk,
    })


@login_required
@role_requis('DIRECTEUR', 'CENSEUR', 'SECRETAIRE')
def proclamation_pdf(request, salle_pk, periode_pk):
    from apps.core.models import ConfigurationEcole
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.lib.enums import TA_CENTER
    import io

    salle = get_object_or_404(SalleClasse, pk=salle_pk)
    periode = get_object_or_404(Periode, pk=periode_pk)
    annee = AnneeScolaire.active()
    config = ConfigurationEcole.get()

    inscrits = Inscription.objects.filter(
        salle=salle, annee=annee, statut='ACTIVE'
    ).select_related('eleve').order_by('eleve__nom')

    resultats = []
    for insc in inscrits:
        eleve = insc.eleve
        moy_gen = MoyenneGenerale.objects.filter(
            eleve=eleve, periode=periode
        ).first()
        if not moy_gen:
            moy_gen = _calculer_moyenne_generale(
                eleve, salle, periode
            )
        moy_val = float(moy_gen.moyenne) if moy_gen else 0
        resultats.append({
            'eleve': eleve,
            'moyenne': moy_val,
            'mention': (
                'Très Bien' if moy_val >= 16 else
                'Bien' if moy_val >= 14 else
                'Assez Bien' if moy_val >= 12 else
                'Passable' if moy_val >= 10 else
                'Insuffisant'
            ),
            'decision': 'ADMIS' if moy_val >= 10 else 'ÉCHOUÉ',
        })

    resultats.sort(key=lambda x: x['moyenne'], reverse=True)

    BLEU = colors.HexColor('#1E3A8A')
    VERT = colors.HexColor('#16A34A')
    ROUGE = colors.HexColor('#DC2626')
    GRIS = colors.HexColor('#F8FAFC')

    buffer = io.BytesIO()
    styles = getSampleStyleSheet()

    def s(name, **kw):
        return ParagraphStyle(name, parent=styles['Normal'], **kw)

    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
    )

    elements = []

    # En-tête
    elements.append(Paragraph(
        f"<b>{config.nom}</b>",
        s('t', fontSize=14, textColor=BLEU, alignment=TA_CENTER,
          fontName='Helvetica-Bold')
    ))
    elements.append(Paragraph(
        f"LISTE DE PROCLAMATION — {salle.nom} — {periode} — {annee.nom}",
        s('st', fontSize=11, fontName='Helvetica-Bold',
          alignment=TA_CENTER, spaceAfter=8)
    ))
    elements.append(Spacer(1, 0.3*cm))

    # Tableau résultats
    header = ['Rang', 'Matricule', 'Nom et Prénoms', 'Moyenne', 'Mention', 'Décision']
    data = [header]

    for i, r in enumerate(resultats, 1):
        data.append([
            str(i),
            r['eleve'].matricule,
            r['eleve'].nom_complet,
            f"{r['moyenne']:.2f}",
            r['mention'],
            r['decision'],
        ])

    nb_admis = sum(1 for r in resultats if r['decision'] == 'ADMIS')

    table = Table(
        data,
        colWidths=[1.5*cm, 3*cm, 6*cm, 2.5*cm, 3*cm, 2.5*cm],
        repeatRows=1
    )
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), BLEU),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('ALIGN', (0,0), (0,-1), 'CENTER'),
        ('ALIGN', (3,0), (3,-1), 'CENTER'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [
            colors.white, GRIS
        ]),
    ]))

    # Colorier décisions
    for i, r in enumerate(resultats, 1):
        if r['decision'] == 'ADMIS':
            table.setStyle(TableStyle([
                ('TEXTCOLOR', (5,i), (5,i), VERT),
                ('FONTNAME', (5,i), (5,i), 'Helvetica-Bold'),
            ]))
        else:
            table.setStyle(TableStyle([
                ('TEXTCOLOR', (5,i), (5,i), ROUGE),
                ('FONTNAME', (5,i), (5,i), 'Helvetica-Bold'),
            ]))

    elements.append(table)
    elements.append(Spacer(1, 0.4*cm))

    # Résumé
    taux = round(nb_admis / len(resultats) * 100, 1) if resultats else 0
    elements.append(Paragraph(
        f"Total : {len(resultats)} élève(s) — "
        f"Admis : {nb_admis} — "
        f"Échoués : {len(resultats) - nb_admis} — "
        f"Taux de réussite : {taux}%",
        s('r', fontSize=10, fontName='Helvetica-Bold',
          textColor=BLEU, alignment=TA_CENTER)
    ))

    from django.utils import timezone
    elements.append(Spacer(1, 0.5*cm))
    elements.append(Paragraph(
        f"Fait à Lomé, le {timezone.now().strftime('%d/%m/%Y')}",
        s('d', fontSize=9, alignment=TA_CENTER)
    ))

    doc.build(elements)
    buffer.seek(0)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="proclamation_{salle.nom}_{periode}.pdf"'
    )
    response.write(buffer.getvalue())
    return response
