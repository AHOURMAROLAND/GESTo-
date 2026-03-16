from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from .models import MoyenneGenerale, MoyenneMatiere, NoteComposition
from .calculs import calculer_moyennes_salle, calculer_toutes_salles
from apps.academic.models import (
    AnneeScolaire, Periode, SalleClasse, Niveau, GroupeMatiere
)
from apps.students.models import Eleve, Inscription


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
@role_requis('DIRECTEUR', 'CENSEUR', 'SECRETAIRE')
def gestion_bulletins(request):
    annee = AnneeScolaire.active()
    periodes = Periode.objects.filter(
        annee=annee
    ).order_by('numero') if annee else []
    niveaux = Niveau.objects.all().order_by('ordre', 'nom')
    salles = SalleClasse.objects.filter(
        annee=annee, est_active=True
    ).order_by('niveau__ordre', 'nom') if annee else []

    return render(request, 'grades/bulletins/gestion_bulletins.html', {
        'annee': annee,
        'periodes': periodes,
        'niveaux': niveaux,
        'salles': salles,
    })


@login_required
@role_requis('DIRECTEUR', 'CENSEUR', 'SECRETAIRE')
def calculer_moyennes(request):
    if request.method == 'POST':
        periode_pk = request.POST.get('periode_id')
        salle_pk = request.POST.get('salle_id') or None
        tout = request.POST.get('tout') == '1'

        periode = get_object_or_404(Periode, pk=periode_pk)

        if tout:
            nb = calculer_toutes_salles(periode)
            messages.success(
                request,
                f"Moyennes calculees pour {nb} salle(s) — {periode}."
            )
        elif salle_pk:
            salle = get_object_or_404(SalleClasse, pk=salle_pk)
            calculer_moyennes_salle(salle, periode)
            messages.success(
                request,
                f"Moyennes calculees pour {salle.nom} — {periode}."
            )
        else:
            messages.error(request, "Choisissez une salle ou toutes.")

    return redirect('gestion_bulletins')


@login_required
@role_requis('DIRECTEUR', 'CENSEUR', 'SECRETAIRE')
def liste_bulletins_salle(request, salle_pk, periode_pk):
    salle = get_object_or_404(SalleClasse, pk=salle_pk)
    periode = get_object_or_404(Periode, pk=periode_pk)

    moyennes = MoyenneGenerale.objects.filter(
        periode=periode,
        eleve__inscriptions__salle=salle,
        eleve__inscriptions__annee=periode.annee,
        eleve__inscriptions__statut='ACTIVE',
    ).select_related('eleve').order_by('rang')

    return render(request, 'grades/bulletins/liste_bulletins_salle.html', {
        'salle': salle,
        'periode': periode,
        'moyennes': moyennes,
    })


@login_required
def apercu_bulletin(request, eleve_pk, periode_pk):
    eleve = get_object_or_404(Eleve, pk=eleve_pk)
    periode = get_object_or_404(Periode, pk=periode_pk)

    try:
        moy_gen = MoyenneGenerale.objects.get(eleve=eleve, periode=periode)
    except MoyenneGenerale.DoesNotExist:
        messages.error(
            request,
            "Aucune moyenne calculee pour cet eleve. "
            "Lancez d'abord le calcul des moyennes."
        )
        return redirect('gestion_bulletins')

    inscription = eleve.inscriptions.filter(
        annee=periode.annee, statut='ACTIVE'
    ).select_related('salle__niveau').first()

    if not inscription:
        messages.error(request, "Eleve non inscrit pour cette annee.")
        return redirect('gestion_bulletins')

    salle = inscription.salle
    groupes = GroupeMatiere.objects.filter(
        niveau=salle.niveau
    ).order_by('ordre').prefetch_related('groupematiere_set')

    # Moyennes par groupe
    donnees_groupes = []
    for groupe in groupes:
        matieres_moy = MoyenneMatiere.objects.filter(
            eleve=eleve,
            periode=periode,
            matiere_salle__groupe=groupe,
            matiere_salle__salle=salle,
        ).select_related(
            'matiere_salle__matiere', 'matiere_salle'
        ).order_by('matiere_salle__groupe__ordre', '-matiere_salle__coefficient')

        if matieres_moy.exists():
            donnees_groupes.append({
                'groupe': groupe,
                'matieres': matieres_moy,
            })

    # Matieres sans groupe
    matieres_sans_groupe = MoyenneMatiere.objects.filter(
        eleve=eleve,
        periode=periode,
        matiere_salle__groupe__isnull=True,
        matiere_salle__salle=salle,
    ).select_related('matiere_salle__matiere', 'matiere_salle')

    from apps.core.models import ConfigurationEcole
    config = ConfigurationEcole.get()
    parents = eleve.parents.select_related('parent').all()

    return render(request, 'grades/bulletins/apercu_bulletin.html', {
        'eleve': eleve,
        'periode': periode,
        'moy_gen': moy_gen,
        'salle': salle,
        'donnees_groupes': donnees_groupes,
        'matieres_sans_groupe': matieres_sans_groupe,
        'config': config,
        'parents': parents,
    })


