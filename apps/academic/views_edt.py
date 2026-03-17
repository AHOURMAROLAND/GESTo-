from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from .models import (
    EmploiDuTemps, CreneauType, NiveauHoraire,
    SalleClasse, AnneeScolaire, MatiereSalle
)
from apps.authentication.models import CustomUser


def role_requis(*roles):
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            if not (request.user.is_superuser or request.user.role in roles):
                messages.error(request, "Accès refusé.")
                return redirect('dashboard')
            return view_func(request, *args, **kwargs)
        wrapper.__name__ = view_func.__name__
        return wrapper
    return decorator


JOURS = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi']
JOURS_COURTS = ['L', 'Ma', 'Me', 'J', 'V', 'S']


def _construire_grille(salle, annee):
    """
    Construit la grille EDT d'une salle.
    Retourne : creneaux (liste triée), grille (dict jour -> creneau -> EDT)
    """
    niveau_horaire = NiveauHoraire.objects.filter(
        niveau=salle.niveau, annee=annee
    ).first()

    if not niveau_horaire:
        return [], {}

    creneaux = CreneauType.objects.filter(
        niveau_horaire=niveau_horaire
    ).order_by('numero')

    # Récupérer tous les EDT de cette salle
    edts = EmploiDuTemps.objects.filter(
        salle=salle, annee=annee
    ).select_related(
        'creneau_type',
        'matiere_salle__matiere',
        'matiere_salle__professeur',
    )

    # Construire dict : grille[jour][creneau_id] = edt
    grille = {}
    for jour in range(6):
        grille[jour] = {}

    for edt in edts:
        grille[edt.jour][edt.creneau_type_id] = edt

    return creneaux, grille


@login_required
def vue_edt(request):
    """Vue principale EDT — adapte selon le rôle."""
    annee = AnneeScolaire.active()
    user = request.user

    salles = SalleClasse.objects.filter(
        annee=annee, est_active=True
    ).order_by('niveau__ordre', 'nom') if annee else []

    salle_pk = request.GET.get('salle', '')
    salle_selectionnee = None
    creneaux = []
    grille = {}

    # Restriction PROFESSEUR — filtre sur ses salles
    if user.role == 'PROFESSEUR':
        salles_prof = MatiereSalle.objects.filter(
            professeur=user, salle__annee=annee
        ).values_list('salle_id', flat=True)
        salles = salles.filter(pk__in=salles_prof)

    # Restriction ELEVE — sa salle uniquement
    if user.role == 'ELEVE':
        try:
            eleve = user.profil_eleve
            insc = eleve.inscription_active
            if insc:
                salle_pk = str(insc.salle_id)
                salles = salles.filter(pk=insc.salle_id)
        except Exception:
            salles = SalleClasse.objects.none()

    # Restriction PARENT — salles de ses enfants
    if user.role == 'PARENT':
        try:
            parent = user.profil_parent
            salles_enfants = [
                ep.eleve.inscription_active.salle_id
                for ep in parent.enfants.all()
                if ep.eleve.inscription_active
            ]
            salles = salles.filter(pk__in=salles_enfants)
        except Exception:
            salles = SalleClasse.objects.none()

    # Auto-sélection si une seule salle
    if not salle_pk and salles.count() == 1:
        salle_pk = str(salles.first().pk)

    if salle_pk:
        try:
            salle_selectionnee = SalleClasse.objects.get(pk=salle_pk)
            creneaux, grille = _construire_grille(salle_selectionnee, annee)
        except SalleClasse.DoesNotExist:
            pass

    # Vue professeur — son EDT personnel sur toutes ses salles
    mon_edt = []
    if user.role == 'PROFESSEUR':
        mes_edts = EmploiDuTemps.objects.filter(
            matiere_salle__professeur=user,
            annee=annee,
            est_libre=False,
        ).select_related(
            'creneau_type',
            'matiere_salle__matiere',
            'salle',
        ).order_by('jour', 'creneau_type__numero')

        for jour_idx, jour_nom in enumerate(JOURS):
            cours_jour = [
                e for e in mes_edts if e.jour == jour_idx
            ]
            if cours_jour:
                mon_edt.append({
                    'jour': jour_nom,
                    'cours': cours_jour,
                })

    peut_modifier = user.role in ('DIRECTEUR', 'CENSEUR')

    return render(request, 'academic/edt/vue_edt.html', {
        'salles': salles,
        'salle_selectionnee': salle_selectionnee,
        'creneaux': creneaux,
        'grille': grille,
        'jours': JOURS,
        'salle_pk': salle_pk,
        'mon_edt': mon_edt,
        'annee': annee,
        'peut_modifier': peut_modifier,
    })


