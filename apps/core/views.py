from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.cache import cache
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
    from apps.academic.models import AnneeScolaire, Periode, SalleClasse
    from apps.students.models import Eleve, Inscription
    from apps.authentication.models import CustomUser
    from apps.communication.models import (
        Notification, ReunionParent, EvenementCalendrier
    )
    from django.utils import timezone

    annee = AnneeScolaire.active()
    periode = Periode.active(annee) if annee else None
    today = timezone.now().date()
    user = request.user

    context = {
        'annee_active': annee,
        'periode_active': periode,
        'today': today,
        'nb_eleves': 0,
        'nb_salles': 0,
        'nb_personnel': 0,
    }

    if annee:
        context['nb_salles'] = SalleClasse.objects.filter(
            annee=annee, est_active=True
        ).count()
        context['nb_eleves'] = Inscription.objects.filter(
            annee=annee, statut='ACTIVE'
        ).count()

    context['nb_personnel'] = CustomUser.objects.filter(
        is_active=True
    ).exclude(role__in=['PARENT', 'ELEVE']).count()

    # Prochains evenements
    context['prochains_evenements'] = EvenementCalendrier.objects.filter(
        annee=annee, date_debut__gte=today,
    ).order_by('date_debut')[:3] if annee else []

    context['prochaine_reunion'] = ReunionParent.objects.filter(
        annee=annee, date__gte=today, statut='PLANIFIEE',
    ).order_by('date').first() if annee else None

    # ── DIRECTEUR ─────────────────────────────────────────────────────────────
    if user.role in ('DIRECTEUR', 'CENSEUR') or user.is_superuser:
        stats_key = f'stats_directeur_{user.pk}_{annee.pk if annee else "none"}'
        stats = cache.get(stats_key)

        from apps.grades.models import Evaluation
        from apps.attendance.models import Presence
        from apps.finance.models import Paiement, FraisEleve
        from django.db.models import Sum
        import json

        # Presences du jour (not cached, volatile)
        presences_today = Presence.objects.filter(
            seance__date=today,
            seance__matiere_salle__salle__annee=annee,
        ) if annee else Presence.objects.none()

        context['nb_presents_today'] = presences_today.filter(
            statut='PRESENT'
        ).count()
        context['nb_absents_today'] = presences_today.filter(
            statut__in=['ABSENT', 'ABSENT_JUSTIFIE']
        ).count()

        if not stats:
            stats = {}
            # Evaluations en attente
            stats['nb_evals_attente'] = Evaluation.objects.filter(
                statut='BROUILLON',
                matiere_salle__salle__annee=annee,
            ).count() if annee else 0

            # Finance
            stats['total_recettes'] = float(
                Paiement.objects.aggregate(t=Sum('montant'))['t'] or 0
            )
            if annee:
                frais = FraisEleve.objects.filter(annee=annee)
                total_du = float(frais.aggregate(t=Sum('montant'))['t'] or 0)
                total_paye = float(
                    frais.aggregate(t=Sum('montant_paye'))['t'] or 0
                )
                stats['total_impaye'] = total_du - total_paye
                stats['taux_recouvrement'] = round(
                    total_paye / total_du * 100, 1
                ) if total_du > 0 else 0

            # Graphique 1 — Presences 7 derniers jours
            from datetime import timedelta
            labels_presences = []
            data_presents = []
            data_absents = []
            for i in range(6, -1, -1):
                j = today - timedelta(days=i)
                pres = Presence.objects.filter(
                    seance__date=j,
                    seance__matiere_salle__salle__annee=annee,
                ) if annee else Presence.objects.none()
                labels_presences.append(j.strftime('%d/%m'))
                data_presents.append(pres.filter(statut='PRESENT').count())
                data_absents.append(
                    pres.filter(
                        statut__in=['ABSENT', 'ABSENT_JUSTIFIE']
                    ).count()
                )
            stats['chart_presences_labels'] = json.dumps(labels_presences)
            stats['chart_presences_presents'] = json.dumps(data_presents)
            stats['chart_presences_absents'] = json.dumps(data_absents)

            # Graphique 2 — Eleves par niveau
            from apps.academic.models import Niveau
            niveaux_data = []
            niveaux_labels = []
            for niveau in Niveau.objects.all().order_by('ordre'):
                nb = Inscription.objects.filter(
                    salle__niveau=niveau,
                    annee=annee,
                    statut='ACTIVE',
                ).count() if annee else 0
                if nb > 0:
                    niveaux_labels.append(niveau.nom)
                    niveaux_data.append(nb)
            stats['chart_niveaux_labels'] = json.dumps(niveaux_labels)
            stats['chart_niveaux_data'] = json.dumps(niveaux_data)

            cache.set(stats_key, stats, 300) # 5 minutes cache

        context.update(stats)

        # Graphique 3 — Statuts evaluations
        from apps.grades.models import Evaluation
        statuts_evals = {
            'BROUILLON': 0, 'VALIDEE': 0,
            'EN_SAISIE': 0, 'NOTES_SAISIES': 0,
            'VALIDEE_FINALE': 0, 'REJETEE': 0,
        }
        if annee:
            for ev in Evaluation.objects.filter(
                matiere_salle__salle__annee=annee
            ).values('statut'):
                statuts_evals[ev['statut']] = (
                    statuts_evals.get(ev['statut'], 0) + 1
                )
        context['chart_evals_labels'] = json.dumps([
            'Brouillon', 'Validee', 'En saisie',
            'Notes saisies', 'Validee finale', 'Rejetee'
        ])
        context['chart_evals_data'] = json.dumps(
            list(statuts_evals.values())
        )

        # Alertes actives
        context['alertes'] = Notification.objects.filter(
            destinataire=user,
            est_lue=False,
            type='ALERTE',
        ).order_by('-created_at')[:5]

    # ── PROFESSEUR ────────────────────────────────────────────────────────────
    elif user.role == 'PROFESSEUR':
        from apps.academic.models import MatiereSalle
        from apps.grades.models import Evaluation, AutorisationSaisie
        import json

        mes_matieres = MatiereSalle.objects.filter(
            professeur=user,
            salle__annee=annee,
        ).select_related('matiere', 'salle', 'salle__niveau') if annee else []

        stats_matieres = []
        for ms in mes_matieres:
            nb_evals_total = Evaluation.objects.filter(matiere_salle=ms).count()
            nb_evals = Evaluation.objects.filter(
                matiere_salle=ms, statut='VALIDEE_FINALE'
            ).count()
            taux = round(nb_evals / nb_evals_total * 100) if nb_evals_total else 0
            stats_matieres.append({
                'ms': ms,
                'nb_evals': nb_evals,
                'nb_evals_total': nb_evals_total,
                'taux': taux,
            })

        context['stats_matieres'] = stats_matieres

        # Taches en attente
        context['taches'] = AutorisationSaisie.objects.filter(
            saisie_par=user,
            est_autorisee=True,
            notes_saisies=False,
        ).select_related(
            'evaluation__matiere_salle__salle',
            'evaluation__matiere_salle__matiere',
        )[:5]

        # Graphique — initialiser labels et data avant de les remplir
        labels = [ms['ms'].matiere.nom for ms in stats_matieres]
        data = [ms['taux'] for ms in stats_matieres]

        # Toujours définir ces clés même si vides
        context['chart_saisie_labels'] = json.dumps(labels)
        context['chart_saisie_data'] = json.dumps(data)

        # Devoirs recents
        from apps.devoirs.models import Devoir
        context['devoirs_recents'] = Devoir.objects.filter(
            publie_par=user,
            matiere_salle__salle__annee=annee,
        ).order_by('-date_publication')[:5] if annee else []

    # ── SECRETAIRE ────────────────────────────────────────────────────────────────
    elif user.role == 'SECRETAIRE':
        from apps.grades.models import AutorisationSaisie

        # Taches de saisie assignees a cette secretaire
        taches = AutorisationSaisie.objects.filter(
            saisie_par=user,
            est_autorisee=True,
            notes_saisies=False,
        ).select_related(
            'evaluation__matiere_salle__salle',
            'evaluation__matiere_salle__matiere',
            'evaluation__periode',
        ).order_by('-evaluation__created_at')

        taches_terminees = AutorisationSaisie.objects.filter(
            saisie_par=user,
            est_autorisee=True,
            notes_saisies=True,
        ).count()

        context['taches'] = taches
        context['nb_taches'] = taches.count()
        context['nb_taches_terminees'] = taches_terminees

    # ── COMPTABLE ─────────────────────────────────────────────────────────────
    elif user.role == 'COMPTABLE':
        from apps.finance.models import Paiement, Depense, FraisEleve
        from django.db.models import Sum
        from datetime import timedelta
        import json

        mes_paiements = Paiement.objects.filter(recu_par=user)
        mes_depenses = Depense.objects.filter(enregistre_par=user)

        context['total_recettes'] = float(
            mes_paiements.aggregate(t=Sum('montant'))['t'] or 0
        )
        context['total_depenses'] = float(
            mes_depenses.aggregate(t=Sum('montant'))['t'] or 0
        )
        context['nb_paiements'] = mes_paiements.count()

        # Graphique recettes 7 derniers jours
        labels = []
        data_rec = []
        for i in range(6, -1, -1):
            j = today - timedelta(days=i)
            total = float(
                mes_paiements.filter(
                    date_paiement=j
                ).aggregate(t=Sum('montant'))['t'] or 0
            )
            labels.append(j.strftime('%d/%m'))
            data_rec.append(total)

        context['chart_recettes_labels'] = json.dumps(labels)
        context['chart_recettes_data'] = json.dumps(data_rec)

        # Derniers paiements
        context['derniers_paiements'] = mes_paiements.select_related(
            'eleve', 'frais__type_frais'
        ).order_by('-created_at')[:5]

    # ── SURVEILLANT ───────────────────────────────────────────────────────────
    elif user.role == 'SURVEILLANT':
        from apps.attendance.models import Presence
        from apps.discipline.models import Sanction
        import json

        presences_today = Presence.objects.filter(
            seance__date=today,
            seance__matiere_salle__salle__annee=annee,
        ) if annee else Presence.objects.none()

        context['nb_absents_today'] = presences_today.filter(
            statut='ABSENT'
        ).count()
        context['nb_retards_today'] = presences_today.filter(
            statut='RETARD'
        ).count()
        context['nb_presents_today'] = presences_today.filter(
            statut='PRESENT'
        ).count()

        context['eleves_absents'] = presences_today.filter(
            statut='ABSENT'
        ).select_related(
            'eleve', 'seance__matiere_salle__salle'
        ).order_by('eleve__nom')[:10]

        context['sanctions_attente'] = Sanction.objects.filter(
            statut='EN_ATTENTE'
        ).select_related('eleve', 'type_sanction').count()

        # Graphique presences semaine
        from datetime import timedelta
        labels = []
        data_p = []
        data_a = []
        for i in range(4, -1, -1):
            j = today - timedelta(days=i)
            pres = Presence.objects.filter(
                seance__date=j,
                seance__matiere_salle__salle__annee=annee,
            ) if annee else Presence.objects.none()
            labels.append(j.strftime('%a %d'))
            data_p.append(pres.filter(statut='PRESENT').count())
            data_a.append(
                pres.filter(
                    statut__in=['ABSENT', 'ABSENT_JUSTIFIE']
                ).count()
            )
        context['chart_surv_labels'] = json.dumps(labels)
        context['chart_surv_presents'] = json.dumps(data_p)
        context['chart_surv_absents'] = json.dumps(data_a)

    # ── PARENT ────────────────────────────────────────────────────────────────
    elif user.role == 'PARENT':
        from apps.students.models import EleveParent
        from apps.grades.models import MoyenneGenerale
        from apps.finance.models import FraisEleve
        from django.db.models import Sum

        try:
            parent = user.profil_parent
            enfants_liens = EleveParent.objects.filter(
                parent=parent
            ).select_related('eleve')
        except Exception:
            enfants_liens = []

        enfants_data = []
        for ep in enfants_liens:
            eleve = ep.eleve
            insc = eleve.inscription_active
            moy = None
            if insc and periode:
                moy = MoyenneGenerale.objects.filter(
                    eleve=eleve, periode=periode
                ).first()

            frais = FraisEleve.objects.filter(
                eleve=eleve, annee=annee
            ) if annee else FraisEleve.objects.none()
            solde = float(
                frais.aggregate(
                    s=Sum('montant')
                )['s'] or 0
            ) - float(
                frais.aggregate(
                    s=Sum('montant_paye')
                )['s'] or 0
            )

            enfants_data.append({
                'eleve': eleve,
                'inscription': insc,
                'salle': insc.salle if insc else None,
                'moyenne': moy,
                'solde': solde,
                'lien': ep.get_lien_display(),
            })

        context['enfants_data'] = enfants_data

    # ── ELEVE ─────────────────────────────────────────────────────────────────
    elif user.role == 'ELEVE':
        from apps.grades.models import MoyenneGenerale, MoyenneMatiere
        from apps.attendance.models import Presence
        import json

        try:
            eleve = user.profil_eleve
        except Exception:
            eleve = None

        if eleve:
            context['eleve'] = eleve
            insc = eleve.inscription_active
            context['inscription'] = insc

            if insc and periode:
                moy_gen = MoyenneGenerale.objects.filter(
                    eleve=eleve, periode=periode
                ).first()
                context['moy_gen'] = moy_gen

                moy_matieres = MoyenneMatiere.objects.filter(
                    eleve=eleve,
                    periode=periode,
                    matiere_salle__salle=insc.salle,
                ).select_related(
                    'matiere_salle__matiere'
                ).order_by('-moyenne_eleve')
                context['moy_matieres'] = moy_matieres

                # Graphique moyennes par matiere
                labels = [m.matiere_salle.matiere.nom for m in moy_matieres]
                data = [float(m.moyenne_eleve) for m in moy_matieres]
                context['chart_eleve_labels'] = json.dumps(labels)
                context['chart_eleve_data'] = json.dumps(data)

            context['nb_absences'] = Presence.objects.filter(
                eleve=eleve,
                statut__in=['ABSENT', 'ABSENT_JUSTIFIE'],
                seance__matiere_salle__salle__annee=annee,
            ).count() if annee else 0

            # Devoirs a rendre
            from apps.devoirs.models import Devoir, SoumissionDevoir
            tous_devoirs = Devoir.objects.filter(
                matiere_salle__salle=insc.salle,
                statut='PUBLIE'
            ).exclude(
                pk__in=SoumissionDevoir.objects.filter(eleve=eleve).values_list('devoir_id', flat=True)
            ).order_by('date_limite')
            context['devoirs_a_rendre'] = tous_devoirs[:5]
            context['nb_devoirs_attente'] = tous_devoirs.count()

    role = user.role
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


