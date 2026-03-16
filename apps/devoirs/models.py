from django.db import models


class Devoir(models.Model):
    TYPES = [
        ('DEVOIR', 'Devoir a rendre'),
        ('EXERCICE', 'Exercice'),
        ('PROJET', 'Projet'),
        ('LECTURE', 'Lecture obligatoire'),
    ]
    STATUTS = [
        ('PUBLIE', 'Publie'),
        ('CLOS', 'Clos'),
        ('ARCHIVE', 'Archive'),
    ]
    matiere_salle = models.ForeignKey(
        'academic.MatiereSalle',
        on_delete=models.CASCADE,
        related_name='devoirs',
    )
    titre = models.CharField(max_length=200)
    type = models.CharField(max_length=15, choices=TYPES, default='DEVOIR')
    description = models.TextField()
    date_publication = models.DateField(auto_now_add=True)
    date_limite = models.DateField()
    note_sur = models.DecimalField(max_digits=5, decimal_places=2, default=20)
    statut = models.CharField(max_length=15, choices=STATUTS, default='PUBLIE')
    publie_par = models.ForeignKey(
        'authentication.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        related_name='devoirs_publies',
    )
    fichier_joint = models.FileField(
        upload_to='devoirs/sujets/',
        null=True, blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_limite']
        verbose_name = 'Devoir'

    def __str__(self):
        return f"{self.titre} — {self.matiere_salle.salle.nom}"

    @property
    def est_en_retard(self):
        from django.utils import timezone
        return timezone.now().date() > self.date_limite

    @property
    def nb_soumissions(self):
        return self.soumissions.count()

    @property
    def nb_inscrits(self):
        return self.matiere_salle.salle.inscriptions.filter(
            statut='ACTIVE'
        ).count()

    @property
    def taux_remise(self):
        if self.nb_inscrits == 0:
            return 0
        return round(self.nb_soumissions / self.nb_inscrits * 100)


class SoumissionDevoir(models.Model):
    STATUTS = [
        ('SOUMIS', 'Soumis'),
        ('CORRIGE', 'Corrige'),
        ('EN_RETARD', 'Soumis en retard'),
    ]
    devoir = models.ForeignKey(
        Devoir,
        on_delete=models.CASCADE,
        related_name='soumissions',
    )
    eleve = models.ForeignKey(
        'students.Eleve',
        on_delete=models.CASCADE,
        related_name='soumissions_devoirs',
    )
    contenu_texte = models.TextField(blank=True)
    fichier = models.FileField(
        upload_to='devoirs/soumissions/',
        null=True, blank=True,
    )
    statut = models.CharField(
        max_length=15, choices=STATUTS, default='SOUMIS'
    )
    note = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True,
    )
    commentaire_prof = models.TextField(blank=True)
    date_soumission = models.DateTimeField(auto_now_add=True)
    date_correction = models.DateTimeField(null=True, blank=True)
    corrige_par = models.ForeignKey(
        'authentication.CustomUser',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='corrections_devoirs',
    )

    class Meta:
        unique_together = ['devoir', 'eleve']
        ordering = ['-date_soumission']

    def __str__(self):
        return f"{self.eleve.nom_complet} — {self.devoir.titre}"
