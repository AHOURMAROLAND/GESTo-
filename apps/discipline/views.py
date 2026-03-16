from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
from .models import TypeSanction, Sanction, DemandeExclusion
from apps.academic.models import AnneeScolaire, SalleClasse
from apps.students.models import Eleve, Inscription
from apps.authentication.models import CustomUser
from apps.communication.models import Notification


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


# ── TYPES DE SANCTIONS ────────────────────────────────────────────────────────

@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def liste_types_sanctions(request):
    types = TypeSanction.objects.all().order_by('gravite', 'nom')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'ajouter':
            nom = request.POST.get('nom', '').strip()
            gravite = int(request.POST.get('gravite', 1))
            description = request.POST.get('description', '').strip()
            if nom:
                TypeSanction.objects.get_or_create(
                    nom=nom,
                    defaults={'gravite': gravite, 'description': description}
                )
                messages.success(request, f"Type '{nom}' ajoute.")
        elif action == 'supprimer':
            pk = request.POST.get('type_id')
            TypeSanction.objects.filter(pk=pk).delete()
            messages.success(request, "Type supprime.")
        return redirect('liste_types_sanctions')

    return render(request, 'discipline/types_sanctions.html', {
        'types': types,
        'gravites': TypeSanction._meta.get_field('gravite').choices,
    })


# ── SANCTIONS ─────────────────────────────────────────────────────────────────

@login_required
@role_requis('DIRECTEUR', 'CENSEUR', 'SURVEILLANT', 'PROFESSEUR')
def liste_sanctions(request):
    annee = AnneeScolaire.active()
    q = request.GET.get('q', '')
    statut_f = request.GET.get('statut', '')
    salle_f = request.GET.get('salle', '')

    sanctions = Sanction.objects.select_related(
        'eleve', 'type_sanction', 'signale_par', 'approuve_par'
    ).order_by('-created_at')

    if q:
        sanctions = sanctions.filter(
            Q(eleve__nom__icontains=q) |
            Q(eleve__prenom__icontains=q) |
            Q(motif__icontains=q)
        )
    if statut_f:
        sanctions = sanctions.filter(statut=statut_f)
    if salle_f and annee:
        sanctions = sanctions.filter(
            eleve__inscriptions__salle__pk=salle_f,
            eleve__inscriptions__annee=annee,
        )

    salles = SalleClasse.objects.filter(
        annee=annee, est_active=True
    ).order_by('niveau__ordre', 'nom') if annee else []

    return render(request, 'discipline/liste_sanctions.html', {
        'sanctions': sanctions,
        'salles': salles,
        'statuts': Sanction.STATUTS,
        'q': q,
        'statut_filtre': statut_f,
        'salle_filtre': salle_f,
        'total': sanctions.count(),
    })


@login_required
@role_requis('DIRECTEUR', 'CENSEUR', 'SURVEILLANT', 'PROFESSEUR')
def nouvelle_sanction(request):
    annee = AnneeScolaire.active()
    types = TypeSanction.objects.all().order_by('gravite', 'nom')
    salles = SalleClasse.objects.filter(
        annee=annee, est_active=True
    ).order_by('niveau__ordre', 'nom') if annee else []

    if request.method == 'POST':
        eleve_pk = request.POST.get('eleve_id')
        type_pk = request.POST.get('type_sanction_id')
        motif = request.POST.get('motif', '').strip()
        date_faits = request.POST.get('date_faits')
        commentaire = request.POST.get('commentaire', '').strip()

        if not all([eleve_pk, type_pk, motif, date_faits]):
            messages.error(
                request, "Eleve, type, motif et date sont obligatoires."
            )
            return render(request, 'discipline/nouvelle_sanction.html', {
                'types': types, 'salles': salles, 'annee': annee,
            })

        sanction = Sanction.objects.create(
            eleve_id=eleve_pk,
            type_sanction_id=type_pk,
            motif=motif,
            date_faits=date_faits,
            commentaire=commentaire,
            statut='EN_ATTENTE',
            signale_par=request.user,
        )

        # Notifier censeur et directeur
        for dest in CustomUser.objects.filter(
            role__in=['CENSEUR', 'DIRECTEUR'], is_active=True
        ):
            Notification.creer(
                destinataire=dest,
                titre=f"Nouvelle sanction — {sanction.eleve.nom_complet}",
                message=(
                    f"{sanction.type_sanction.nom} : {motif[:80]}"
                ),
                type='AVERTISSEMENT',
                lien=f'/discipline/{sanction.pk}/',
            )

        messages.success(
            request,
            f"Sanction signalee pour {sanction.eleve.nom_complet}."
        )
        return redirect('detail_sanction', pk=sanction.pk)

    return render(request, 'discipline/nouvelle_sanction.html', {
        'types': types,
        'salles': salles,
        'annee': annee,
    })


