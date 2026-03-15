from django.db import models


class Evaluation(models.Model):
    TYPES = [
        ('DEVOIR', 'Devoir'), ('COMPOSITION', 'Composition'),
        ('INTERROGATION', 'Interrogation'), ('TP', 'TP'),
    ]
    STATUTS = [
        ('BROUILLON', 'Brouillon'),
        ('VALIDEE', 'Validée — prête pour saisie'),
        ('EN_SAISIE', 'En cours de saisie'),
        ('NOTES_SAISIES', 'Notes saisies — validation en attente'),
        ('VALIDEE_FINALE', 'Validée définitivement'),
        ('REJETEE', 'Rejetée'),
    ]
    matiere_salle = models.ForeignKey(
        'academic.MatiereSalle', on_delete=models.CASCADE, related_name='evaluations')
    periode = models.ForeignKey(
        'academic.Periode', on_delete=models.CASCADE, related_name='evaluations')
    titre = models.CharField(max_length=200)
    type = models.CharField(max_length=20, choices=TYPES, default='DEVOIR')
    date = models.DateField()
    note_sur = models.DecimalField(max_digits=5, decimal_places=2, default=20)
    statut = models.CharField(max_length=20, choices=STATUTS, default='BROUILLON')
    creee_par = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.SET_NULL,
        null=True, related_name='evaluations_creees')
    validee_par = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='evaluations_validees')
    commentaire_rejet = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Évaluation'
        ordering = ['-date']

    def __str__(self):
        return f"{self.titre} — {self.matiere_salle.salle.nom}"


class AutorisationSaisie(models.Model):
    evaluation = models.OneToOneField(
        Evaluation, on_delete=models.CASCADE, related_name='autorisation')
    autorise_par = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.SET_NULL,
        null=True, related_name='autorisations_donnees')
    saisie_par = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='autorisations_recues',
        help_text="Null = professeur de la matière")
    est_autorisee = models.BooleanField(default=True)
    notes_saisies = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def saisisseur_effectif(self):
        return self.saisie_par or self.evaluation.matiere_salle.professeur


class Note(models.Model):
    evaluation = models.ForeignKey(
        Evaluation, on_delete=models.CASCADE, related_name='notes')
    eleve = models.ForeignKey(
        'students.Eleve', on_delete=models.CASCADE, related_name='notes')
    valeur = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    est_absent = models.BooleanField(default=False)
    saisie_par = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.SET_NULL,
        null=True, related_name='notes_saisies')
    date_saisie = models.DateTimeField(auto_now_add=True)
    est_validee = models.BooleanField(default=False)

    class Meta:
        unique_together = ['evaluation', 'eleve']

    def save(self, *args, **kwargs):
        if self.pk:
            try:
                ancienne = Note.objects.get(pk=self.pk)
                if ancienne.valeur != self.valeur:
                    HistoriqueNote.objects.create(
                        note=self,
                        ancienne_valeur=ancienne.valeur,
                        nouvelle_valeur=self.valeur,
                    )
            except Note.DoesNotExist:
                pass
        super().save(*args, **kwargs)


class HistoriqueNote(models.Model):
    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name='historique')
    ancienne_valeur = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    nouvelle_valeur = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    modifie_par = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.SET_NULL, null=True)
    date_modification = models.DateTimeField(auto_now_add=True)
    raison = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['-date_modification']


class NoteComposition(models.Model):
    matiere_salle = models.ForeignKey(
        'academic.MatiereSalle', on_delete=models.CASCADE, related_name='notes_compo')
    periode = models.ForeignKey('academic.Periode', on_delete=models.CASCADE)
    eleve = models.ForeignKey('students.Eleve', on_delete=models.CASCADE)
    valeur = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    est_absent = models.BooleanField(default=False)
    saisie_par = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.SET_NULL, null=True)
    date_saisie = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['matiere_salle', 'periode', 'eleve']


class MoyenneMatiere(models.Model):
    eleve = models.ForeignKey('students.Eleve', on_delete=models.CASCADE)
    matiere_salle = models.ForeignKey('academic.MatiereSalle', on_delete=models.CASCADE)
    periode = models.ForeignKey('academic.Periode', on_delete=models.CASCADE)
    moyenne_classe = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    note_composition = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    moyenne_eleve = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    points = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    rang = models.IntegerField(null=True, blank=True)
    appreciation = models.CharField(max_length=50, blank=True)

    class Meta:
        unique_together = ['eleve', 'matiere_salle', 'periode']

    def save(self, *args, **kwargs):
        self.points = self.moyenne_eleve * self.matiere_salle.coefficient
        m = float(self.moyenne_eleve)
        if m >= 16:      self.appreciation = 'Très Bien'
        elif m >= 14:    self.appreciation = 'Bien'
        elif m >= 12:    self.appreciation = 'Assez Bien'
        elif m >= 10:    self.appreciation = 'Passable'
        elif m >= 8:     self.appreciation = 'Insuffisant'
        else:            self.appreciation = 'Très Insuffisant'
        super().save(*args, **kwargs)


