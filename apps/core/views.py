from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import ConfigurationEcole, SauvegardeAuto


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


@login_required
def dashboard(request):
    from apps.academic.models import AnneeScolaire, Niveau, SalleClasse
    from apps.students.models import Eleve, Inscription
    from apps.authentication.models import CustomUser

    annee = AnneeScolaire.active()
    context = {
        'annee_active': annee,
        'nb_eleves': 0,
        'nb_salles': 0,
        'nb_personnel': 0,
    }

    if annee:
        context['nb_salles'] = SalleClasse.objects.filter(
            annee=annee, est_active=True).count()
        context['nb_eleves'] = Inscription.objects.filter(
            annee=annee, statut='ACTIVE').count()

    context['nb_personnel'] = CustomUser.objects.filter(
        is_active=True
    ).exclude(role__in=['PARENT', 'ELEVE']).count()

    # Apres le calcul nb_personnel
    from apps.communication.models import Notification, ReunionParent, EvenementCalendrier
    from django.utils import timezone

    today = timezone.now().date()

    # Prochains evenements
    prochains_evenements = EvenementCalendrier.objects.filter(
        annee=annee,
        date_debut__gte=today,
    ).order_by('date_debut')[:3] if annee else []

    # Prochaine reunion
    prochaine_reunion = ReunionParent.objects.filter(
        annee=annee,
        date__gte=today,
        statut='PLANIFIEE',
    ).order_by('date').first() if annee else None

    context['prochains_evenements'] = prochains_evenements
    context['prochaine_reunion'] = prochaine_reunion
    context['today'] = today

    role = request.user.role
    template = f'dashboards/{role.lower()}.html'

    try:
        return render(request, template, context)
    except Exception:
        return render(request, 'dashboards/default.html', context)


@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def parametres(request):
    config = ConfigurationEcole.get()
    return render(request, 'core/parametres.html', {'config': config})


@login_required
@role_requis('DIRECTEUR')
def modifier_config_ecole(request):
    config = ConfigurationEcole.get()
    if request.method == 'POST':
        config.nom = request.POST.get('nom', '').strip()
        config.slogan = request.POST.get('slogan', '').strip()
        config.adresse = request.POST.get('adresse', '').strip()
        config.telephone = request.POST.get('telephone', '').strip()
        config.email = request.POST.get('email', '').strip()
        config.type_ecole = request.POST.get('type_ecole', 'PRIVE')
        config.systeme_defaut = request.POST.get('systeme_defaut', 'TRIMESTRIEL')
        config.region = request.POST.get('region', '').strip()
        config.ministre_tutelle = request.POST.get('ministre_tutelle', '').strip()
        config.devise = request.POST.get('devise', '').strip()
        config.wa_numero_source = request.POST.get('wa_numero_source', '').strip()
        config.heure_rapport_directeur = request.POST.get(
            'heure_rapport_directeur', '09:00')
        config.heure_rapport_censeur = request.POST.get(
            'heure_rapport_censeur', '18:00')
        config.seuil_retards_consecutifs = int(
            request.POST.get('seuil_retards_consecutifs', 5))
        config.seuil_alerte_dette_jours = int(
            request.POST.get('seuil_alerte_dette_jours', 30))
        if request.FILES.get('logo'):
            config.logo = request.FILES['logo']
        config.save()
        messages.success(request, "Configuration enregistree.")
        return redirect('parametres')
    return render(request, 'core/modifier_config_ecole.html', {'config': config})


# ── ANNEES SCOLAIRES ──────────────────────────────────────────────────────────

@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def liste_annees(request):
    from apps.academic.models import AnneeScolaire
    annees = AnneeScolaire.objects.all().order_by('-nom')
    return render(request, 'core/annees.html', {'annees': annees})


@login_required
@role_requis('DIRECTEUR')
def nouvelle_annee(request):
    from apps.academic.models import AnneeScolaire
    if request.method == 'POST':
        nom = request.POST.get('nom', '').strip()
        date_debut = request.POST.get('date_debut') or None
        date_fin = request.POST.get('date_fin') or None
        if not nom:
            messages.error(request, "Le nom est obligatoire.")
            return redirect('liste_annees')
        if AnneeScolaire.objects.filter(nom=nom).exists():
            messages.error(request, f"L'annee {nom} existe deja.")
            return redirect('liste_annees')
        AnneeScolaire.objects.create(
            nom=nom, date_debut=date_debut, date_fin=date_fin)
        messages.success(request, f"Annee {nom} creee.")
        return redirect('liste_annees')
    return render(request, 'core/nouvelle_annee.html')


@login_required
@role_requis('DIRECTEUR')
def activer_annee(request, pk):
    from apps.academic.models import AnneeScolaire
    if request.method == 'POST':
        annee = get_object_or_404(AnneeScolaire, pk=pk)
        annee.est_active = True
        annee.save()
        messages.success(request, f"Annee {annee.nom} activee.")
    return redirect('liste_annees')


# ── PERIODES ──────────────────────────────────────────────────────────────────

@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def liste_periodes(request):
    from apps.academic.models import AnneeScolaire, Periode
    annee = AnneeScolaire.active()
    periodes = Periode.objects.filter(annee=annee).order_by('numero') if annee else []
    return render(request, 'core/periodes.html', {
        'periodes': periodes, 'annee': annee})