@login_required
def detail_sanction(request, pk):
    sanction = get_object_or_404(Sanction, pk=pk)
    return render(request, 'discipline/detail_sanction.html', {
        'sanction': sanction,
    })


@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def traiter_sanction(request, pk):
    if request.method == 'POST':
        sanction = get_object_or_404(Sanction, pk=pk)
        action = request.POST.get('action')
        commentaire = request.POST.get('commentaire', '').strip()

        if action == 'approuver':
            sanction.statut = 'APPROUVEE'
            sanction.approuve_par = request.user
            if commentaire:
                sanction.commentaire = commentaire
            sanction.save()

            # Notifier le signaleur
            Notification.creer(
                destinataire=sanction.signale_par,
                titre=f"Sanction approuvee — {sanction.eleve.nom_complet}",
                message=f"{sanction.type_sanction.nom} approuvee.",
                type='SUCCES',
                lien=f'/discipline/{sanction.pk}/',
            )
            messages.success(request, "Sanction approuvee.")

        elif action == 'rejeter':
            sanction.statut = 'REJETEE'
            sanction.approuve_par = request.user
            sanction.commentaire = commentaire
            sanction.save()
            messages.warning(request, "Sanction rejetee.")

        elif action == 'lever':
            sanction.statut = 'LEVEE'
            sanction.save()
            messages.info(request, "Sanction levee.")

    return redirect('detail_sanction', pk=pk)


# ── DEMANDES D'EXCLUSION ──────────────────────────────────────────────────────

@login_required
@role_requis('DIRECTEUR', 'CENSEUR', 'SURVEILLANT')
def liste_exclusions(request):
    exclusions = DemandeExclusion.objects.select_related(
        'eleve', 'demandee_par', 'traitee_par'
    ).order_by('-created_at')

    return render(request, 'discipline/liste_exclusions.html', {
        'exclusions': exclusions,
        'statuts': DemandeExclusion.STATUTS,
    })


@login_required
@role_requis('DIRECTEUR', 'CENSEUR', 'SURVEILLANT')
def nouvelle_exclusion(request):
    annee = AnneeScolaire.active()
    salles = SalleClasse.objects.filter(
        annee=annee, est_active=True
    ).order_by('niveau__ordre', 'nom') if annee else []

    if request.method == 'POST':
        eleve_pk = request.POST.get('eleve_id')
        motif = request.POST.get('motif', '').strip()

        if not eleve_pk or not motif:
            messages.error(request, "Eleve et motif sont obligatoires.")
            return redirect('nouvelle_exclusion')

        if DemandeExclusion.objects.filter(
            eleve_id=eleve_pk, statut='EN_ATTENTE'
        ).exists():
            messages.error(
                request,
                "Une demande d'exclusion est deja en attente pour cet eleve."
            )
            return redirect('liste_exclusions')

        exclusion = DemandeExclusion.objects.create(
            eleve_id=eleve_pk,
            motif=motif,
            statut='EN_ATTENTE',
            demandee_par=request.user,
        )

        # Notifier le directeur
        for d in CustomUser.objects.filter(
            role='DIRECTEUR', is_active=True
        ):
            Notification.creer(
                destinataire=d,
                titre=f"Demande exclusion — {exclusion.eleve.nom_complet}",
                message=f"Motif : {motif[:100]}",
                type='ALERTE',
                lien=f'/discipline/exclusions/{exclusion.pk}/',
            )

        messages.success(
            request,
            f"Demande d'exclusion soumise pour {exclusion.eleve.nom_complet}."
        )
        return redirect('detail_exclusion', pk=exclusion.pk)

    return render(request, 'discipline/nouvelle_exclusion.html', {
        'salles': salles,
        'annee': annee,
    })