# ── SAUVEGARDES ───────────────────────────────────────────────────────────────

@login_required
@role_requis('DIRECTEUR')
def liste_sauvegardes(request):
    from .backup import lister_sauvegardes
    sauvegardes_db = SauvegardeAuto.objects.all()[:20]
    fichiers = lister_sauvegardes()
    return render(request, 'core/sauvegardes.html', {
        'sauvegardes_db': sauvegardes_db,
        'fichiers': fichiers,
    })


@login_required
@role_requis('DIRECTEUR')
def declencher_sauvegarde(request):
    from .backup import sauvegarde_manuelle
    if request.method == 'POST':
        success = sauvegarde_manuelle(user=request.user)
        if success:
            messages.success(request, "Sauvegarde reussie.")
        else:
            messages.error(request, "La sauvegarde a echoue.")
    return redirect('liste_sauvegardes')


@login_required
@role_requis('DIRECTEUR')
def telecharger_sauvegarde(request, filename):
    import os
    from django.conf import settings
    from django.http import FileResponse, Http404

    # Securite : empecher de sortir du dossier backups
    if '..' in filename or '/' in filename or '\\' in filename:
        raise Http404("Fichier invalide.")

    path = os.path.join(settings.BASE_DIR, 'backups', filename)
    if os.path.exists(path):
        return FileResponse(open(path, 'rb'), as_attachment=True)
    
    raise Http404("Fichier introuvable.")


# ── PWA ─────────────────────────────────────────────────────────────────────

def pwa_manifest(request):
    from django.http import JsonResponse
    import json
    import os
    from django.conf import settings
    path = os.path.join(settings.BASE_DIR, 'static', 'manifest.json')
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return JsonResponse(data)


def pwa_sw(request):
    from django.http import HttpResponse
    import os
    from django.conf import settings
    path = os.path.join(settings.BASE_DIR, 'static', 'sw.js')
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    return HttpResponse(content, content_type='application/javascript')


def offline(request):
    return render(request, 'core/offline.html')