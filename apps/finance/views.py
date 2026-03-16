from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db.models import Sum, Q
from django.utils import timezone
from .models import (
    TypeFrais, TarifNiveau, TypeCollecte,
    FraisEleve, Paiement, Depense
)
from apps.academic.models import AnneeScolaire, Niveau, SalleClasse
from apps.students.models import Eleve, Inscription
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


def generer_numero_recu(annee_str):
    """Genere un numero sequentiel REC-2025-0001."""
    prefix = f"REC-{annee_str}-"
    derniers = Paiement.objects.filter(
        numero_recu__startswith=prefix
    ).order_by('-numero_recu')
    if derniers.exists():
        dernier = derniers.first().numero_recu
        try:
            num = int(dernier.split('-')[-1]) + 1
        except ValueError:
            num = 1
    else:
        num = 1
    return f"{prefix}{num:04d}"


# ── DASHBOARD FINANCE ─────────────────────────────────────────────────────────

@login_required
@role_requis('DIRECTEUR', 'CENSEUR', 'COMPTABLE')
def dashboard_finance(request):
    annee = AnneeScolaire.active()
    user = request.user
    comptable_f = request.GET.get('comptable', '')

    # Filtrage selon le role
    if user.role == 'COMPTABLE':
        paiements_qs = Paiement.objects.filter(recu_par=user)
        depenses_qs = Depense.objects.filter(enregistre_par=user)
    elif user.role in ('DIRECTEUR', 'CENSEUR'):
        paiements_qs = Paiement.objects.all()
        depenses_qs = Depense.objects.all()
        if comptable_f:
            paiements_qs = paiements_qs.filter(recu_par_id=comptable_f)
            depenses_qs = depenses_qs.filter(enregistre_par_id=comptable_f)
    else:
        paiements_qs = Paiement.objects.none()
        depenses_qs = Depense.objects.none()

    total_recettes = paiements_qs.aggregate(
        t=Sum('montant')
    )['t'] or 0

    total_depenses = depenses_qs.aggregate(
        t=Sum('montant')
    )['t'] or 0

    solde = total_recettes - total_depenses

    # Impayés
    if annee:
        frais_qs = FraisEleve.objects.filter(annee=annee)
        total_attendu = frais_qs.aggregate(t=Sum('montant'))['t'] or 0
        total_paye = frais_qs.aggregate(t=Sum('montant_paye'))['t'] or 0
        total_impaye = total_attendu - total_paye
        taux_recouvrement = round(
            total_paye / total_attendu * 100, 1
        ) if total_attendu > 0 else 0
    else:
        total_attendu = total_impaye = taux_recouvrement = 0

    # Derniers paiements
    derniers_paiements = paiements_qs.select_related(
        'eleve', 'frais', 'recu_par'
    ).order_by('-created_at')[:10]

    # Comptables pour le filtre directeur
    comptables = CustomUser.objects.filter(
        role='COMPTABLE', is_active=True
    ) if user.role in ('DIRECTEUR', 'CENSEUR') else []

    return render(request, 'finance/dashboard_finance.html', {
        'annee': annee,
        'total_recettes': total_recettes,
        'total_depenses': total_depenses,
        'solde': solde,
        'total_attendu': total_attendu,
        'total_impaye': total_impaye,
        'taux_recouvrement': taux_recouvrement,
        'derniers_paiements': derniers_paiements,
        'comptables': comptables,
        'comptable_filtre': comptable_f,
    })


# ── TARIFS ────────────────────────────────────────────────────────────────────

@login_required
@role_requis('DIRECTEUR', 'CENSEUR', 'COMPTABLE')
def liste_tarifs(request):
    annee = AnneeScolaire.active()
    niveaux = Niveau.objects.all().order_by('ordre', 'nom')
    tarifs = TarifNiveau.objects.filter(
        annee=annee
    ).select_related('niveau') if annee else []
    types_frais = TypeFrais.objects.all()

    return render(request, 'finance/tarifs.html', {
        'niveaux': niveaux,
        'tarifs': tarifs,
        'types_frais': types_frais,
        'annee': annee,
    })


