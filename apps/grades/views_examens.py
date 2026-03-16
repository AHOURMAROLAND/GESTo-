from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from .models import Examen, ExamenMatiere, NoteExamen
from apps.academic.models import (
    AnneeScolaire, Periode, Niveau, SalleClasse, Matiere
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
    'PREPARATION': 'badge-gray',
    'EN_COURS': 'badge-warning',
    'NOTES_EN_SAISIE': 'badge-info',
    'NOTES_SAISIES': 'badge-primary',
    'VALIDE': 'badge-success',
}


@login_required
@role_requis('DIRECTEUR', 'CENSEUR', 'PROFESSEUR', 'SECRETAIRE')
def liste_examens(request):
    annee = AnneeScolaire.active()
    periode_f = request.GET.get('periode', '')
    statut_f = request.GET.get('statut', '')

    examens = Examen.objects.select_related(
        'niveau', 'salle', 'periode', 'creee_par'
    ).filter(
        periode__annee=annee
    ).order_by('-created_at') if annee else []

    if statut_f and hasattr(examens, 'filter'):
        examens = examens.filter(statut=statut_f)
    if periode_f and hasattr(examens, 'filter'):
        examens = examens.filter(periode__pk=periode_f)

    periodes = Periode.objects.filter(
        annee=annee
    ).order_by('numero') if annee else []

    return render(request, 'grades/examens/liste_examens.html', {
        'examens': examens,
        'periodes': periodes,
        'statuts': Examen.STATUTS,
        'statut_colors': STATUT_COLORS,
        'annee': annee,
        'statut_filtre': statut_f,
        'periode_filtre': periode_f,
    })


@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def nouvel_examen(request):
    annee = AnneeScolaire.active()
    if not annee:
        messages.error(request, "Aucune annee active.")
        return redirect('liste_examens')

    niveaux = Niveau.objects.all().order_by('ordre', 'nom')
    salles = SalleClasse.objects.filter(
        annee=annee, est_active=True
    ).order_by('niveau__ordre', 'nom')
    periodes = Periode.objects.filter(annee=annee).order_by('numero')
    matieres = Matiere.objects.all().order_by('nom')

    if request.method == 'POST':
        titre = request.POST.get('titre', '').strip()
        type_exam = request.POST.get('type', 'BLANC')
        cible = request.POST.get('cible', 'NIVEAU')
        niveau_pk = request.POST.get('niveau_id') or None
        salle_pk = request.POST.get('salle_id') or None
        periode_pk = request.POST.get('periode_id')
        date_debut = request.POST.get('date_debut')
        date_fin = request.POST.get('date_fin') or None
        matieres_pks = request.POST.getlist('matieres')
        coefficients = request.POST.getlist('coefficients')
        notes_sur = request.POST.getlist('notes_sur')

        if not all([titre, periode_pk, date_debut]):
            messages.error(request, "Titre, periode et date sont obligatoires.")
            return render(request, 'grades/examens/nouvel_examen.html', {
                'niveaux': niveaux, 'salles': salles,
                'periodes': periodes, 'matieres': matieres,
                'types': Examen.TYPES, 'cibles': Examen.CIBLES,
                'annee': annee,
            })

        examen = Examen.objects.create(
            titre=titre,
            type=type_exam,
            cible=cible,
            niveau_id=niveau_pk,
            salle_id=salle_pk,
            periode_id=periode_pk,
            date_debut=date_debut,
            date_fin=date_fin,
            statut='PREPARATION',
            creee_par=request.user,
        )

        for i, mat_pk in enumerate(matieres_pks):
            coeff = coefficients[i] if i < len(coefficients) else '1'
            note_sur = notes_sur[i] if i < len(notes_sur) else '20'
            try:
                ExamenMatiere.objects.create(
                    examen=examen,
                    matiere_id=mat_pk,
                    coefficient=float(coeff),
                    note_sur=float(note_sur),
                )
            except Exception:
                pass

        messages.success(request, f"Examen '{titre}' cree.")
        return redirect('detail_examen', pk=examen.pk)

    return render(request, 'grades/examens/nouvel_examen.html', {
        'niveaux': niveaux,
        'salles': salles,
        'periodes': periodes,
        'matieres': matieres,
        'types': Examen.TYPES,
        'cibles': Examen.CIBLES,
        'annee': annee,
    })


@login_required
def detail_examen(request, pk):
    examen = get_object_or_404(Examen, pk=pk)
    matieres_exam = ExamenMatiere.objects.filter(
        examen=examen
    ).select_related('matiere', 'saisie_par')

    salles = list(examen.salles_concernees)
    professeurs = CustomUser.objects.filter(
        role='PROFESSEUR', is_active=True
    )

    return render(request, 'grades/examens/detail_examen.html', {
        'examen': examen,
        'matieres_exam': matieres_exam,
        'salles': salles,
        'professeurs': professeurs,
        'statut_color': STATUT_COLORS.get(examen.statut, 'badge-gray'),
    })


