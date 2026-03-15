from django.db import models


class AnneeScolaire(models.Model):
    nom = models.CharField(max_length=20, unique=True)
    date_debut = models.DateField(null=True, blank=True)
    date_fin = models.DateField(null=True, blank=True)
    est_active = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Année scolaire'
        ordering = ['-nom']

    def __str__(self):
        return self.nom

    def save(self, *args, **kwargs):
        if self.est_active:
            AnneeScolaire.objects.exclude(pk=self.pk).update(est_active=False)
        super().save(*args, **kwargs)

    @classmethod
    def active(cls):
        return cls.objects.filter(est_active=True).first()


class Periode(models.Model):
    TYPES = [('TRIMESTRE', 'Trimestre'), ('SEMESTRE', 'Semestre')]
    annee = models.ForeignKey(
        AnneeScolaire, on_delete=models.CASCADE, related_name='periodes')
    type = models.CharField(max_length=10, choices=TYPES, default='TRIMESTRE')
    numero = models.IntegerField()
    date_debut = models.DateField(null=True, blank=True)
    date_fin = models.DateField(null=True, blank=True)
    est_active = models.BooleanField(default=False)

    class Meta:
        unique_together = ['annee', 'type', 'numero']
        ordering = ['numero']

    def __str__(self):
        label = 'Trimestre' if self.type == 'TRIMESTRE' else 'Semestre'
        return f"{label} {self.numero} — {self.annee.nom}"

    @property
    def libelle_court(self):
        return f"{'T' if self.type == 'TRIMESTRE' else 'S'}{self.numero}"

    @property
    def est_dernier(self):
        return (self.type == 'TRIMESTRE' and self.numero == 3) or \
               (self.type == 'SEMESTRE' and self.numero == 2)

    def save(self, *args, **kwargs):
        if self.est_active:
            Periode.objects.filter(annee=self.annee).exclude(
                pk=self.pk).update(est_active=False)
        super().save(*args, **kwargs)

    @classmethod
    def active(cls, annee=None):
        qs = cls.objects.filter(est_active=True)
        if annee:
            qs = qs.filter(annee=annee)
        return qs.first()


class Niveau(models.Model):
    SYSTEMES = [('TRIMESTRIEL', 'Trimestriel'), ('SEMESTRIEL', 'Semestriel')]
    TYPES_ECOLE = [('PRIVE', 'Privé'), ('PUBLIC', 'Public')]
    nom = models.CharField(max_length=50, unique=True)
    ordre = models.IntegerField(default=0)
    description = models.CharField(max_length=200, blank=True)
    systeme = models.CharField(max_length=15, choices=SYSTEMES, default='TRIMESTRIEL')
    type_ecole = models.CharField(max_length=10, choices=TYPES_ECOLE, default='PRIVE')

    class Meta:
        verbose_name = 'Niveau'
        verbose_name_plural = 'Niveaux'
        ordering = ['ordre', 'nom']

    def __str__(self):
        return self.nom

    @property
    def nb_periodes(self):
        return 3 if self.systeme == 'TRIMESTRIEL' else 2


class GroupeMatiere(models.Model):
    TYPES = [
        ('SCIENTIFIQUE', 'Scientifiques'),
        ('LITTERAIRE', 'Littéraires'),
        ('FACULTATIF', 'Facultatives'),
        ('AUTRE', 'Autre'),
    ]
    niveau = models.ForeignKey(
        Niveau, on_delete=models.CASCADE, related_name='groupes_matieres')
    nom = models.CharField(max_length=100)
    type = models.CharField(max_length=15, choices=TYPES, default='AUTRE')
    ordre = models.IntegerField(default=0)
    est_obligatoire = models.BooleanField(default=True)

    class Meta:
        unique_together = ['niveau', 'nom']
        ordering = ['ordre']

    def __str__(self):
        return f"{self.nom} ({self.niveau.nom})"


class SalleClasse(models.Model):
    niveau = models.ForeignKey(
        Niveau, on_delete=models.CASCADE, related_name='salles')
    annee = models.ForeignKey(
        AnneeScolaire, on_delete=models.CASCADE, related_name='salles')
    nom = models.CharField(max_length=50)
    capacite = models.IntegerField(default=40)
    titulaire = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='salles_titulaire',
        limit_choices_to={'role': 'PROFESSEUR'})
    batiment = models.CharField(max_length=50, blank=True)
    est_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Salle de classe'
        verbose_name_plural = 'Salles de classe'
        unique_together = ['niveau', 'annee', 'nom']
        ordering = ['niveau__ordre', 'nom']

    def __str__(self):
        return f"{self.nom} ({self.annee.nom})"

    @property
    def effectif(self):
        return self.inscriptions.filter(statut='ACTIVE').count()

    @property
    def systeme(self):
        return self.niveau.systeme


class Matiere(models.Model):
    nom = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, blank=True)

    class Meta:
        verbose_name = 'Matière'
        ordering = ['nom']

    def __str__(self):
        return self.nom