@login_required
@role_requis('DIRECTEUR', 'COMPTABLE')
def creer_tarif(request):
    annee = AnneeScolaire.active()
    if not annee:
        messages.error(request, "Aucune annee active.")
        return redirect('liste_tarifs')

    if request.method == 'POST':
        niveau_pk = request.POST.get('niveau_id')
        frais_inscription = float(request.POST.get('frais_inscription', 0))
        frais_scolarite = float(request.POST.get('frais_scolarite', 0))
        frais_examen = float(request.POST.get('frais_examen', 0))

        if not niveau_pk:
            messages.error(request, "Choisissez un niveau.")
            return redirect('liste_tarifs')

        TarifNiveau.objects.update_or_create(
            niveau_id=niveau_pk,
            annee=annee,
            defaults={
                'frais_inscription': frais_inscription,
                'frais_scolarite': frais_scolarite,
                'frais_examen': frais_examen,
            }
        )
        messages.success(request, "Tarif enregistre.")
    return redirect('liste_tarifs')


@login_required
@role_requis('DIRECTEUR')
def initialiser_types_frais(request):
    types = [
        ('Frais d\'inscription', True),
        ('Frais de scolarite', True),
        ('Frais d\'examen', True),
    ]
    for nom, obligatoire in types:
        TypeFrais.objects.get_or_create(
            nom=nom,
            defaults={'est_obligatoire': obligatoire}
        )
    messages.success(request, "Types de frais initialises.")
    return redirect('liste_tarifs')


# ── COLLECTES ─────────────────────────────────────────────────────────────────

@login_required
@role_requis('DIRECTEUR', 'COMPTABLE')
def liste_collectes(request):
    annee = AnneeScolaire.active()
    collectes = TypeCollecte.objects.filter(
        annee=annee
    ).select_related('niveau', 'salle') if annee else []

    return render(request, 'finance/collectes.html', {
        'collectes': collectes,
        'annee': annee,
    })


@login_required
@role_requis('DIRECTEUR', 'COMPTABLE')
def nouvelle_collecte(request):
    annee = AnneeScolaire.active()
    if not annee:
        messages.error(request, "Aucune annee active.")
        return redirect('liste_collectes')

    niveaux = Niveau.objects.all().order_by('ordre')
    salles = SalleClasse.objects.filter(
        annee=annee, est_active=True
    ).order_by('niveau__ordre', 'nom')

    if request.method == 'POST':
        nom = request.POST.get('nom', '').strip()
        montant = float(request.POST.get('montant', 0))
        description = request.POST.get('description', '').strip()
        cible = request.POST.get('cible', 'TOUS')
        niveau_pk = request.POST.get('niveau_id') or None
        salle_pk = request.POST.get('salle_id') or None

        if not nom or montant <= 0:
            messages.error(request, "Nom et montant sont obligatoires.")
            return redirect('nouvelle_collecte')

        TypeCollecte.objects.create(
            nom=nom,
            montant=montant,
            description=description,
            cible=cible,
            niveau_id=niveau_pk,
            salle_id=salle_pk,
            annee=annee,
            creee_par=request.user,
        )
        messages.success(request, f"Collecte '{nom}' creee.")
        return redirect('liste_collectes')

    return render(request, 'finance/nouvelle_collecte.html', {
        'niveaux': niveaux,
        'salles': salles,
        'cibles': TypeCollecte.CIBLES,
        'annee': annee,
    })


# ── FRAIS ELEVES ──────────────────────────────────────────────────────────────

@login_required
@role_requis('DIRECTEUR', 'CENSEUR', 'COMPTABLE', 'SECRETAIRE')
def frais_eleve(request, eleve_pk):
    eleve = get_object_or_404(Eleve, pk=eleve_pk)
    annee = AnneeScolaire.active()
    frais = FraisEleve.objects.filter(
        eleve=eleve, annee=annee
    ).select_related('type_frais') if annee else []

    paiements = Paiement.objects.filter(
        eleve=eleve,
        frais__annee=annee,
    ).select_related('frais__type_frais', 'recu_par').order_by(
        '-created_at'
    ) if annee else []

    total_du = sum(float(f.montant) for f in frais)
    total_paye = sum(float(f.montant_paye) for f in frais)
    solde = total_du - total_paye

    return render(request, 'finance/frais_eleve.html', {
        'eleve': eleve,
        'frais': frais,
        'paiements': paiements,
        'total_du': total_du,
        'total_paye': total_paye,
        'solde': solde,
        'annee': annee,
    })


