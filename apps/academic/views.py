from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import (
    SalleClasse, Niveau, AnneeScolaire, Matiere,
    MatiereSalle, GroupeMatiere
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


# ── SALLES ────────────────────────────────────────────────────────────────────

@login_required
@role_requis('DIRECTEUR', 'CENSEUR', 'SECRETAIRE')
def liste_salles(request):
    annee = AnneeScolaire.active()
    niveaux = Niveau.objects.all().order_by('ordre', 'nom')
    niveau_filtre = request.GET.get('niveau', '')

    salles = SalleClasse.objects.filter(
        annee=annee
    ).select_related('niveau', 'titulaire') if annee else []

    if niveau_filtre:
        salles = salles.filter(niveau__pk=niveau_filtre)

    return render(request, 'academic/liste_salles.html', {
        'salles': salles,
        'niveaux': niveaux,
        'annee': annee,
        'niveau_filtre': niveau_filtre,
    })


@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def nouvelle_salle(request):
    annee = AnneeScolaire.active()
    if not annee:
        messages.error(request, "Activez d'abord une annee scolaire.")
        return redirect('liste_salles')

    niveaux = Niveau.objects.all().order_by('ordre', 'nom')
    professeurs = CustomUser.objects.filter(
        role='PROFESSEUR', is_active=True
    ).order_by('last_name')

    if request.method == 'POST':
        niveau_pk = request.POST.get('niveau_id')
        nom = request.POST.get('nom', '').strip()
        capacite = int(request.POST.get('capacite', 40))
        titulaire_pk = request.POST.get('titulaire_id') or None
        batiment = request.POST.get('batiment', '').strip()

        if not all([niveau_pk, nom]):
            messages.error(request, "Le niveau et le nom sont obligatoires.")
            return render(request, 'academic/nouvelle_salle.html', {
                'niveaux': niveaux,
                'professeurs': professeurs,
                'annee': annee,
            })

        if SalleClasse.objects.filter(
            niveau_id=niveau_pk, annee=annee, nom=nom
        ).exists():
            messages.error(request, f"La salle {nom} existe deja pour ce niveau.")
            return render(request, 'academic/nouvelle_salle.html', {
                'niveaux': niveaux,
                'professeurs': professeurs,
                'annee': annee,
            })

        SalleClasse.objects.create(
            niveau_id=niveau_pk,
            annee=annee,
            nom=nom,
            capacite=capacite,
            titulaire_id=titulaire_pk,
            batiment=batiment,
        )
        messages.success(request, f"Salle {nom} creee.")
        return redirect('liste_salles')

    return render(request, 'academic/nouvelle_salle.html', {
        'niveaux': niveaux,
        'professeurs': professeurs,
        'annee': annee,
    })


@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def modifier_salle(request, pk):
    salle = get_object_or_404(SalleClasse, pk=pk)
    niveaux = Niveau.objects.all().order_by('ordre', 'nom')
    professeurs = CustomUser.objects.filter(
        role='PROFESSEUR', is_active=True
    ).order_by('last_name')

    if request.method == 'POST':
        salle.nom = request.POST.get('nom', '').strip()
        salle.capacite = int(request.POST.get('capacite', 40))
        salle.titulaire_id = request.POST.get('titulaire_id') or None
        salle.batiment = request.POST.get('batiment', '').strip()
        salle.est_active = request.POST.get('est_active') == '1'
        salle.save()
        messages.success(request, f"Salle {salle.nom} mise a jour.")
        return redirect('detail_salle', pk=pk)

    return render(request, 'academic/modifier_salle.html', {
        'salle': salle,
        'niveaux': niveaux,
        'professeurs': professeurs,
    })


@login_required
@role_requis('DIRECTEUR', 'CENSEUR', 'SECRETAIRE', 'PROFESSEUR')
def detail_salle(request, pk):
    salle = get_object_or_404(SalleClasse, pk=pk)
    matieres_salle = MatiereSalle.objects.filter(
        salle=salle
    ).select_related('matiere', 'professeur', 'groupe').order_by(
        'groupe__ordre', '-coefficient'
    )
    professeurs = CustomUser.objects.filter(
        role='PROFESSEUR', is_active=True
    ).order_by('last_name')
    matieres_dispo = Matiere.objects.exclude(
        pk__in=matieres_salle.values_list('matiere__pk', flat=True)
    ).order_by('nom')
    groupes = GroupeMatiere.objects.filter(
        niveau=salle.niveau
    ).order_by('ordre')

    return render(request, 'academic/detail_salle.html', {
        'salle': salle,
        'matieres_salle': matieres_salle,
        'professeurs': professeurs,
        'matieres_dispo': matieres_dispo,
        'groupes': groupes,
        'effectif': salle.effectif,
    })


@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def supprimer_salle(request, pk):
    if request.method == 'POST':
        salle = get_object_or_404(SalleClasse, pk=pk)
        if salle.inscriptions.filter(statut='ACTIVE').exists():
            messages.error(
                request,
                "Impossible — des eleves sont inscrits dans cette salle."
            )
            return redirect('detail_salle', pk=pk)
        nom = salle.nom
        salle.delete()
        messages.success(request, f"Salle {nom} supprimee.")
    return redirect('liste_salles')


# ── MATIERES ──────────────────────────────────────────────────────────────────

@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def liste_matieres(request):
    matieres = Matiere.objects.all().order_by('nom')
    return render(request, 'academic/liste_matieres.html', {
        'matieres': matieres,
    })


@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def nouvelle_matiere(request):
    if request.method == 'POST':
        nom = request.POST.get('nom', '').strip()
        code = request.POST.get('code', '').strip()
        if not nom:
            messages.error(request, "Le nom est obligatoire.")
            return redirect('liste_matieres')
        if Matiere.objects.filter(nom__iexact=nom).exists():
            messages.error(request, f"La matiere {nom} existe deja.")
            return redirect('liste_matieres')
        Matiere.objects.create(nom=nom, code=code)
        messages.success(request, f"Matiere {nom} creee.")
    return redirect('liste_matieres')


@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def supprimer_matiere(request, pk):
    if request.method == 'POST':
        matiere = get_object_or_404(Matiere, pk=pk)
        if matiere.matieres_salle.exists():
            messages.error(
                request,
                "Impossible — cette matiere est assignee a des salles."
            )
            return redirect('liste_matieres')
        nom = matiere.nom
        matiere.delete()
        messages.success(request, f"Matiere {nom} supprimee.")
    return redirect('liste_matieres')


# ── MATIERES PAR SALLE ────────────────────────────────────────────────────────

@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def ajouter_matiere_salle(request, salle_pk):
    salle = get_object_or_404(SalleClasse, pk=salle_pk)
    if request.method == 'POST':
        matiere_pk = request.POST.get('matiere_id')
        professeur_pk = request.POST.get('professeur_id') or None
        groupe_pk = request.POST.get('groupe_id') or None
        coefficient = request.POST.get('coefficient', '1')
        heures_semaine = request.POST.get('heures_semaine', '2')
        est_facultative = request.POST.get('est_facultative') == '1'

        if not matiere_pk:
            messages.error(request, "Choisissez une matiere.")
            return redirect('detail_salle', pk=salle_pk)

        if MatiereSalle.objects.filter(
            salle=salle, matiere_id=matiere_pk
        ).exists():
            messages.error(request, "Cette matiere est deja assignee a cette salle.")
            return redirect('detail_salle', pk=salle_pk)

        try:
            MatiereSalle.objects.create(
                salle=salle,
                matiere_id=matiere_pk,
                professeur_id=professeur_pk,
                groupe_id=groupe_pk,
                coefficient=float(coefficient),
                heures_semaine=float(heures_semaine),
                est_facultative=est_facultative,
            )
            messages.success(request, "Matiere ajoutee a la salle.")
        except Exception as e:
            messages.error(request, f"Erreur : {e}")

    return redirect('detail_salle', pk=salle_pk)


@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def modifier_matiere_salle(request, pk):
    ms = get_object_or_404(MatiereSalle, pk=pk)
    if request.method == 'POST':
        ms.professeur_id = request.POST.get('professeur_id') or None
        ms.groupe_id = request.POST.get('groupe_id') or None
        ms.coefficient = float(request.POST.get('coefficient', 1))
        ms.heures_semaine = float(request.POST.get('heures_semaine', 2))
        ms.est_facultative = request.POST.get('est_facultative') == '1'
        ms.save()
        messages.success(request, "Matiere mise a jour.")
    return redirect('detail_salle', pk=ms.salle.pk)


@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def supprimer_matiere_salle(request, pk):
    if request.method == 'POST':
        ms = get_object_or_404(MatiereSalle, pk=pk)
        salle_pk = ms.salle.pk
        if ms.evaluations.exists():
            messages.error(
                request,
                "Impossible — des evaluations existent pour cette matiere."
            )
            return redirect('detail_salle', pk=salle_pk)
        ms.delete()
        messages.success(request, "Matiere retiree de la salle.")
        return redirect('detail_salle', pk=salle_pk)
    return redirect('liste_salles')
