from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from .models import CustomUser


def custom_login(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    error = None
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        role = request.POST.get('role', '')

        if not all([username, password, role]):
            error = "Tous les champs sont obligatoires."
        else:
            user = authenticate(request, username=username, password=password)
            if user and user.is_active:
                if user.role != role:
                    error = f"Ce compte n'est pas un compte {dict(CustomUser.ROLES).get(role, role)}."
                else:
                    login(request, user)
                    # Bot B01 — alerte connexion (sera active a E3)
                    next_url = request.POST.get('next') or request.GET.get('next') or '/'
                    return redirect(next_url)
            elif user and not user.is_active:
                error = "Ce compte est desactive. Contactez l'administration."
            else:
                error = "Nom d'utilisateur ou mot de passe incorrect."

    return render(request, 'auth/login.html', {
        'error': error,
        'roles': CustomUser.ROLES,
        'next': request.GET.get('next', ''),
    })


def custom_logout(request):
    logout(request)
    return redirect('login')


@login_required
def changer_mot_de_passe(request):
    if request.method == 'POST':
        ancien = request.POST.get('ancien_mdp', '')
        nouveau = request.POST.get('nouveau_mdp', '')
        confirmation = request.POST.get('confirmation_mdp', '')

        if not request.user.check_password(ancien):
            messages.error(request, "Ancien mot de passe incorrect.")
        elif len(nouveau) < 6:
            messages.error(request, "Le nouveau mot de passe doit faire au moins 6 caracteres.")
        elif nouveau != confirmation:
            messages.error(request, "Les mots de passe ne correspondent pas.")
        else:
            request.user.set_password(nouveau)
            request.user.save()
            messages.success(request, "Mot de passe modifie. Reconnectez-vous.")
            logout(request)
            return redirect('login')

    return render(request, 'auth/changer_mot_de_passe.html')


@login_required
def profil(request):
    if request.method == 'POST':
        user = request.user
        user.first_name = request.POST.get('first_name', '').strip()
        user.last_name = request.POST.get('last_name', '').strip().upper()
        user.telephone = request.POST.get('telephone', '').strip()
        user.adresse = request.POST.get('adresse', '').strip()
        if request.FILES.get('photo'):
            user.photo = request.FILES['photo']
        user.save()
        messages.success(request, "Profil mis a jour.")
        return redirect('profil')
    return render(request, 'auth/profil.html')


@login_required
def liste_personnel(request):
    if not request.user.has_role('DIRECTEUR', 'CENSEUR', 'SECRETAIRE'):
        messages.error(request, "Acces refuse.")
        return redirect('dashboard')

    q = request.GET.get('q', '')
    role_f = request.GET.get('role', '')
    qs = CustomUser.objects.exclude(
        role__in=['PARENT', 'ELEVE']
    ).order_by('last_name', 'first_name')

    if q:
        qs = qs.filter(
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q) |
            Q(username__icontains=q)
        )
    if role_f:
        qs = qs.filter(role=role_f)

    return render(request, 'auth/liste_personnel.html', {
        'personnel': qs,
        'q': q,
        'role_filter': role_f,
        'roles': [r for r in CustomUser.ROLES if r[0] not in ('PARENT', 'ELEVE')],
        'total': qs.count(),
    })


@login_required
def nouveau_personnel(request):
    if not request.user.has_role('DIRECTEUR', 'CENSEUR', 'SECRETAIRE'):
        messages.error(request, "Acces refuse.")
        return redirect('dashboard')

    if request.method == 'POST':
        import random
        from django.contrib.auth.hashers import make_password

        prenom = request.POST.get('first_name', '').strip()
        nom = request.POST.get('last_name', '').strip().upper()
        role = request.POST.get('role', '')

        # Generation username unique
        base = f"{prenom[:6].lower()}.{nom[:4].lower()}"
        base = base.replace(' ', '').replace('-', '')
        username = base
        cpt = 1
        while CustomUser.objects.filter(username=username).exists():
            username = f"{base}{cpt}"
            cpt += 1

        pwd = f"iai{random.randint(1000, 9999)}"

        user = CustomUser(
            username=username,
            first_name=prenom,
            last_name=nom,
            role=role,
            telephone=request.POST.get('telephone', ''),
            telephone_wa=request.POST.get('telephone_wa', ''),
            specialite=request.POST.get('specialite', ''),
            password=make_password(pwd),
        )
        if request.FILES.get('photo'):
            user.photo = request.FILES['photo']
        user.save()

        messages.success(
            request,
            f"Compte cree — Login: {username} | MDP: {pwd} — "
            f"Notez ces informations et remettez-les a {prenom} {nom}."
        )
        return redirect('liste_personnel')

    roles = [r for r in CustomUser.ROLES if r[0] not in ('PARENT', 'ELEVE')]
    return render(request, 'auth/nouveau_personnel.html', {'roles': roles})


@login_required
def detail_personnel(request, pk):
    personne = get_object_or_404(CustomUser, pk=pk)
    return render(request, 'auth/detail_personnel.html', {'personne': personne})


@login_required
def modifier_personnel(request, pk):
    if not request.user.has_role('DIRECTEUR', 'CENSEUR'):
        messages.error(request, "Acces refuse.")
        return redirect('dashboard')

    personne = get_object_or_404(CustomUser, pk=pk)
    if request.method == 'POST':
        personne.first_name = request.POST.get('first_name', '')
        personne.last_name = request.POST.get('last_name', '').upper()
        personne.telephone = request.POST.get('telephone', '')
        personne.telephone_wa = request.POST.get('telephone_wa', '')
        personne.specialite = request.POST.get('specialite', '')
        personne.adresse = request.POST.get('adresse', '')
        if request.FILES.get('photo'):
            personne.photo = request.FILES['photo']
        pwd = request.POST.get('new_password', '').strip()
        if pwd:
            if len(pwd) >= 6:
                personne.set_password(pwd)
            else:
                messages.error(request, "Mot de passe trop court (6 caracteres minimum).")
                return redirect('modifier_personnel', pk=pk)
        personne.save()
        messages.success(request, "Mis a jour.")
        return redirect('detail_personnel', pk=pk)

    roles = [r for r in CustomUser.ROLES if r[0] not in ('PARENT', 'ELEVE')]
    return render(request, 'auth/modifier_personnel.html', {
        'personne': personne,
        'roles': roles,
    })


@login_required
def toggle_actif(request, pk):
    if not request.user.has_role('DIRECTEUR'):
        messages.error(request, "Acces refuse.")
        return redirect('dashboard')
    if request.method == 'POST':
        p = get_object_or_404(CustomUser, pk=pk)
        p.is_active = not p.is_active
        p.save()
        etat = "active" if p.is_active else "desactive"
        messages.success(request, f"Compte {etat}.")
    return redirect('detail_personnel', pk=pk)