@login_required
@role_requis('DIRECTEUR', 'COMPTABLE')
def ajouter_frais(request, eleve_pk):
    eleve = get_object_or_404(Eleve, pk=eleve_pk)
    annee = AnneeScolaire.active()

    if request.method == 'POST':
        type_frais_pk = request.POST.get('type_frais_id')
        montant = float(request.POST.get('montant', 0))

        if not type_frais_pk or montant <= 0:
            messages.error(request, "Type de frais et montant obligatoires.")
            return redirect('frais_eleve', eleve_pk=eleve_pk)

        FraisEleve.objects.get_or_create(
            eleve=eleve,
            type_frais_id=type_frais_pk,
            annee=annee,
            defaults={'montant': montant}
        )
        messages.success(request, "Frais ajoute.")
    return redirect('frais_eleve', eleve_pk=eleve_pk)


# ── PAIEMENTS ─────────────────────────────────────────────────────────────────

@login_required
@role_requis('DIRECTEUR', 'CENSEUR', 'COMPTABLE')
def liste_paiements(request):
    annee = AnneeScolaire.active()
    user = request.user
    salle_f = request.GET.get('salle', '')
    date_f = request.GET.get('date', '')

    if user.role == 'COMPTABLE':
        paiements = Paiement.objects.filter(
            recu_par=user
        ).select_related('eleve', 'frais__type_frais', 'recu_par')
    else:
        paiements = Paiement.objects.all().select_related(
            'eleve', 'frais__type_frais', 'recu_par'
        )

    if salle_f:
        paiements = paiements.filter(
            eleve__inscriptions__salle__pk=salle_f,
            eleve__inscriptions__annee=annee,
        )
    if date_f:
        paiements = paiements.filter(date_paiement=date_f)

    paiements = paiements.order_by('-created_at')[:100]

    salles = SalleClasse.objects.filter(
        annee=annee, est_active=True
    ).order_by('niveau__ordre', 'nom') if annee else []

    return render(request, 'finance/liste_paiements.html', {
        'paiements': paiements,
        'salles': salles,
        'salle_filtre': salle_f,
        'date_filtre': date_f,
        'annee': annee,
    })


@login_required
@role_requis('DIRECTEUR', 'CENSEUR', 'COMPTABLE')
def nouveau_paiement(request):
    annee = AnneeScolaire.active()
    if not annee:
        messages.error(request, "Aucune annee active.")
        return redirect('dashboard_finance')

    salles = SalleClasse.objects.filter(
        annee=annee, est_active=True
    ).order_by('niveau__ordre', 'nom')

    if request.method == 'POST':
        eleve_pk = request.POST.get('eleve_id')
        frais_pk = request.POST.get('frais_id')
        montant = float(request.POST.get('montant', 0))
        moyen = request.POST.get('moyen', 'ESPECES')
        reference = request.POST.get('reference', '').strip()

        if not all([eleve_pk, frais_pk]) or montant <= 0:
            messages.error(
                request, "Eleve, frais et montant sont obligatoires."
            )
            return redirect('nouveau_paiement')

        frais = get_object_or_404(FraisEleve, pk=frais_pk)
        annee_str = str(timezone.now().year)
        numero_recu = generer_numero_recu(annee_str)

        paiement = Paiement.objects.create(
            eleve_id=eleve_pk,
            frais=frais,
            montant=montant,
            moyen=moyen,
            reference=reference,
            recu_par=request.user,
            numero_recu=numero_recu,
        )

        # Mettre a jour montant paye sur les frais
        frais.montant_paye = float(frais.montant_paye) + montant
        frais.save()

        # Notification directeur
        from apps.communication.models import Notification
        directeurs = CustomUser.objects.filter(
            role='DIRECTEUR', is_active=True
        )
        eleve = get_object_or_404(Eleve, pk=eleve_pk)
        for d in directeurs:
            Notification.creer(
                destinataire=d,
                titre=f"Paiement enregistre — {eleve.nom_complet}",
                message=(
                    f"{montant:,.0f} FCFA recu par "
                    f"{request.user.nom_complet} — {numero_recu}"
                ),
                type='SUCCES',
                lien=f'/finance/recu/{paiement.pk}/',
            )

        messages.success(
            request,
            f"Paiement enregistre — Recu N° {numero_recu}"
        )

        from django_q.tasks import async_task
        try:
            async_task('apps.communication.bots.bot_paiement_confirme', paiement)
        except Exception:
            pass

        return redirect('recu_paiement', pk=paiement.pk)

    return render(request, 'finance/nouveau_paiement.html', {
        'salles': salles,
        'moyens': Paiement.MOYENS,
        'annee': annee,
    })


@login_required
def recu_paiement(request, pk):
    paiement = get_object_or_404(Paiement, pk=pk)
    from apps.core.models import ConfigurationEcole
    config = ConfigurationEcole.get()
    return render(request, 'finance/recu_paiement.html', {
        'paiement': paiement,
        'config': config,
    })