class MoyenneGenerale(models.Model):
    DECISIONS = [
        ('ADMIS', 'Admis(e)'), ('EN_ATTENTE', 'En attente'),
        ('REDOUBLEMENT', 'Redoublement'), ('EXCLU', 'Exclu(e)'),
    ]
    eleve = models.ForeignKey('students.Eleve', on_delete=models.CASCADE)
    periode = models.ForeignKey('academic.Periode', on_delete=models.CASCADE)
    moyenne = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    rang = models.IntegerField(null=True, blank=True)
    effectif_classe = models.IntegerField(default=0)
    moy_la_plus_forte = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    moy_la_plus_faible = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    moy_de_la_classe = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    mention_travail = models.CharField(max_length=50, blank=True)
    tableau_honneur = models.BooleanField(default=False)
    assiduite = models.CharField(max_length=50, blank=True)
    conduite = models.CharField(max_length=50, blank=True)
    nb_absences = models.IntegerField(default=0)
    nb_retards = models.IntegerField(default=0)
    decision = models.CharField(max_length=15, choices=DECISIONS, default='EN_ATTENTE')
    decision_texte = models.CharField(max_length=200, blank=True)
    appreciation_conseil = models.TextField(blank=True)

    class Meta:
        unique_together = ['eleve', 'periode']

    @property
    def mention(self):
        m = float(self.moyenne)
        if m >= 16: return 'Très Bien'
        if m >= 14: return 'Bien'
        if m >= 12: return 'Assez Bien'
        if m >= 10: return 'Passable'
        if m >= 8:  return 'Insuffisant'
        return 'Très Insuffisant'


class Examen(models.Model):
    TYPES = [
        ('BLANC', 'Examen Blanc'),
        ('OFFICIEL', 'Examen Officiel'),
        ('BILAN', 'Bilan de fin de période'),
    ]
    CIBLES = [('NIVEAU', 'Tout le niveau'), ('SALLE', 'Salle spécifique')]
    STATUTS = [
        ('PREPARATION', 'En préparation'),
        ('EN_COURS', 'En cours'),
        ('NOTES_EN_SAISIE', 'Notes en saisie'),
        ('NOTES_SAISIES', 'Notes saisies — validation en attente'),
        ('VALIDE', 'Validé'),
    ]
    titre = models.CharField(max_length=200)
    type = models.CharField(max_length=20, choices=TYPES, default='BLANC')
    cible = models.CharField(max_length=10, choices=CIBLES, default='NIVEAU')
    niveau = models.ForeignKey(
        'academic.Niveau', on_delete=models.CASCADE,
        null=True, blank=True, related_name='examens')
    salle = models.ForeignKey(
        'academic.SalleClasse', on_delete=models.CASCADE,
        null=True, blank=True, related_name='examens')
    periode = models.ForeignKey(
        'academic.Periode', on_delete=models.CASCADE, related_name='examens')
    date_debut = models.DateField()
    date_fin = models.DateField(null=True, blank=True)
    statut = models.CharField(max_length=20, choices=STATUTS, default='PREPARATION')
    creee_par = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.SET_NULL,
        null=True, related_name='examens_crees')
    valide_par = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='examens_valides')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Examen'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.titre} — {self.periode}"

    @property
    def salles_concernees(self):
        annee = self.periode.annee
        if self.cible == 'NIVEAU' and self.niveau:
            return self.niveau.salles.filter(annee=annee, est_active=True)
        elif self.cible == 'SALLE' and self.salle:
            from apps.academic.models import SalleClasse
            return SalleClasse.objects.filter(pk=self.salle.pk)
        return []


class ExamenMatiere(models.Model):
    examen = models.ForeignKey(Examen, on_delete=models.CASCADE, related_name='matieres')
    matiere = models.ForeignKey('academic.Matiere', on_delete=models.CASCADE)
    coefficient = models.DecimalField(max_digits=4, decimal_places=1, default=1)
    note_sur = models.DecimalField(max_digits=5, decimal_places=2, default=20)
    saisie_par = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='examen_matieres_a_saisir')
    notes_saisies = models.BooleanField(default=False)

    class Meta:
        unique_together = ['examen', 'matiere']


class NoteExamen(models.Model):
    examen_matiere = models.ForeignKey(
        ExamenMatiere, on_delete=models.CASCADE, related_name='notes')
    eleve = models.ForeignKey('students.Eleve', on_delete=models.CASCADE)
    valeur = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    est_absent = models.BooleanField(default=False)
    saisie_par = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.SET_NULL, null=True)
    date_saisie = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['examen_matiere', 'eleve']