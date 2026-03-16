from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import (
    AnneeScolaire, Niveau, SalleClasse, NiveauHoraire,
    CreneauType, EmploiDuTemps, MatiereSalle, DisponibiliteProf
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


JOURS = ['LUNDI', 'MARDI', 'MERCREDI', 'JEUDI', 'VENDREDI', 'SAMEDI']
JOURS_LABELS = {
    'LUNDI': 'Lundi', 'MARDI': 'Mardi', 'MERCREDI': 'Mercredi',
    'JEUDI': 'Jeudi', 'VENDREDI': 'Vendredi', 'SAMEDI': 'Samedi',
}


# ── GRILLES HORAIRES ──────────────────────────────────────────────────────────

@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def liste_grilles(request):
    annee = AnneeScolaire.active()
    niveaux = Niveau.objects.all().order_by('ordre', 'nom')
    grilles = NiveauHoraire.objects.filter(
        annee=annee
    ).select_related('niveau') if annee else []
    return render(request, 'academic/edt/liste_grilles.html', {
        'grilles': grilles,
        'niveaux': niveaux,
        'annee': annee,
    })


@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def creer_grille(request):
    annee = AnneeScolaire.active()
    if not annee:
        messages.error(request, "Activez d'abord une annee scolaire.")
        return redirect('liste_grilles')
    niveaux = Niveau.objects.all().order_by('ordre', 'nom')
    if request.method == 'POST':
        niveau_pk = request.POST.get('niveau_id')
        if not niveau_pk:
            messages.error(request, "Choisissez un niveau.")
            return redirect('creer_grille')
        grille, created = NiveauHoraire.objects.get_or_create(
            niveau_id=niveau_pk, annee=annee)
        if created:
            messages.success(request, "Grille creee.")
        else:
            messages.info(request, "Cette grille existe deja.")
        return redirect('detail_grille', pk=grille.pk)
    return render(request, 'academic/edt/creer_grille.html', {
        'niveaux': niveaux, 'annee': annee,
    })


@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def detail_grille(request, pk):
    grille = get_object_or_404(NiveauHoraire, pk=pk)
    creneaux = CreneauType.objects.filter(
        niveau_horaire=grille).order_by('numero')
    return render(request, 'academic/edt/detail_grille.html', {
        'grille': grille,
        'creneaux': creneaux,
    })


@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def ajouter_creneau(request, grille_pk):
    grille = get_object_or_404(NiveauHoraire, pk=grille_pk)
    if request.method == 'POST':
        numero = request.POST.get('numero')
        type_c = request.POST.get('type', 'COURS')
        heure_debut = request.POST.get('heure_debut')
        heure_fin = request.POST.get('heure_fin')
        jours = request.POST.getlist('jours')

        if not all([numero, heure_debut, heure_fin]):
            messages.error(request, "Tous les champs sont obligatoires.")
            return redirect('detail_grille', pk=grille_pk)

        if CreneauType.objects.filter(
            niveau_horaire=grille, numero=numero
        ).exists():
            messages.error(request, f"Le creneau H{numero} existe deja.")
            return redirect('detail_grille', pk=grille_pk)

        jours_str = ','.join(jours) if jours else 'LUNDI,MARDI,MERCREDI,JEUDI,VENDREDI'
        CreneauType.objects.create(
            niveau_horaire=grille,
            numero=int(numero),
            type=type_c,
            heure_debut=heure_debut,
            heure_fin=heure_fin,
            jours_applicables=jours_str,
        )
        messages.success(request, f"Creneau H{numero} ajoute.")
    return redirect('detail_grille', pk=grille_pk)


@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def supprimer_creneau(request, pk):
    if request.method == 'POST':
        creneau = get_object_or_404(CreneauType, pk=pk)
        grille_pk = creneau.niveau_horaire.pk
        creneau.delete()
        messages.success(request, "Creneau supprime.")
        return redirect('detail_grille', pk=grille_pk)
    return redirect('liste_grilles')


# ── EMPLOI DU TEMPS ───────────────────────────────────────────────────────────

@login_required
def edt_salle(request, salle_pk):
    salle = get_object_or_404(SalleClasse, pk=salle_pk)
    annee = AnneeScolaire.active()

    try:
        grille = NiveauHoraire.objects.get(niveau=salle.niveau, annee=annee)
        creneaux = CreneauType.objects.filter(
            niveau_horaire=grille
        ).order_by('numero')
    except NiveauHoraire.DoesNotExist:
        grille = None
        creneaux = []

    edt_data = {}
    if grille:
        for jour in JOURS:
            edt_data[jour] = {}
            for creneau in creneaux:
                try:
                    slot = EmploiDuTemps.objects.get(
                        salle=salle, creneau_type=creneau,
                        jour=jour, annee=annee
                    )
                    edt_data[jour][creneau.numero] = slot
                except EmploiDuTemps.DoesNotExist:
                    edt_data[jour][creneau.numero] = None

    matieres_salle = MatiereSalle.objects.filter(
        salle=salle
    ).select_related('matiere', 'professeur')

    est_publie = EmploiDuTemps.objects.filter(
        salle=salle, annee=annee, statut='VALIDE'
    ).exists()

    return render(request, 'academic/edt/edt_salle.html', {
        'salle': salle,
        'grille': grille,
        'creneaux': creneaux,
        'edt_data': edt_data,
        'jours': JOURS,
        'jours_labels': JOURS_LABELS,
        'matieres_salle': matieres_salle,
        'est_publie': est_publie,
        'annee': annee,
    })


@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def modifier_slot_edt(request, salle_pk):
    if request.method != 'POST':
        return redirect('liste_salles')

    salle = get_object_or_404(SalleClasse, pk=salle_pk)
    annee = AnneeScolaire.active()
    creneau_pk = request.POST.get('creneau_id')
    jour = request.POST.get('jour')
    matiere_salle_pk = request.POST.get('matiere_salle_id') or None
    est_libre = request.POST.get('est_libre') == '1'

    creneau = get_object_or_404(CreneauType, pk=creneau_pk)

    slot, created = EmploiDuTemps.objects.get_or_create(
        salle=salle, creneau_type=creneau, jour=jour, annee=annee,
        defaults={'statut': 'BROUILLON'}
    )

    slot.matiere_salle_id = matiere_salle_pk
    slot.est_libre = est_libre
    slot.statut = 'BROUILLON'
    slot.save()

    messages.success(request, "Creneau mis a jour.")
    return redirect('edt_salle', salle_pk=salle_pk)


@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def publier_edt(request, salle_pk):
    if request.method == 'POST':
        salle = get_object_or_404(SalleClasse, pk=salle_pk)
        annee = AnneeScolaire.active()
        nb = EmploiDuTemps.objects.filter(
            salle=salle, annee=annee
        ).update(statut='VALIDE')
        messages.success(
            request,
            f"EDT de {salle.nom} publie ({nb} creneaux). "
            f"Les parents et eleves seront notifies."
        )
    return redirect('edt_salle', salle_pk=salle_pk)


@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def reinitialiser_edt(request, salle_pk):
    if request.method == 'POST':
        salle = get_object_or_404(SalleClasse, pk=salle_pk)
        annee = AnneeScolaire.active()
        EmploiDuTemps.objects.filter(salle=salle, annee=annee).delete()
        messages.success(request, f"EDT de {salle.nom} reinitialise.")
    return redirect('edt_salle', salle_pk=salle_pk)


@login_required
def edt_professeur(request, prof_pk=None):
    annee = AnneeScolaire.active()
    if prof_pk:
        prof = get_object_or_404(CustomUser, pk=prof_pk, role='PROFESSEUR')
    else:
        prof = request.user

    slots = EmploiDuTemps.objects.filter(
        annee=annee,
        matiere_salle__professeur=prof,
    ).select_related(
        'salle', 'creneau_type', 'matiere_salle__matiere'
    ).order_by('jour', 'creneau_type__numero')

    edt_data = {}
    for jour in JOURS:
        edt_data[jour] = {}

    for slot in slots:
        jour = slot.jour
        num = slot.creneau_type.numero
        if jour not in edt_data:
            edt_data[jour] = {}
        if num not in edt_data[jour]:
            edt_data[jour][num] = []
        edt_data[jour][num].append(slot)

    creneaux_nums = sorted(set(
        s.creneau_type.numero for s in slots
    )) if slots else []

    professeurs = CustomUser.objects.filter(
        role='PROFESSEUR', is_active=True
    ).order_by('last_name')

    return render(request, 'academic/edt/edt_professeur.html', {
        'prof': prof,
        'edt_data': edt_data,
        'jours': JOURS,
        'jours_labels': JOURS_LABELS,
        'creneaux_nums': creneaux_nums,
        'professeurs': professeurs,
        'annee': annee,
    })


@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def disponibilites_prof(request, prof_pk):
    prof = get_object_or_404(CustomUser, pk=prof_pk, role='PROFESSEUR')
    annee = AnneeScolaire.active()
    dispos = DisponibiliteProf.objects.filter(
        professeur=prof, annee=annee
    ).order_by('jour', 'heure_debut') if annee else []

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'ajouter' and annee:
            jour = request.POST.get('jour')
            heure_debut = request.POST.get('heure_debut')
            heure_fin = request.POST.get('heure_fin')
            if all([jour, heure_debut, heure_fin]):
                DisponibiliteProf.objects.create(
                    professeur=prof, annee=annee,
                    jour=jour, heure_debut=heure_debut, heure_fin=heure_fin,
                )
                messages.success(request, "Disponibilite ajoutee.")
        elif action == 'supprimer':
            dispo_pk = request.POST.get('dispo_id')
            DisponibiliteProf.objects.filter(
                pk=dispo_pk, professeur=prof).delete()
            messages.success(request, "Disponibilite supprimee.")
        return redirect('disponibilites_prof', prof_pk=prof_pk)

    return render(request, 'academic/edt/disponibilites.html', {
        'prof': prof,
        'dispos': dispos,
        'jours': JOURS,
        'jours_labels': JOURS_LABELS,
        'annee': annee,
    })