@login_required
@role_requis('DIRECTEUR', 'CENSEUR', 'SECRETAIRE')
def generer_bulletin_pdf(request, eleve_pk, periode_pk):
    eleve = get_object_or_404(Eleve, pk=eleve_pk)
    periode = get_object_or_404(Periode, pk=periode_pk)

    try:
        moy_gen = MoyenneGenerale.objects.get(eleve=eleve, periode=periode)
    except MoyenneGenerale.DoesNotExist:
        messages.error(request, "Calculez les moyennes d'abord.")
        return redirect('gestion_bulletins')

    inscription = eleve.inscriptions.filter(
        annee=periode.annee, statut='ACTIVE'
    ).select_related('salle__niveau').first()

    if not inscription:
        messages.error(request, "Eleve non inscrit.")
        return redirect('gestion_bulletins')

    salle = inscription.salle

    from apps.core.models import ConfigurationEcole
    config = ConfigurationEcole.get()

    groupes = GroupeMatiere.objects.filter(
        niveau=salle.niveau
    ).order_by('ordre')

    donnees_groupes = []
    for groupe in groupes:
        matieres_moy = MoyenneMatiere.objects.filter(
            eleve=eleve, periode=periode,
            matiere_salle__groupe=groupe,
            matiere_salle__salle=salle,
        ).select_related(
            'matiere_salle__matiere', 'matiere_salle'
        ).order_by('-matiere_salle__coefficient')
        if matieres_moy.exists():
            donnees_groupes.append({
                'groupe': groupe,
                'matieres': matieres_moy,
            })

    matieres_sans_groupe = MoyenneMatiere.objects.filter(
        eleve=eleve, periode=periode,
        matiere_salle__groupe__isnull=True,
        matiere_salle__salle=salle,
    ).select_related('matiere_salle__matiere', 'matiere_salle')

    buffer = _generer_pdf_bulletin(
        eleve, periode, moy_gen, salle, config,
        donnees_groupes, matieres_sans_groupe
    )

    response = HttpResponse(content_type='application/pdf')
    nom = f"bulletin_{eleve.matricule}_{periode.libelle_court}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{nom}"'
    response.write(buffer)
    return response