@login_required
@role_requis('DIRECTEUR', 'CENSEUR', 'COMPTABLE')
def recu_pdf(request, pk):
    paiement = get_object_or_404(Paiement, pk=pk)
    from apps.core.models import ConfigurationEcole
    config = ConfigurationEcole.get()

    import io
    from reportlab.lib.pagesizes import A5
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.lib.enums import TA_CENTER, TA_LEFT

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A5,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
    )

    styles = getSampleStyleSheet()
    BLEU = colors.HexColor('#1E40AF')
    GRIS = colors.HexColor('#F1F5F9')

    elements = []

    titre_style = ParagraphStyle(
        'titre', parent=styles['Normal'],
        fontSize=14, fontName='Helvetica-Bold',
        textColor=BLEU, alignment=TA_CENTER,
    )
    normal = ParagraphStyle(
        'n', parent=styles['Normal'], fontSize=9,
    )
    centre = ParagraphStyle(
        'c', parent=styles['Normal'], fontSize=9,
        alignment=TA_CENTER,
    )
    bold = ParagraphStyle(
        'b', parent=styles['Normal'],
        fontSize=9, fontName='Helvetica-Bold',
    )

    elements.append(
        Paragraph(config.nom, titre_style)
    )
    elements.append(
        Paragraph(config.adresse or '', centre)
    )
    elements.append(Spacer(1, 0.3*cm))

    recu_table = Table(
        [[Paragraph(
            f"RECU DE PAIEMENT N° {paiement.numero_recu}",
            ParagraphStyle('r', parent=styles['Normal'],
                          fontSize=11, fontName='Helvetica-Bold',
                          textColor=colors.white, alignment=TA_CENTER)
        )]],
        colWidths=[13*cm]
    )
    recu_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), BLEU),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))
    elements.append(recu_table)
    elements.append(Spacer(1, 0.4*cm))

    data = [
        [Paragraph('Eleve :', bold),
         Paragraph(paiement.eleve.nom_complet, normal)],
        [Paragraph('Matricule :', bold),
         Paragraph(paiement.eleve.matricule, normal)],
        [Paragraph('Type de frais :', bold),
         Paragraph(paiement.frais.type_frais.nom, normal)],
        [Paragraph('Montant paye :', bold),
         Paragraph(
             f"{float(paiement.montant):,.0f} FCFA",
             ParagraphStyle('m', parent=styles['Normal'],
                           fontSize=11, fontName='Helvetica-Bold',
                           textColor=BLEU)
         )],
        [Paragraph('Moyen :', bold),
         Paragraph(paiement.get_moyen_display(), normal)],
        [Paragraph('Date :', bold),
         Paragraph(
             paiement.date_paiement.strftime('%d/%m/%Y'), normal
         )],
        [Paragraph('Recu par :', bold),
         Paragraph(paiement.recu_par.nom_complet, normal)],
    ]

    if paiement.reference:
        data.append([
            Paragraph('Reference :', bold),
            Paragraph(paiement.reference, normal),
        ])

    info_table = Table(data, colWidths=[4*cm, 9*cm])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), GRIS),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 0.3,
         colors.HexColor('#E2E8F0')),
        ('BACKGROUND', (0,3), (-1,3),
         colors.HexColor('#DBEAFE')),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 0.5*cm))

    sig_data = [[
        Paragraph("Le Comptable", centre),
        Paragraph("Le Directeur", centre),
    ]]
    sig_table = Table(sig_data, colWidths=[6.5*cm, 6.5*cm])
    sig_table.setStyle(TableStyle([
        ('TOPPADDING', (0,0), (-1,-1), 25),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('BOX', (0,0), (0,-1), 0.3, colors.grey),
        ('BOX', (1,0), (1,-1), 0.3, colors.grey),
    ]))
    elements.append(sig_table)

    doc.build(elements)
    buffer.seek(0)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="recu_{paiement.numero_recu}.pdf"'
    )
    response.write(buffer.getvalue())
    return response


# ── DEPENSES ──────────────────────────────────────────────────────────────────

@login_required
@role_requis('DIRECTEUR', 'CENSEUR', 'COMPTABLE')
def liste_depenses(request):
    user = request.user
    if user.role == 'COMPTABLE':
        depenses = Depense.objects.filter(
            enregistre_par=user
        ).order_by('-date')
    else:
        depenses = Depense.objects.all().select_related(
            'enregistre_par'
        ).order_by('-date')

    total = depenses.aggregate(t=Sum('montant'))['t'] or 0

    return render(request, 'finance/liste_depenses.html', {
        'depenses': depenses,
        'total': total,
        'types_depense': Depense.TYPES,
        'today': timezone.now().date().isoformat(),
    })


