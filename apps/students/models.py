from django.db import models


class Eleve(models.Model):
    SEXES = [('M', 'Masculin'), ('F', 'Féminin')]
    STATUTS = [
        ('INSCRIT', 'Inscrit'), ('ACTIF', 'Actif'),
        ('SUSPENDU', 'Suspendu'), ('EXCLU', 'Exclu'), ('TRANSFERE', 'Transféré'),
    ]
    user = models.OneToOneField(
        'authentication.CustomUser', on_delete=models.CASCADE,
        related_name='profil_eleve', null=True, blank=True)
    matricule = models.CharField(max_length=30, unique=True)
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    sexe = models.CharField(max_length=1, choices=SEXES)
    date_naissance = models.DateField(null=True, blank=True)
    lieu_naissance = models.CharField(max_length=100, blank=True)
    photo = models.ImageField(upload_to='photos/eleves/', null=True, blank=True)
    statut = models.CharField(max_length=20, choices=STATUTS, default='INSCRIT')
    redoublant = models.BooleanField(default=False)
    contact_urgence = models.CharField(max_length=100, blank=True)
    telephone_urgence = models.CharField(max_length=20, blank=True)
    groupe_sanguin = models.CharField(max_length=5, blank=True)
    allergies = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Élève'
        ordering = ['nom', 'prenom']

    def __str__(self):
        return f"{self.nom} {self.prenom} ({self.matricule})"

    @property
    def nom_complet(self):
        return f"{self.nom} {self.prenom}"

    @property
    def inscription_active(self):
        return self.inscriptions.filter(statut='ACTIVE').first()

    @property
    def salle_active(self):
        insc = self.inscription_active
        return insc.salle if insc else None


class Parent(models.Model):
    LIENS = [
        ('PERE', 'Père'), ('MERE', 'Mère'),
        ('TUTEUR', 'Tuteur légal'), ('AUTRE', 'Autre'),
    ]
    user = models.OneToOneField(
        'authentication.CustomUser', on_delete=models.CASCADE,
        related_name='profil_parent', null=True, blank=True)
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100, blank=True)
    telephone = models.CharField(max_length=20, blank=True)
    telephone2 = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    profession = models.CharField(max_length=100, blank=True)
    adresse = models.CharField(max_length=200, blank=True)
    langue = models.CharField(
        max_length=5,
        choices=[('FR', 'Français'), ('EW', 'Ewe'), ('KA', 'Kabyè')],
        default='FR')

    class Meta:
        verbose_name = 'Parent/Tuteur'

    def __str__(self):
        return f"{self.nom} {self.prenom}"

    @property
    def nom_complet(self):
        return f"{self.nom} {self.prenom}"

    @property
    def tous_les_enfants(self):
        return [ep.eleve for ep in self.enfants.select_related('eleve').all()]


class EleveParent(models.Model):
    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE, related_name='parents')
    parent = models.ForeignKey(Parent, on_delete=models.CASCADE, related_name='enfants')
    lien = models.CharField(max_length=10, choices=Parent.LIENS, default='TUTEUR')
    est_contact_principal = models.BooleanField(default=False)

    class Meta:
        unique_together = ['eleve', 'parent']

    def __str__(self):
        return f"{self.parent} → {self.eleve} ({self.get_lien_display()})"


class Inscription(models.Model):
    STATUTS = [
        ('ACTIVE', 'Active'), ('TRANSFEREE', 'Transférée'),
        ('ANNULEE', 'Annulée'), ('TERMINEE', 'Terminée'),
    ]
    eleve = models.ForeignKey(
        Eleve, on_delete=models.CASCADE, related_name='inscriptions')
    salle = models.ForeignKey(
        'academic.SalleClasse', on_delete=models.CASCADE, related_name='inscriptions')
    annee = models.ForeignKey(
        'academic.AnneeScolaire', on_delete=models.CASCADE, related_name='inscriptions')
    statut = models.CharField(max_length=15, choices=STATUTS, default='ACTIVE')
    date_inscription = models.DateField(auto_now_add=True)
    numero_ordre = models.IntegerField(null=True, blank=True)

    class Meta:
        unique_together = ['eleve', 'annee']
        ordering = ['salle__nom', 'eleve__nom']

    def __str__(self):
        return f"{self.eleve} → {self.salle} ({self.annee})"