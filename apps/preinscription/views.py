from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import PreInscription
from apps.academic.models import AnneeScolaire, Niveau, SalleClasse
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


# ── FORMULAIRE PUBLIC ─────────────────────────────────────────────────────────

def formulaire_preinscription(request):
    """Vue publique — accessible sans connexion."""
    from apps.core.models import ConfigurationEcole
    config = ConfigurationEcole.get()
    annee = AnneeScolaire.active()
    niveaux = Niveau.objects.all().order_by('ordre', 'nom')

    if request.method == 'POST':
        # Infos eleve
        nom_eleve = request.POST.get('nom_eleve', '').strip().upper()
        prenom_eleve = request.POST.get('prenom_eleve', '').strip()
        sexe_eleve = request.POST.get('sexe_eleve', 'M')
        date_naissance = request.POST.get('date_naissance') or None
        lieu_naissance = request.POST.get('lieu_naissance', '').strip()
        niveau_souhaite = request.POST.get('niveau_souhaite', '').strip()
        est_redoublant = request.POST.get('est_redoublant') == '1'
        ancienne_ecole = request.POST.get('ancienne_ecole', '').strip()

        # Infos parent
        nom_parent = request.POST.get('nom_parent', '').strip().upper()
        prenom_parent = request.POST.get('prenom_parent', '').strip()
        telephone_parent = request.POST.get('telephone_parent', '').strip()
        telephone_wa_parent = request.POST.get(
            'telephone_wa_parent', ''
        ).strip()
        email_parent = request.POST.get('email_parent', '').strip()
        profession_parent = request.POST.get('profession_parent', '').strip()
        adresse_parent = request.POST.get('adresse_parent', '').strip()
        lien_parent = request.POST.get('lien_parent', 'TUTEUR')

        # Validation minimale
        if not all([nom_eleve, prenom_eleve, niveau_souhaite,
                    nom_parent, telephone_parent]):
            return render(request, 'preinscription/formulaire.html', {
                'config': config,
                'niveaux': niveaux,
                'annee': annee,
                'error': "Les champs marques * sont obligatoires.",
                'post': request.POST,
            })

        pi = PreInscription.objects.create(
            nom_eleve=nom_eleve,
            prenom_eleve=prenom_eleve,
            sexe_eleve=sexe_eleve,
            date_naissance=date_naissance,
            lieu_naissance=lieu_naissance,
            niveau_souhaite=niveau_souhaite,
            est_redoublant=est_redoublant,
            ancienne_ecole=ancienne_ecole,
            nom_parent=nom_parent,
            prenom_parent=prenom_parent,
            telephone_parent=telephone_parent,
            telephone_wa_parent=telephone_wa_parent or telephone_parent,
            email_parent=email_parent,
            profession_parent=profession_parent,
            adresse_parent=adresse_parent,
            lien_parent=lien_parent,
            statut='EN_ATTENTE',
        )

        # Notifier secrétaires et censeurs
        from apps.communication.models import Notification
        for dest in CustomUser.objects.filter(
            role__in=['SECRETAIRE', 'CENSEUR', 'DIRECTEUR'],
            is_active=True,
        ):
            Notification.creer(
                destinataire=dest,
                titre=f"Nouvelle pre-inscription — {prenom_eleve} {nom_eleve}",
                message=f"Niveau souhaite : {niveau_souhaite}",
                type='INFO',
                lien=f'/inscription/admin/{pi.pk}/',
            )

        return redirect('confirmation_preinscription', ref=pi.reference)

    return render(request, 'preinscription/formulaire.html', {
        'config': config,
        'niveaux': niveaux,
        'annee': annee,
    })


def confirmation_preinscription(request, ref):
    """Page de confirmation publique."""
    from apps.core.models import ConfigurationEcole
    config = ConfigurationEcole.get()
    pi = get_object_or_404(PreInscription, reference=ref)
    return render(request, 'preinscription/confirmation.html', {
        'pi': pi,
        'config': config,
    })


# ── GESTION ADMIN ─────────────────────────────────────────────────────────────

@login_required
@role_requis('DIRECTEUR', 'CENSEUR', 'SECRETAIRE')
def liste_preinscriptions(request):
    statut_f = request.GET.get('statut', 'EN_ATTENTE')
    pis = PreInscription.objects.all()
    if statut_f:
        pis = pis.filter(statut=statut_f)

    return render(request, 'preinscription/liste.html', {
        'pis': pis,
        'statut_filtre': statut_f,
        'statuts': PreInscription.STATUTS,
        'total': pis.count(),
        'nb_attente': PreInscription.objects.filter(
            statut='EN_ATTENTE'
        ).count(),
    })


@login_required
@role_requis('DIRECTEUR', 'CENSEUR', 'SECRETAIRE')
def detail_preinscription(request, pk):
    pi = get_object_or_404(PreInscription, pk=pk)
    annee = AnneeScolaire.active()
    salles = SalleClasse.objects.filter(
        annee=annee, est_active=True,
    ).order_by('niveau__ordre', 'nom') if annee else []

    return render(request, 'preinscription/detail.html', {
        'pi': pi,
        'salles': salles,
        'annee': annee,
        'peut_valider': request.user.is_superuser or request.user.role in ('DIRECTEUR', 'CENSEUR'),
    })