@login_required
@role_requis('DIRECTEUR', 'CENSEUR', 'COMPTABLE')
def nouvelle_depense(request):
    if request.method == 'POST':
        libelle = request.POST.get('libelle', '').strip()
        type_d = request.POST.get('type', 'AUTRE')
        montant = float(request.POST.get('montant', 0))
        date = request.POST.get('date')
        description = request.POST.get('description', '').strip()

        if not libelle or montant <= 0 or not date:
            messages.error(
                request, "Libelle, montant et date sont obligatoires."
            )
            return redirect('liste_depenses')

        Depense.objects.create(
            libelle=libelle,
            type=type_d,
            montant=montant,
            date=date,
            description=description,
            enregistre_par=request.user,
        )
        messages.success(request, f"Depense '{libelle}' enregistree.")
    return redirect('liste_depenses')


# ── ETAT RECOUVREMENT ─────────────────────────────────────────────────────────

@login_required
@role_requis('DIRECTEUR', 'CENSEUR', 'COMPTABLE')
def etat_recouvrement(request):
    annee = AnneeScolaire.active()
    salle_f = request.GET.get('salle', '')

    salles = SalleClasse.objects.filter(
        annee=annee, est_active=True
    ).order_by('niveau__ordre', 'nom') if annee else []

    rapport = []
    for salle in salles:
        if salle_f and str(salle.pk) != salle_f:
            continue

        inscrits = Inscription.objects.filter(
            salle=salle, annee=annee, statut='ACTIVE'
        ).select_related('eleve')

        debiteurs = []
        total_du_salle = 0
        total_paye_salle = 0

        for insc in inscrits:
            frais = FraisEleve.objects.filter(
                eleve=insc.eleve, annee=annee
            )
            du = float(frais.aggregate(t=Sum('montant'))['t'] or 0)
            paye = float(frais.aggregate(t=Sum('montant_paye'))['t'] or 0)
            solde = du - paye

            total_du_salle += du
            total_paye_salle += paye

            if solde > 0:
                debiteurs.append({
                    'eleve': insc.eleve,
                    'du': du,
                    'paye': paye,
                    'solde': solde,
                })

        taux = round(
            total_paye_salle / total_du_salle * 100, 1
        ) if total_du_salle > 0 else 0

        rapport.append({
            'salle': salle,
            'total_du': total_du_salle,
            'total_paye': total_paye_salle,
            'total_impaye': total_du_salle - total_paye_salle,
            'taux': taux,
            'debiteurs': debiteurs,
            'nb_debiteurs': len(debiteurs),
        })

    return render(request, 'finance/etat_recouvrement.html', {
        'rapport': rapport,
        'salles': salles,
        'salle_filtre': salle_f,
        'annee': annee,
    })


# ── API FRAIS PAR ELEVE (AJAX) ────────────────────────────────────────────────

@login_required
def api_frais_eleve(request):
    from django.http import JsonResponse
    eleve_pk = request.GET.get('eleve_id')
    annee = AnneeScolaire.active()
    if not eleve_pk or not annee:
        return JsonResponse({'frais': []})

    frais = FraisEleve.objects.filter(
        eleve_id=eleve_pk, annee=annee
    ).select_related('type_frais')

    data = [{
        'pk': f.pk,
        'nom': f.type_frais.nom,
        'montant': float(f.montant),
        'montant_paye': float(f.montant_paye),
        'solde': float(f.solde),
    } for f in frais]

    return JsonResponse({'frais': data})


# ── API ELEVES PAR SALLE (AJAX) ───────────────────────────────────────────────

@login_required
def api_eleves_salle(request):
    from django.http import JsonResponse
    annee = AnneeScolaire.active()
    salle_pk = request.GET.get('salle_id')
    if not salle_pk or not annee:
        return JsonResponse({'eleves': []})

    inscrits = Inscription.objects.filter(
        salle_id=salle_pk, annee=annee, statut='ACTIVE'
    ).select_related('eleve').order_by('eleve__nom')

    data = [{
        'pk': i.eleve.pk,
        'nom': i.eleve.nom_complet,
        'matricule': i.eleve.matricule,
    } for i in inscrits]

    return JsonResponse({'eleves': data})