@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def demarrer_examen(request, pk):
    if request.method == 'POST':
        examen = get_object_or_404(Examen, pk=pk)
        examen.statut = 'EN_COURS'
        examen.save()
        messages.success(request, f"Examen '{examen.titre}' demarre.")
    return redirect('detail_examen', pk=pk)


@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def assigner_saisie_examen(request, pk):
    if request.method == 'POST':
        examen = get_object_or_404(Examen, pk=pk)
        for em in ExamenMatiere.objects.filter(examen=examen):
            saisisseur_pk = request.POST.get(f'saisisseur_{em.pk}') or None
            em.saisie_par_id = saisisseur_pk
            em.save()
        examen.statut = 'NOTES_EN_SAISIE'
        examen.save()
        messages.success(request, "Saisisseurs assignes.")
    return redirect('detail_examen', pk=pk)


@login_required
def saisir_notes_examen(request, examen_pk, matiere_pk):
    examen = get_object_or_404(Examen, pk=examen_pk)
    examen_matiere = get_object_or_404(
        ExamenMatiere, pk=matiere_pk, examen=examen
    )
    user = request.user

    if (examen_matiere.saisie_par and
            examen_matiere.saisie_par != user and
            not user.has_role('DIRECTEUR', 'CENSEUR')):
        messages.error(request, "Vous n'etes pas le saisisseur assigne.")
        return redirect('detail_examen', pk=examen_pk)

    salles = list(examen.salles_concernees)

    notes_existantes = {
        (n.examen_matiere_id, n.eleve_id): n
        for n in NoteExamen.objects.filter(examen_matiere=examen_matiere)
    }

    inscrits_par_salle = []
    for salle in salles:
        inscrits = salle.inscriptions.filter(
            statut='ACTIVE'
        ).select_related('eleve').order_by('eleve__nom')
        inscrits_par_salle.append({
            'salle': salle,
            'inscrits': inscrits,
        })

    if request.method == 'POST':
        nb = 0
        for salle_data in inscrits_par_salle:
            for insc in salle_data['inscrits']:
                eleve = insc.eleve
                valeur_str = request.POST.get(
                    f'note_{eleve.pk}', ''
                ).strip()
                absent = request.POST.get(f'absent_{eleve.pk}') == '1'

                note, _ = NoteExamen.objects.get_or_create(
                    examen_matiere=examen_matiere,
                    eleve=eleve,
                    defaults={'saisie_par': user}
                )

                if absent:
                    note.est_absent = True
                    note.valeur = None
                elif valeur_str:
                    try:
                        val = float(valeur_str.replace(',', '.'))
                        if 0 <= val <= float(examen_matiere.note_sur):
                            note.valeur = val
                            note.est_absent = False
                            nb += 1
                    except ValueError:
                        pass

                note.saisie_par = user
                note.save()

        examen_matiere.notes_saisies = True
        examen_matiere.save()

        # Verifier si toutes les matieres sont saisies
        total = ExamenMatiere.objects.filter(examen=examen).count()
        saisies = ExamenMatiere.objects.filter(
            examen=examen, notes_saisies=True
        ).count()
        if total == saisies:
            examen.statut = 'NOTES_SAISIES'
            examen.save()

        messages.success(request, f"{nb} note(s) saisie(s).")
        return redirect('detail_examen', pk=examen_pk)

    return render(request, 'grades/examens/saisir_notes_examen.html', {
        'examen': examen,
        'examen_matiere': examen_matiere,
        'inscrits_par_salle': inscrits_par_salle,
        'notes': notes_existantes,
    })


@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def valider_examen(request, pk):
    if request.method == 'POST':
        examen = get_object_or_404(Examen, pk=pk)
        action = request.POST.get('action')
        if action == 'valider':
            NoteExamen.objects.filter(
                examen_matiere__examen=examen
            ).update(est_absent=False)
            examen.statut = 'VALIDE'
            examen.valide_par = request.user
            examen.save()
            messages.success(
                request, f"Examen '{examen.titre}' valide."
            )
        elif action == 'renvoyer':
            examen.statut = 'NOTES_EN_SAISIE'
            ExamenMatiere.objects.filter(
                examen=examen
            ).update(notes_saisies=False)
            examen.save()
            messages.warning(request, "Examen renvoye en saisie.")
    return redirect('detail_examen', pk=pk)


@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def supprimer_examen(request, pk):
    if request.method == 'POST':
        examen = get_object_or_404(Examen, pk=pk)
        if examen.statut != 'PREPARATION':
            messages.error(
                request,
                "Impossible de supprimer un examen en cours ou valide."
            )
            return redirect('detail_examen', pk=pk)
        titre = examen.titre
        examen.delete()
        messages.success(request, f"Examen '{titre}' supprime.")
    return redirect('liste_examens')