@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def gestion_edt(request):
    """Interface de saisie/modification EDT."""
    annee = AnneeScolaire.active()

    salles = SalleClasse.objects.filter(
        annee=annee, est_active=True
    ).order_by('niveau__ordre', 'nom') if annee else []

    salle_pk = request.GET.get('salle', '')
    salle_selectionnee = None
    creneaux = []
    grille = {}
    matieres_salle = []

    if salle_pk:
        try:
            salle_selectionnee = SalleClasse.objects.get(pk=salle_pk)
            creneaux, grille = _construire_grille(salle_selectionnee, annee)
            matieres_salle = MatiereSalle.objects.filter(
                salle=salle_selectionnee
            ).select_related('matiere', 'professeur')
        except SalleClasse.DoesNotExist:
            pass

    return render(request, 'academic/edt/gestion_edt.html', {
        'salles': salles,
        'salle_selectionnee': salle_selectionnee,
        'creneaux': creneaux,
        'grille': grille,
        'jours': JOURS,
        'matieres_salle': matieres_salle,
        'salle_pk': salle_pk,
        'annee': annee,
    })


@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def assigner_creneau(request):
    """Assigne ou vide un créneau EDT via AJAX."""
    from django.http import JsonResponse

    if request.method != 'POST':
        return JsonResponse({'ok': False})

    salle_pk = request.POST.get('salle_id')
    creneau_pk = request.POST.get('creneau_id')
    jour = int(request.POST.get('jour', 0))
    matiere_salle_pk = request.POST.get('matiere_salle_id', '')
    annee = AnneeScolaire.active()

    if not all([salle_pk, creneau_pk, annee]):
        return JsonResponse({'ok': False, 'msg': 'Données manquantes'})

    edt, created = EmploiDuTemps.objects.get_or_create(
        salle_id=salle_pk,
        creneau_type_id=creneau_pk,
        jour=jour,
        annee=annee,
    )

    if matiere_salle_pk:
        edt.matiere_salle_id = matiere_salle_pk
        edt.est_libre = False
    else:
        edt.matiere_salle = None
        edt.est_libre = True

    edt.save()

    return JsonResponse({
        'ok': True,
        'matiere': edt.matiere_salle.matiere.nom if edt.matiere_salle else '',
        'prof': edt.matiere_salle.professeur.nom_complet
                if edt.matiere_salle and edt.matiere_salle.professeur else '',
    })


@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def modifier_slot_edt(request):
    """Alias/compatibilite pour assigner_creneau."""
    return assigner_creneau(request)


@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def publier_edt(request, salle_pk):
    """Publie (valide) l'EDT d'une salle."""
    from django.http import JsonResponse
    annee = AnneeScolaire.active()
    EmploiDuTemps.objects.filter(salle_id=salle_pk, annee=annee).update(statut='VALIDE')
    messages.success(request, "EDT publié avec succès.")
    return redirect(f'/emploi-du-temps/gestion/?salle={salle_pk}')


@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def reinitialiser_edt(request, salle_pk):
    """Réinitialise (vide) l'EDT d'une salle."""
    annee = AnneeScolaire.active()
    if request.method == 'POST':
        EmploiDuTemps.objects.filter(salle_id=salle_pk, annee=annee).update(
            matiere_salle=None, est_libre=True, statut='BROUILLON'
        )
        messages.success(request, "EDT réinitialisé.")
    return redirect(f'/emploi-du-temps/gestion/?salle={salle_pk}')


@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def disponibilites_prof(request, prof_pk):
    """Affiche et gère les disponibilités d'un professeur."""
    from apps.authentication.models import CustomUser
    from .models import DisponibiliteProf
    prof = get_object_or_404(CustomUser, pk=prof_pk, role='PROFESSEUR')
    annee = AnneeScolaire.active()
    disponibilites = DisponibiliteProf.objects.filter(professeur=prof, annee=annee)

    return render(request, 'academic/edt/disponibilites_prof.html', {
        'prof': prof,
        'disponibilites': disponibilites,
        'annee': annee,
    })