@login_required
def detail_exclusion(request, pk):
    exclusion = get_object_or_404(DemandeExclusion, pk=pk)
    return render(request, 'discipline/detail_exclusion.html', {
        'exclusion': exclusion,
    })


@login_required
@role_requis('DIRECTEUR')
def traiter_exclusion(request, pk):
    if request.method == 'POST':
        exclusion = get_object_or_404(DemandeExclusion, pk=pk)
        action = request.POST.get('action')
        commentaire = request.POST.get('commentaire', '').strip()

        if action == 'approuver':
            exclusion.statut = 'APPROUVEE'
            exclusion.traitee_par = request.user
            exclusion.commentaire_directeur = commentaire
            exclusion.traitee_at = timezone.now()
            exclusion.save()

            # Changer statut de l'eleve
            from apps.students.models import Eleve
            eleve = exclusion.eleve
            eleve.statut = 'EXCLU'
            eleve.save()

            # Notifier le demandeur
            Notification.creer(
                destinataire=exclusion.demandee_par,
                titre=f"Exclusion approuvee — {eleve.nom_complet}",
                message="La demande d'exclusion a ete approuvee.",
                type='ALERTE',
                lien=f'/discipline/exclusions/{pk}/',
            )
            messages.success(
                request,
                f"{eleve.nom_complet} exclu(e). Statut mis a jour."
            )

        elif action == 'rejeter':
            exclusion.statut = 'REJETEE'
            exclusion.traitee_par = request.user
            exclusion.commentaire_directeur = commentaire
            exclusion.traitee_at = timezone.now()
            exclusion.save()

            Notification.creer(
                destinataire=exclusion.demandee_par,
                titre=f"Exclusion rejetee — {exclusion.eleve.nom_complet}",
                message=f"Motif : {commentaire}",
                type='INFO',
                lien=f'/discipline/exclusions/{pk}/',
            )
            messages.info(request, "Demande d'exclusion rejetee.")

    return redirect('detail_exclusion', pk=pk)


# ── DOSSIER DISCIPLINAIRE ELEVE ───────────────────────────────────────────────

@login_required
def dossier_disciplinaire(request, eleve_pk):
    eleve = get_object_or_404(Eleve, pk=eleve_pk)
    sanctions = Sanction.objects.filter(
        eleve=eleve
    ).select_related('type_sanction', 'signale_par').order_by('-date_faits')
    exclusions = DemandeExclusion.objects.filter(
        eleve=eleve
    ).select_related('demandee_par', 'traitee_par').order_by('-created_at')

    stats = {
        'total_sanctions': sanctions.count(),
        'approuvees': sanctions.filter(statut='APPROUVEE').count(),
        'en_attente': sanctions.filter(statut='EN_ATTENTE').count(),
        'exclusions': exclusions.count(),
    }

    return render(request, 'discipline/dossier_disciplinaire.html', {
        'eleve': eleve,
        'sanctions': sanctions,
        'exclusions': exclusions,
        'stats': stats,
    })


@login_required
@role_requis('DIRECTEUR', 'CENSEUR', 'SURVEILLANT')
def convocation_parent(request, pk):
    sanction = get_object_or_404(Sanction, pk=pk)
    # On récupère le parent principal si possible
    parent_eleve = EleveParent.objects.filter(eleve=sanction.eleve, est_contact_principal=True).first()
    if not parent_eleve:
        parent_eleve = EleveParent.objects.filter(eleve=sanction.eleve).first()

    return render(request, 'discipline/convocation_parent.html', {
        'sanction': sanction,
        'parent_eleve': parent_eleve,
        'today': timezone.now(),
    })
