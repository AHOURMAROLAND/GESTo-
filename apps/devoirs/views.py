from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import Devoir, SoumissionDevoir
from apps.academic.models import AnneeScolaire, MatiereSalle
from apps.students.models import Inscription, Eleve
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


# ── LISTE DEVOIRS ─────────────────────────────────────────────────────────────

@login_required
def liste_devoirs(request):
    annee = AnneeScolaire.active()
    user = request.user

    if user.role == 'PROFESSEUR':
        devoirs = Devoir.objects.filter(
            publie_par=user,
            matiere_salle__salle__annee=annee,
        ).select_related(
            'matiere_salle__matiere',
            'matiere_salle__salle',
        )
    elif user.role in ('DIRECTEUR', 'CENSEUR'):
        devoirs = Devoir.objects.filter(
            matiere_salle__salle__annee=annee,
        ).select_related(
            'matiere_salle__matiere',
            'matiere_salle__salle',
            'publie_par',
        )
    elif user.role == 'ELEVE':
        try:
            eleve = user.profil_eleve
            insc = eleve.inscription_active
            if insc:
                devoirs = Devoir.objects.filter(
                    matiere_salle__salle=insc.salle,
                    statut='PUBLIE',
                ).select_related(
                    'matiere_salle__matiere',
                    'publie_par',
                )
            else:
                devoirs = Devoir.objects.none()
        except Exception:
            devoirs = Devoir.objects.none()
    elif user.role == 'PARENT':
        try:
            parent = user.profil_parent
            enfants = [ep.eleve for ep in parent.enfants.all()]
            salles = [
                e.inscription_active.salle
                for e in enfants
                if e.inscription_active
            ]
            devoirs = Devoir.objects.filter(
                matiere_salle__salle__in=salles,
                statut='PUBLIE',
            ).select_related(
                'matiere_salle__matiere',
                'matiere_salle__salle',
            )
        except Exception:
            devoirs = Devoir.objects.none()
    else:
        devoirs = Devoir.objects.none()

    return render(request, 'devoirs/liste_devoirs.html', {
        'devoirs': devoirs,
        'annee': annee,
        'today': timezone.now().date(),
    })


# ── NOUVEAU DEVOIR ────────────────────────────────────────────────────────────

@login_required
@role_requis('PROFESSEUR', 'CENSEUR', 'DIRECTEUR')
def nouveau_devoir(request):
    annee = AnneeScolaire.active()
    user = request.user

    if user.role == 'PROFESSEUR':
        matieres = MatiereSalle.objects.filter(
            professeur=user,
            salle__annee=annee,
        ).select_related('matiere', 'salle', 'salle__niveau')
    else:
        matieres = MatiereSalle.objects.filter(
            salle__annee=annee,
        ).select_related('matiere', 'salle', 'salle__niveau')

    if request.method == 'POST':
        titre = request.POST.get('titre', '').strip()
        type_d = request.POST.get('type', 'DEVOIR')
        description = request.POST.get('description', '').strip()
        date_limite = request.POST.get('date_limite')
        note_sur = float(request.POST.get('note_sur', 20))
        ms_pk = request.POST.get('matiere_salle_id')

        if not all([titre, description, date_limite, ms_pk]):
            messages.error(request, "Tous les champs sont obligatoires.")
            return render(request, 'devoirs/nouveau_devoir.html', {
                'matieres': matieres, 'types': Devoir.TYPES, 'annee': annee,
            })

        devoir = Devoir.objects.create(
            titre=titre,
            type=type_d,
            description=description,
            date_limite=date_limite,
            note_sur=note_sur,
            matiere_salle_id=ms_pk,
            publie_par=user,
            statut='PUBLIE',
        )

        if request.FILES.get('fichier_joint'):
            devoir.fichier_joint = request.FILES['fichier_joint']
            devoir.save()

        # Bot B28 — notifier les eleves et parents
        try:
            from django_q.tasks import async_task
            async_task(
                'apps.devoirs.tasks.notifier_nouveau_devoir',
                devoir.pk,
            )
        except Exception:
            pass

        messages.success(
            request,
            f"Devoir '{titre}' publie pour {devoir.nb_inscrits} eleve(s)."
        )
        return redirect('detail_devoir', pk=devoir.pk)

    return render(request, 'devoirs/nouveau_devoir.html', {
        'matieres': matieres,
        'types': Devoir.TYPES,
        'annee': annee,
        'today': timezone.now().date().isoformat(),
    })


# ── DETAIL DEVOIR ─────────────────────────────────────────────────────────────