@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def valider_preinscription(request, pk):
    if request.method != 'POST':
        return redirect('detail_preinscription', pk=pk)

    pi = get_object_or_404(PreInscription, pk=pk)

    if pi.statut != 'EN_ATTENTE':
        messages.error(request, "Cette pre-inscription a deja ete traitee.")
        return redirect('detail_preinscription', pk=pk)

    annee = AnneeScolaire.active()
    if not annee:
        messages.error(request, "Aucune annee active.")
        return redirect('detail_preinscription', pk=pk)

    salle_pk = request.POST.get('salle_id')
    if not salle_pk:
        messages.error(request, "Choisissez une salle.")
        return redirect('detail_preinscription', pk=pk)

    import random
    from django.contrib.auth.hashers import make_password
    from apps.students.models import Eleve, Parent, EleveParent, Inscription

    # 1 — Creer compte et profil eleve
    username_base = f"{pi.prenom_eleve[:6].lower()}.{pi.nom_eleve[:4].lower()}"
    username_base = username_base.replace(' ', '').replace('-', '')
    username = username_base
    cpt = 1
    while CustomUser.objects.filter(username=username).exists():
        username = f"{username_base}{cpt}"
        cpt += 1

    pwd_eleve = f"bkt{random.randint(1000, 9999)}"

    user_eleve = CustomUser.objects.create(
        username=username,
        first_name=pi.prenom_eleve,
        last_name=pi.nom_eleve,
        role='ELEVE',
        password=make_password(pwd_eleve),
    )

    from django.utils import timezone as tz
    matricule = f"BKT-{tz.now().year}-{random.randint(1000, 9999):04d}"
    while Eleve.objects.filter(matricule=matricule).exists():
        matricule = f"BKT-{tz.now().year}-{random.randint(1000, 9999):04d}"

    eleve = Eleve.objects.create(
        user=user_eleve,
        matricule=matricule,
        nom=pi.nom_eleve,
        prenom=pi.prenom_eleve,
        sexe=pi.sexe_eleve,
        date_naissance=pi.date_naissance,
        lieu_naissance=pi.lieu_naissance,
        redoublant=pi.est_redoublant,
        statut='ACTIF',
    )

    # 2 — Inscription dans la salle
    Inscription.objects.create(
        eleve=eleve,
        salle_id=salle_pk,
        annee=annee,
        statut='ACTIVE',
    )

    # 3 — Creer compte et profil parent
    username_parent = f"parent.{pi.nom_parent[:6].lower()}".replace(' ', '')
    cpt = 1
    up = username_parent
    while CustomUser.objects.filter(username=up).exists():
        up = f"{username_parent}{cpt}"
        cpt += 1

    pwd_parent = f"bkt{random.randint(1000, 9999)}"

    user_parent = CustomUser.objects.create(
        username=up,
        first_name=pi.prenom_parent,
        last_name=pi.nom_parent,
        role='PARENT',
        telephone=pi.telephone_parent,
        telephone_wa=pi.telephone_wa_parent,
        password=make_password(pwd_parent),
    )

    parent = Parent.objects.create(
        user=user_parent,
        nom=pi.nom_parent,
        prenom=pi.prenom_parent,
        telephone=pi.telephone_parent,
        email=pi.email_parent,
        profession=pi.profession_parent,
        adresse=pi.adresse_parent,
    )

    EleveParent.objects.create(
        eleve=eleve,
        parent=parent,
        lien=pi.lien_parent,
        est_contact_principal=True,
    )

    # 4 — Mettre a jour la pre-inscription
    pi.statut = 'VALIDEE'
    pi.traitee_par = request.user
    pi.date_traitement = tz.now()
    pi.eleve_cree = eleve
    pi.save()

    # 5 — Envoyer identifiants par WhatsApp (bot B23)
    try:
        from apps.communication.bots import envoyer_bot
        envoyer_bot('B23', {
            'parent': f"{pi.prenom_parent} {pi.nom_parent}",
            'eleve': f"{pi.prenom_eleve} {pi.nom_eleve}",
            'username': up,
            'password': pwd_parent,
            'lien': '/login/',
        }, destinataire_user=user_parent)

        # Identifiants eleve par WhatsApp aussi
        envoyer_bot('B03', {
            'username': username,
            'password': pwd_eleve,
            'lien': '/login/',
        }, destinataire_user=user_parent)
    except Exception:
        pass

    messages.success(
        request,
        f"Pre-inscription validee ! "
        f"Eleve: {username} / {pwd_eleve} — "
        f"Parent: {up} / {pwd_parent} — "
        f"Identifiants envoyes par WhatsApp."
    )
    return redirect('detail_preinscription', pk=pk)


@login_required
@role_requis('DIRECTEUR', 'CENSEUR', 'SECRETAIRE')
def rejeter_preinscription(request, pk):
    if request.method == 'POST':
        pi = get_object_or_404(PreInscription, pk=pk)
        commentaire = request.POST.get('commentaire', '').strip()
        pi.statut = 'REJETEE'
        pi.traitee_par = request.user
        pi.date_traitement = timezone.now()
        pi.commentaire = commentaire
        pi.save()
        messages.warning(request, "Pre-inscription rejetee.")
    return redirect('liste_preinscriptions')