@login_required
def edt_professeur_detail(request, prof_pk):
    """Affiche le détail de l'EDT d'un professeur."""
    from apps.authentication.models import CustomUser
    prof = get_object_or_404(CustomUser, pk=prof_pk, role='PROFESSEUR')
    annee = AnneeScolaire.active()

    mes_edts = EmploiDuTemps.objects.filter(
        matiere_salle__professeur=prof,
        annee=annee,
        est_libre=False,
    ).select_related(
        'creneau_type',
        'matiere_salle__matiere',
        'salle',
    ).order_by('jour', 'creneau_type__numero')

    mon_edt = []
    for jour_idx, jour_nom in enumerate(JOURS):
        cours_jour = [e for e in mes_edts if e.jour == jour_idx]
        if cours_jour:
            mon_edt.append({'jour': jour_nom, 'cours': cours_jour})

    return render(request, 'academic/edt/edt_professeur.html', {
        'prof': prof,
        'mon_edt': mon_edt,
        'annee': annee,
    })


@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def initialiser_grille(request, salle_pk):
    """Crée les créneaux si NiveauHoraire existe."""
    if request.method != 'POST':
        return redirect('gestion_edt')

    annee = AnneeScolaire.active()
    salle = get_object_or_404(SalleClasse, pk=salle_pk)

    niveau_horaire = NiveauHoraire.objects.filter(
        niveau=salle.niveau, annee=annee
    ).first()

    if not niveau_horaire:
        # Créer un niveau horaire par défaut
        niveau_horaire = NiveauHoraire.objects.create(
            niveau=salle.niveau, annee=annee
        )

        # Créneaux standard : 7h-18h avec pauses
        creneaux_defaut = [
            (1, 'COURS', '07:00', '08:00', '0111110'),
            (2, 'COURS', '08:00', '09:00', '0111110'),
            (3, 'COURS', '09:00', '10:00', '0111110'),
            (4, 'PAUSE', '10:00', '10:15', '0111110'),
            (5, 'COURS', '10:15', '11:15', '0111110'),
            (6, 'COURS', '11:15', '12:15', '0111110'),
            (7, 'PAUSE', '12:15', '14:00', '0111110'),
            (8, 'COURS', '14:00', '15:00', '0111110'),
            (9, 'COURS', '15:00', '16:00', '0111110'),
            (10, 'PAUSE', '16:00', '16:15', '0111110'),
            (11, 'COURS', '16:15', '17:15', '0111110'),
        ]
        for num, type_c, hdeb, hfin, jours in creneaux_defaut:
            CreneauType.objects.get_or_create(
                niveau_horaire=niveau_horaire,
                numero=num,
                defaults={
                    'type': type_c,
                    'heure_debut': hdeb,
                    'heure_fin': hfin,
                    'jours_applicables': jours,
                }
            )

    messages.success(
        request,
        f"Grille initialisée pour {salle.nom}."
    )
    return redirect(f'/emploi-du-temps/gestion/?salle={salle_pk}')


@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def edt_pdf(request, salle_pk):
    """Export PDF de l'EDT d'une salle."""
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.lib.enums import TA_CENTER
    from apps.core.models import ConfigurationEcole
    import io

    annee = AnneeScolaire.active()
    salle = get_object_or_404(SalleClasse, pk=salle_pk)
    config = ConfigurationEcole.get()
    creneaux, grille = _construire_grille(salle, annee)

    BLEU = colors.HexColor('#1E3A8A')
    GRIS = colors.HexColor('#F8FAFC')

    buffer = io.BytesIO()
    styles = getSampleStyleSheet()

    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        leftMargin=1*cm, rightMargin=1*cm,
        topMargin=1.5*cm, bottomMargin=1*cm,
    )

    elements = []

    def s(name, **kw):
        return ParagraphStyle(name, parent=styles['Normal'], **kw)

    elements.append(Paragraph(
        f"{config.nom} — Emploi du temps : {salle.nom} — {annee.nom}",
        s('t', fontSize=12, fontName='Helvetica-Bold',
          textColor=BLEU, alignment=TA_CENTER, spaceAfter=8)
    ))

    # En-tête tableau
    jours_affiches = ['Horaire'] + JOURS[:5]
    col_widths = [3*cm] + [5*cm] * 5

    header = [
        Paragraph(f'<b>{j}</b>', s('h', fontSize=8,
                  fontName='Helvetica-Bold', textColor=colors.white,
                  alignment=TA_CENTER))
        for j in jours_affiches
    ]

    data = [header]

    for creneau in creneaux:
        horaire = (
            f"{creneau.heure_debut.strftime('%H:%M')}"
            f"–{creneau.heure_fin.strftime('%H:%M')}"
        )
        row = [
            Paragraph(
                f'<b>{horaire}</b>' if creneau.type == 'COURS'
                else f'<i>{horaire}</i>',
                s('hr', fontSize=7, alignment=TA_CENTER)
            )
        ]

        for jour_idx in range(5):
            edt = grille.get(jour_idx, {}).get(creneau.pk)
            if creneau.type == 'PAUSE':
                row.append(
                    Paragraph(
                        f'<i>{creneau.get_type_display()}</i>',
                        s('p', fontSize=7, textColor=colors.grey,
                          alignment=TA_CENTER)
                    )
                )
            elif edt and not edt.est_libre and edt.matiere_salle:
                prof = (
                    edt.matiere_salle.professeur.nom_complet
                    if edt.matiere_salle.professeur else ''
                )
                row.append(
                    Paragraph(
                        f'<b>{edt.matiere_salle.matiere.nom}</b><br/>'
                        f'<font size=6>{prof}</font>',
                        s('c', fontSize=7, alignment=TA_CENTER)
                    )
                )
            else:
                row.append(Paragraph('', s('e', fontSize=7)))

        data.append(row)

    table = Table(data, colWidths=col_widths, repeatRows=1)

    style_table = [
        ('BACKGROUND', (0,0), (-1,0), BLEU),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, GRIS]),
    ]

    # Colorier les pauses
    for i, creneau in enumerate(creneaux, 1):
        if creneau.type == 'PAUSE':
            style_table.append(
                ('BACKGROUND', (0,i), (-1,i), colors.HexColor('#FEF9C3'))
            )

    table.setStyle(TableStyle(style_table))
    elements.append(table)

    doc.build(elements)
    buffer.seek(0)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="edt_{salle.nom}.pdf"'
    )
    response.write(buffer.getvalue())
    return response