class MatiereSalle(models.Model):
    salle = models.ForeignKey(
        SalleClasse, on_delete=models.CASCADE, related_name='matieres')
    matiere = models.ForeignKey(Matiere, on_delete=models.CASCADE)
    groupe = models.ForeignKey(
        GroupeMatiere, on_delete=models.SET_NULL, null=True, blank=True)
    professeur = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='matieres_enseignees',
        limit_choices_to={'role': 'PROFESSEUR'})
    coefficient = models.DecimalField(max_digits=4, decimal_places=1, default=1)
    heures_semaine = models.DecimalField(max_digits=4, decimal_places=1, default=2)
    est_facultative = models.BooleanField(default=False)

    class Meta:
        unique_together = ['salle', 'matiere']
        ordering = ['groupe__ordre', '-coefficient', 'matiere__nom']

    def __str__(self):
        prof = self.professeur.nom_complet if self.professeur else 'Non assigné'
        return f"{self.matiere.nom} — {self.salle.nom} ({prof})"


class NiveauHoraire(models.Model):
    niveau = models.ForeignKey(
        Niveau, on_delete=models.CASCADE, related_name='grilles_horaires')
    annee = models.ForeignKey(AnneeScolaire, on_delete=models.CASCADE)

    class Meta:
        unique_together = ['niveau', 'annee']

    def __str__(self):
        return f"Grille {self.niveau.nom} — {self.annee.nom}"


class CreneauType(models.Model):
    TYPES = [('COURS', 'Cours'), ('PAUSE', 'Pause'), ('RECREATION', 'Récréation')]
    niveau_horaire = models.ForeignKey(
        NiveauHoraire, on_delete=models.CASCADE, related_name='creneaux')
    numero = models.IntegerField()
    type = models.CharField(max_length=15, choices=TYPES, default='COURS')
    heure_debut = models.TimeField()
    heure_fin = models.TimeField()
    jours_applicables = models.CharField(
        max_length=100, default='LUNDI,MARDI,MERCREDI,JEUDI,VENDREDI')

    class Meta:
        unique_together = ['niveau_horaire', 'numero']
        ordering = ['numero']

    def __str__(self):
        return f"H{self.numero} {self.heure_debut:%H:%M}-{self.heure_fin:%H:%M}"

    @property
    def jours_list(self):
        return [j.strip() for j in self.jours_applicables.split(',') if j.strip()]

    @property
    def duree_minutes(self):
        from datetime import datetime
        d = datetime.combine(datetime.today(), self.heure_debut)
        f = datetime.combine(datetime.today(), self.heure_fin)
        return int((f - d).seconds / 60)


class DisponibiliteProf(models.Model):
    JOURS = [
        ('LUNDI', 'Lundi'), ('MARDI', 'Mardi'), ('MERCREDI', 'Mercredi'),
        ('JEUDI', 'Jeudi'), ('VENDREDI', 'Vendredi'), ('SAMEDI', 'Samedi'),
    ]
    professeur = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.CASCADE,
        related_name='disponibilites')
    annee = models.ForeignKey(AnneeScolaire, on_delete=models.CASCADE)
    jour = models.CharField(max_length=10, choices=JOURS)
    heure_debut = models.TimeField()
    heure_fin = models.TimeField()

    class Meta:
        ordering = ['jour', 'heure_debut']

    def __str__(self):
        return f"{self.professeur.nom_complet} {self.jour} {self.heure_debut:%H:%M}-{self.heure_fin:%H:%M}"


class EmploiDuTemps(models.Model):
    JOURS = [
        ('LUNDI', 'Lundi'), ('MARDI', 'Mardi'), ('MERCREDI', 'Mercredi'),
        ('JEUDI', 'Jeudi'), ('VENDREDI', 'Vendredi'), ('SAMEDI', 'Samedi'),
    ]
    STATUTS = [('BROUILLON', 'Brouillon'), ('VALIDE', 'Validé et publié')]
    salle = models.ForeignKey(
        SalleClasse, on_delete=models.CASCADE, related_name='emplois_du_temps')
    creneau_type = models.ForeignKey(CreneauType, on_delete=models.CASCADE)
    jour = models.CharField(max_length=10, choices=JOURS)
    matiere_salle = models.ForeignKey(
        MatiereSalle, on_delete=models.SET_NULL, null=True, blank=True)
    est_libre = models.BooleanField(default=False)
    statut = models.CharField(max_length=15, choices=STATUTS, default='BROUILLON')
    annee = models.ForeignKey(AnneeScolaire, on_delete=models.CASCADE)
    contrainte_violee = models.BooleanField(default=False)
    note_contrainte = models.CharField(max_length=200, blank=True)

    class Meta:
        unique_together = ['salle', 'creneau_type', 'jour', 'annee']
        verbose_name = 'Emploi du temps'

    def __str__(self):
        return f"{self.salle.nom} — {self.jour} H{self.creneau_type.numero}"