@login_required
@role_requis('DIRECTEUR')
def nouvelle_periode(request):
    from apps.academic.models import AnneeScolaire, Periode
    annee = AnneeScolaire.active()
    if not annee:
        messages.error(request, "Activez d'abord une annee scolaire.")
        return redirect('liste_periodes')
    if request.method == 'POST':
        type_p = request.POST.get('type', 'TRIMESTRE')
        numero = int(request.POST.get('numero', 1))
        date_debut = request.POST.get('date_debut') or None
        date_fin = request.POST.get('date_fin') or None
        if Periode.objects.filter(annee=annee, type=type_p, numero=numero).exists():
            messages.error(request, "Cette periode existe deja.")
            return redirect('liste_periodes')
        Periode.objects.create(
            annee=annee, type=type_p, numero=numero,
            date_debut=date_debut, date_fin=date_fin)
        messages.success(request, f"Periode creee.")
        return redirect('liste_periodes')
    return render(request, 'core/nouvelle_periode.html', {'annee': annee})


@login_required
@role_requis('DIRECTEUR')
def activer_periode(request, pk):
    from apps.academic.models import Periode
    if request.method == 'POST':
        periode = get_object_or_404(Periode, pk=pk)
        periode.est_active = True
        periode.save()
        messages.success(request, f"{periode} activee.")
    return redirect('liste_periodes')


# ── NIVEAUX ───────────────────────────────────────────────────────────────────

@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def liste_niveaux(request):
    from apps.academic.models import Niveau
    niveaux = Niveau.objects.all().order_by('ordre', 'nom')
    return render(request, 'core/niveaux.html', {'niveaux': niveaux})


@login_required
@role_requis('DIRECTEUR')
def nouveau_niveau(request):
    from apps.academic.models import Niveau
    if request.method == 'POST':
        nom = request.POST.get('nom', '').strip()
        ordre = int(request.POST.get('ordre', 0))
        systeme = request.POST.get('systeme', 'TRIMESTRIEL')
        type_ecole = request.POST.get('type_ecole', 'PRIVE')
        description = request.POST.get('description', '').strip()
        if not nom:
            messages.error(request, "Le nom est obligatoire.")
            return redirect('liste_niveaux')
        if Niveau.objects.filter(nom=nom).exists():
            messages.error(request, f"Le niveau {nom} existe deja.")
            return redirect('liste_niveaux')
        Niveau.objects.create(
            nom=nom, ordre=ordre, systeme=systeme,
            type_ecole=type_ecole, description=description)
        messages.success(request, f"Niveau {nom} cree.")
        return redirect('liste_niveaux')
    return render(request, 'core/nouveau_niveau.html')


@login_required
@role_requis('DIRECTEUR')
def modifier_niveau(request, pk):
    from apps.academic.models import Niveau
    niveau = get_object_or_404(Niveau, pk=pk)
    if request.method == 'POST':
        niveau.nom = request.POST.get('nom', '').strip()
        niveau.ordre = int(request.POST.get('ordre', 0))
        niveau.systeme = request.POST.get('systeme', 'TRIMESTRIEL')
        niveau.type_ecole = request.POST.get('type_ecole', 'PRIVE')
        niveau.description = request.POST.get('description', '').strip()
        niveau.save()
        messages.success(request, "Niveau mis a jour.")
        return redirect('liste_niveaux')
    return render(request, 'core/modifier_niveau.html', {'niveau': niveau})


@login_required
@role_requis('DIRECTEUR')
def supprimer_niveau(request, pk):
    from apps.academic.models import Niveau
    if request.method == 'POST':
        niveau = get_object_or_404(Niveau, pk=pk)
        if niveau.salles.exists():
            messages.error(request,
                "Impossible de supprimer — des salles sont rattachees a ce niveau.")
            return redirect('liste_niveaux')
        nom = niveau.nom
        niveau.delete()
        messages.success(request, f"Niveau {nom} supprime.")
    return redirect('liste_niveaux')


# ── GROUPES MATIERES ──────────────────────────────────────────────────────────

@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def groupes_matieres(request, niveau_pk):
    from apps.academic.models import Niveau, GroupeMatiere
    niveau = get_object_or_404(Niveau, pk=niveau_pk)
    groupes = GroupeMatiere.objects.filter(niveau=niveau).order_by('ordre')
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'ajouter':
            nom = request.POST.get('nom', '').strip()
            type_g = request.POST.get('type', 'AUTRE')
            ordre = int(request.POST.get('ordre', 0))
            est_obligatoire = request.POST.get('est_obligatoire') == '1'
            if nom:
                GroupeMatiere.objects.get_or_create(
                    niveau=niveau, nom=nom,
                    defaults={
                        'type': type_g,
                        'ordre': ordre,
                        'est_obligatoire': est_obligatoire,
                    })
                messages.success(request, f"Groupe {nom} ajoute.")
        elif action == 'supprimer':
            gid = request.POST.get('groupe_id')
            GroupeMatiere.objects.filter(pk=gid, niveau=niveau).delete()
            messages.success(request, "Groupe supprime.")
        return redirect('groupes_matieres', niveau_pk=niveau_pk)
    return render(request, 'core/groupes_matieres.html', {
        'niveau': niveau, 'groupes': groupes,
        'types': GroupeMatiere.TYPES,
    })