@login_required
def detail_devoir(request, pk):
    devoir = get_object_or_404(Devoir, pk=pk)
    user = request.user
    today = timezone.now().date()

    soumissions = devoir.soumissions.select_related(
        'eleve', 'corrige_par'
    ).order_by('eleve__nom')

    ma_soumission = None
    if user.role == 'ELEVE':
        try:
            eleve = user.profil_eleve
            ma_soumission = SoumissionDevoir.objects.filter(
                devoir=devoir, eleve=eleve
            ).first()
        except Exception:
            pass

    # Liste eleves qui n'ont pas rendu
    inscrits = devoir.matiere_salle.salle.inscriptions.filter(
        statut='ACTIVE'
    ).select_related('eleve')
    soumis_ids = set(s.eleve_id for s in soumissions)
    non_rendus = [i.eleve for i in inscrits if i.eleve_id not in soumis_ids]

    return render(request, 'devoirs/detail_devoir.html', {
        'devoir': devoir,
        'soumissions': soumissions,
        'ma_soumission': ma_soumission,
        'non_rendus': non_rendus,
        'today': today,
        'peut_soumettre': (
            user.role == 'ELEVE'
            and not ma_soumission
            and devoir.statut == 'PUBLIE'
        ),
    })


# ── SOUMISSION ELEVE ──────────────────────────────────────────────────────────

@login_required
@role_requis('ELEVE')
def soumettre_devoir(request, pk):
    devoir = get_object_or_404(Devoir, pk=pk)
    user = request.user
    today = timezone.now().date()

    try:
        eleve = user.profil_eleve
    except Exception:
        messages.error(request, "Profil eleve introuvable.")
        return redirect('liste_devoirs')

    if SoumissionDevoir.objects.filter(
        devoir=devoir, eleve=eleve
    ).exists():
        messages.warning(request, "Vous avez deja soumis ce devoir.")
        return redirect('detail_devoir', pk=pk)

    if devoir.statut != 'PUBLIE':
        messages.error(request, "Ce devoir n'accepte plus de soumissions.")
        return redirect('detail_devoir', pk=pk)

    if request.method == 'POST':
        contenu = request.POST.get('contenu_texte', '').strip()
        fichier = request.FILES.get('fichier')

        if not contenu and not fichier:
            messages.error(
                request, "Soumettez un texte ou un fichier."
            )
            return render(request, 'devoirs/soumettre.html', {
                'devoir': devoir
            })

        statut = 'EN_RETARD' if today > devoir.date_limite else 'SOUMIS'

        soumission = SoumissionDevoir.objects.create(
            devoir=devoir,
            eleve=eleve,
            contenu_texte=contenu,
            statut=statut,
        )

        if fichier:
            soumission.fichier = fichier
            soumission.save()

        messages.success(
            request,
            "Devoir soumis avec succes."
            + (" (en retard)" if statut == 'EN_RETARD' else "")
        )
        return redirect('detail_devoir', pk=pk)

    return render(request, 'devoirs/soumettre.html', {
        'devoir': devoir,
        'today': today,
    })


# ── CORRECTION ────────────────────────────────────────────────────────────────

@login_required
@role_requis('PROFESSEUR', 'CENSEUR', 'DIRECTEUR')
def corriger_soumission(request, pk):
    soumission = get_object_or_404(SoumissionDevoir, pk=pk)

    if request.method == 'POST':
        note_str = request.POST.get('note', '').strip()
        commentaire = request.POST.get('commentaire', '').strip()

        note = None
        if note_str:
            try:
                note = float(note_str.replace(',', '.'))
                if not 0 <= note <= float(soumission.devoir.note_sur):
                    messages.error(
                        request,
                        f"Note invalide (0 a {soumission.devoir.note_sur})."
                    )
                    return redirect(
                        'detail_devoir', pk=soumission.devoir.pk
                    )
            except ValueError:
                messages.error(request, "Note invalide.")
                return redirect('detail_devoir', pk=soumission.devoir.pk)

        soumission.note = note
        soumission.commentaire_prof = commentaire
        soumission.statut = 'CORRIGE'
        soumission.corrige_par = request.user
        soumission.date_correction = timezone.now()
        soumission.save()

        messages.success(
            request,
            f"Correction enregistree pour {soumission.eleve.nom_complet}."
        )
    return redirect('detail_devoir', pk=soumission.devoir.pk)


# ── CLORE DEVOIR ──────────────────────────────────────────────────────────────

@login_required
@role_requis('PROFESSEUR', 'CENSEUR', 'DIRECTEUR')
def clore_devoir(request, pk):
    if request.method == 'POST':
        devoir = get_object_or_404(Devoir, pk=pk)
        devoir.statut = 'CLOS'
        devoir.save()
        messages.success(request, f"Devoir '{devoir.titre}' clos.")
    return redirect('detail_devoir', pk=pk)


# ── MES DEVOIRS ELEVE ─────────────────────────────────────────────────────────

@login_required
@role_requis('ELEVE')
def mes_soumissions(request):
    user = request.user
    try:
        eleve = user.profil_eleve
        soumissions = SoumissionDevoir.objects.filter(
            eleve=eleve
        ).select_related(
            'devoir__matiere_salle__matiere',
            'devoir__matiere_salle__salle',
        ).order_by('-date_soumission')
    except Exception:
        soumissions = []

    return render(request, 'devoirs/mes_soumissions.html', {
        'soumissions': soumissions,
    })