@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def liste_grilles(request):
    """Liste des grilles horaires par niveau."""
    annee = AnneeScolaire.active()
    grilles = NiveauHoraire.objects.filter(annee=annee).select_related('niveau')
    niveaux = Niveau.objects.all().order_by('ordre', 'nom')
    
    return render(request, 'academic/edt/liste_grilles.html', {
        'grilles': grilles,
        'niveaux': niveaux,
        'annee': annee,
    })


@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def creer_grille(request):
    """Crée une nouvelle grille pour un niveau."""
    annee = AnneeScolaire.active()
    if request.method == 'POST':
        niveau_id = request.POST.get('niveau_id')
        if niveau_id:
            niveau = get_object_or_404(Niveau, pk=niveau_id)
            grille, created = NiveauHoraire.objects.get_or_create(
                niveau=niveau, annee=annee
            )
            if created:
                messages.success(request, f"Grille créée pour le niveau {niveau.nom}")
            else:
                messages.info(request, f"La grille pour le niveau {niveau.nom} existe déjà.")
            return redirect('detail_grille', pk=grille.pk)
            
    return redirect('liste_grilles')


@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def detail_grille(request, pk):
    """Gère les créneaux d'une grille spécifique."""
    grille = get_object_or_404(NiveauHoraire, pk=pk)
    creneaux = grille.creneaux.all().order_by('numero')
    
    return render(request, 'academic/edt/detail_grille.html', {
        'grille': grille,
        'creneaux': creneaux,
    })


@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def ajouter_creneau(request, pk):
    """Ajoute un créneau à une grille."""
    grille = get_object_or_404(NiveauHoraire, pk=pk)
    if request.method == 'POST':
        numero = request.POST.get('numero')
        type_c = request.POST.get('type', 'COURS')
        h_debut = request.POST.get('heure_debut')
        h_fin = request.POST.get('heure_fin')
        jours = request.POST.getlist('jours')
        
        CreneauType.objects.create(
            niveau_horaire=grille,
            numero=numero,
            type=type_c,
            heure_debut=h_debut,
            heure_fin=h_fin,
            jours_applicables=",".join(jours)
        )
        messages.success(request, "Créneau ajouté.")
        
    return redirect('detail_grille', pk=pk)


@login_required
@role_requis('DIRECTEUR', 'CENSEUR')
def supprimer_creneau(request, pk):
    """Supprime un créneau."""
    creneau = get_object_or_404(CreneauType, pk=pk)
    grille_pk = creneau.niveau_horaire.pk
    if request.method == 'POST':
        creneau.delete()
        messages.success(request, "Créneau supprimé.")
    return redirect('detail_grille', pk=grille_pk)


@login_required
def edt_salle(request, pk):
    """Accès direct à l'EDT d'une salle spécifique."""
    return redirect(f"/emploi-du-temps/?salle={pk}")


@login_required
def edt_professeur(request):
    """Accès direct à l'EDT du professeur connecté."""
    return redirect('vue_edt')