@login_required
@role_requis('DIRECTEUR', 'CENSEUR', 'SECRETAIRE')
def generer_bulletins_salle_pdf(request, salle_pk, periode_pk):
    salle = get_object_or_404(SalleClasse, pk=salle_pk)
    periode = get_object_or_404(Periode, pk=periode_pk)

    from apps.core.models import ConfigurationEcole
    config = ConfigurationEcole.get()
    groupes = GroupeMatiere.objects.filter(
        niveau=salle.niveau
    ).order_by('ordre')

    inscrits = Inscription.objects.filter(
        salle=salle, annee=periode.annee, statut='ACTIVE'
    ).select_related('eleve').order_by('eleve__nom')

    import io
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Spacer
    from reportlab.lib.units import cm

    buffer_total = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer_total, pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
    )

    all_elements = []
    for i, insc in enumerate(inscrits):
        eleve = insc.eleve
        try:
            moy_gen = MoyenneGenerale.objects.get(
                eleve=eleve, periode=periode
            )
        except MoyenneGenerale.DoesNotExist:
            continue

        donnees_groupes = []
        for groupe in groupes:
            matieres_moy = MoyenneMatiere.objects.filter(
                eleve=eleve, periode=periode,
                matiere_salle__groupe=groupe,
                matiere_salle__salle=salle,
            ).select_related('matiere_salle__matiere', 'matiere_salle')
            if matieres_moy.exists():
                donnees_groupes.append({
                    'groupe': groupe, 'matieres': matieres_moy,
                })

        matieres_sg = MoyenneMatiere.objects.filter(
            eleve=eleve, periode=periode,
            matiere_salle__groupe__isnull=True,
            matiere_salle__salle=salle,
        ).select_related('matiere_salle__matiere', 'matiere_salle')

        elements = _elements_bulletin(
            eleve, periode, moy_gen, salle, config,
            donnees_groupes, matieres_sg
        )
        all_elements.extend(elements)

        if i < inscrits.count() - 1:
            from reportlab.platypus import PageBreak
            all_elements.append(PageBreak())

    if all_elements:
        doc.build(all_elements)
        buffer_total.seek(0)
        response = HttpResponse(content_type='application/pdf')
        nom = f"bulletins_{salle.nom}_{periode.libelle_court}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{nom}"'
        response.write(buffer_total.getvalue())
        return response
    else:
        messages.error(request, "Aucune moyenne calculee for this salle.")
        return redirect('liste_bulletins_salle', salle_pk=salle_pk,
                        periode_pk=periode_pk)


def _generer_pdf_bulletin(
    eleve, periode, moy_gen, salle, config,
    donnees_groupes, matieres_sans_groupe
):
    import io
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate
    from reportlab.lib.units import cm

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
    )
    elements = _elements_bulletin(
        eleve, periode, moy_gen, salle, config,
        donnees_groupes, matieres_sans_groupe
    )
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


def _elements_bulletin(
    eleve, periode, moy_gen, salle, config,
    donnees_groupes, matieres_sans_groupe
):
    from reportlab.platypus import (
        Paragraph, Spacer, Table, TableStyle
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

    styles = getSampleStyleSheet()
    elements = []

    BLEU = colors.HexColor('#1E40AF')
    GRIS_CLAIR = colors.HexColor('#F1F5F9')
    GRIS = colors.HexColor('#64748B')
    NOIR = colors.black
    BLANC = colors.white

    titre_style = ParagraphStyle(
        'titre', parent=styles['Normal'],
        fontSize=9, textColor=GRIS,
        alignment=TA_CENTER,
    )
    ecole_style = ParagraphStyle(
        'ecole', parent=styles['Normal'],
        fontSize=12, fontName='Helvetica-Bold',
        textColor=BLEU, alignment=TA_CENTER,
    )
    bold_style = ParagraphStyle(
        'bold', parent=styles['Normal'],
        fontSize=9, fontName='Helvetica-Bold',
    )
    normal_style = ParagraphStyle(
        'normal_s', parent=styles['Normal'],
        fontSize=8,
    )
    centre_style = ParagraphStyle(
        'centre', parent=styles['Normal'],
        fontSize=8, alignment=TA_CENTER,
    )

    # En-tete
    entete_data = [
        [
            Paragraph(f"Republique Togolaise<br/>{config.devise}", titre_style),
            Paragraph(f"<b>{config.nom}</b>", ecole_style),
            Paragraph(f"{config.ministre_tutelle}<br/>Direction regionale", titre_style),
        ]
    ]
    entete_table = Table(entete_data, colWidths=[5*cm, 8*cm, 5*cm])
    entete_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(entete_table)
    elements.append(Spacer(1, 0.3*cm))

    # Titre bulletin
    titre_bulletin = Table(
        [[Paragraph(
            f"BULLETIN DE NOTES — {periode}",
            ParagraphStyle('tb', parent=styles['Normal'],
                          fontSize=13, fontName='Helvetica-Bold',
                          textColor=BLANC, alignment=TA_CENTER)
        )]],
        colWidths=[18*cm]
    )
    titre_bulletin.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), BLEU),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('ROUNDEDCORNERS', [4]),
    ]))
    elements.append(titre_bulletin)
    elements.append(Spacer(1, 0.3*cm))

    # Infos eleve
    parents_str = ', '.join([
        ep.parent.nom_complet
        for ep in eleve.parents.select_related('parent').all()
    ]) or 'Non renseigne'

    info_data = [
        [
            Paragraph(f"<b>Nom et Prenoms :</b> {eleve.nom_complet}", bold_style),
            Paragraph(f"<b>Matricule :</b> {eleve.matricule}", bold_style),
        ],
        [
            Paragraph(f"<b>Classe :</b> {salle.nom} — {salle.niveau.nom}", bold_style),
            Paragraph(f"<b>Annee :</b> {periode.annee.nom}", bold_style),
        ],
        [
            Paragraph(f"<b>Parent/Tuteur :</b> {parents_str}", bold_style),
            Paragraph(
                f"<b>Effectif :</b> {moy_gen.effectif_classe} eleve(s)",
                bold_style
            ),
        ],
    ]
    info_table = Table(info_data, colWidths=[11*cm, 7*cm])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), GRIS_CLAIR),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#E2E8F0')),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 0.3*cm))

    # Tableau notes
    header = [
        Paragraph('<b>Matieres</b>', bold_style),
        Paragraph('<b>Coeff</b>', centre_style),
        Paragraph('<b>Moy.Classe</b>', centre_style),
        Paragraph('<b>Compo</b>', centre_style),
        Paragraph('<b>Moy.Trim</b>', centre_style),
        Paragraph('<b>Points</b>', centre_style),
        Paragraph('<b>Appreciation</b>', centre_style),
    ]

    table_data = [header]

    def ligne_matiere(mm):
        moy = float(mm.moyenne_eleve)
        if moy >= 10:
            couleur = colors.HexColor('#166534')
        elif moy >= 8:
            couleur = colors.HexColor('#854D0E')
        else:
            couleur = colors.HexColor('#991B1B')

        return [
            Paragraph(mm.matiere_salle.matiere.nom, normal_style),
            Paragraph(str(mm.matiere_salle.coefficient), centre_style),
            Paragraph(f"{mm.moyenne_classe:.2f}", centre_style),
            Paragraph(
                f"{mm.note_composition:.2f}" if mm.note_composition else "—",
                centre_style
            ),
            Paragraph(
                f"{mm.moyenne_eleve:.2f}",
                ParagraphStyle('note', parent=styles['Normal'],
                              fontSize=9, fontName='Helvetica-Bold',
                              alignment=TA_CENTER,
                              textColor=couleur)
            ),
            Paragraph(f"{mm.points:.2f}", centre_style),
            Paragraph(mm.appreciation, normal_style),
        ]

    for gd in donnees_groupes:
        # Ligne groupe
        table_data.append([
            Paragraph(
                f"<b>{gd['groupe'].nom.upper()}</b>",
                ParagraphStyle('grp', parent=styles['Normal'],
                              fontSize=8, fontName='Helvetica-Bold',
                              textColor=BLANC)
            ),
            '', '', '', '', '', '',
        ])
        for mm in gd['matieres']:
            table_data.append(ligne_matiere(mm))

    for mm in matieres_sans_groupe:
        table_data.append(ligne_matiere(mm))

    col_widths = [6.5*cm, 1.2*cm, 1.8*cm, 1.5*cm, 1.8*cm, 1.5*cm, 3.7*cm]
    notes_table = Table(table_data, colWidths=col_widths)

    ts = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), BLEU),
        ('TEXTCOLOR', (0,0), (-1,0), BLANC),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('ALIGN', (1,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (0,-1), 8),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [BLANC, GRIS_CLAIR]),
    ])

    # Couleur lignes groupe
    for i, row in enumerate(table_data):
        if i > 0 and isinstance(row[0], Paragraph):
            if hasattr(row[0], 'text') and row[0].text and 'HELVETICA-BOLD' in str(row[0].style.fontName).upper():
                ts.add('BACKGROUND', (0,i), (-1,i), colors.HexColor('#334155'))
                ts.add('SPAN', (0,i), (-1,i))

    notes_table.setStyle(ts)
    elements.append(notes_table)
    elements.append(Spacer(1, 0.3*cm))

    # Recapitulatif
    moy = float(moy_gen.moyenne)
    if moy >= 10:
        couleur_moy = colors.HexColor('#166534')
    elif moy >= 8:
        couleur_moy = colors.HexColor('#854D0E')
    else:
        couleur_moy = colors.HexColor('#991B1B')

    recap_data = [
        [
            Paragraph(
                f"<b>Moyenne generale : {moy_gen.moyenne:.2f}/20</b>",
                ParagraphStyle('moy', parent=styles['Normal'],
                              fontSize=11, fontName='Helvetica-Bold',
                              textColor=couleur_moy)
            ),
            Paragraph(
                f"<b>Rang : {moy_gen.rang}/{moy_gen.effectif_classe}</b>",
                bold_style
            ),
            Paragraph(f"<b>Mention : {moy_gen.mention}</b>", bold_style),
        ],
        [
            Paragraph(
                f"Moy. classe : {moy_gen.moy_de_la_classe:.2f} | "
                f"+ forte : {moy_gen.moy_la_plus_forte:.2f} | "
                f"+ faible : {moy_gen.moy_la_plus_faible:.2f}",
                normal_style
            ),
            Paragraph(
                f"Absences : {moy_gen.nb_absences} | "
                f"Retards : {moy_gen.nb_retards}",
                normal_style
            ),
            Paragraph(
                'Tableau honneur' if moy_gen.tableau_honneur else '',
                ParagraphStyle('th', parent=styles['Normal'],
                              fontSize=8, textColor=colors.HexColor('#166534'),
                              fontName='Helvetica-Bold')
            ),
        ],
    ]

    recap_table = Table(recap_data, colWidths=[8*cm, 5*cm, 5*cm])
    recap_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), GRIS_CLAIR),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#E2E8F0')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    elements.append(recap_table)
    elements.append(Spacer(1, 0.3*cm))

    # Appreciation conseil
    if moy_gen.appreciation_conseil or moy_gen.decision_texte:
        appr_data = [[
            Paragraph(
                f"<b>Appreciation du conseil de classe :</b> "
                f"{moy_gen.appreciation_conseil or moy_gen.decision_texte}",
                normal_style
            )
        ]]
        appr_table = Table(appr_data, colWidths=[18*cm])
        appr_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), GRIS_CLAIR),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('BOX', (0,0), (-1,-1), 0.5, BLEU),
        ]))
        elements.append(appr_table)
        elements.append(Spacer(1, 0.3*cm))

    # Signatures
    sig_data = [[
        Paragraph("Le Titulaire de classe", centre_style),
        Paragraph("Le Directeur", centre_style),
        Paragraph("Signature parent/tuteur", centre_style),
    ]]
    sig_table = Table(sig_data, colWidths=[6*cm, 6*cm, 6*cm])
    sig_table.setStyle(TableStyle([
        ('TOPPADDING', (0,0), (-1,-1), 20),
        ('BOTTOMPADDING', (0,0), (-1,-1), 20),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('BOX', (0,0), (0,-1), 0.3, GRIS),
        ('BOX', (1,0), (1,-1), 0.3, GRIS),
        ('BOX', (2,0), (2,-1), 0.3, GRIS),
    ]))
    elements.append(sig_table)

    return elements
