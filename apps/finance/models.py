from django.db import models


class TypeFrais(models.Model):
    nom = models.CharField(max_length=100)
    description = models.CharField(max_length=200, blank=True)
    est_obligatoire = models.BooleanField(default=True)

    def __str__(self): return self.nom


class TarifNiveau(models.Model):
    niveau = models.ForeignKey('academic.Niveau', on_delete=models.CASCADE)
    annee = models.ForeignKey('academic.AnneeScolaire', on_delete=models.CASCADE)
    frais_inscription = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    frais_scolarite = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    frais_examen = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        unique_together = ['niveau', 'annee']

    @property
    def total(self):
        return self.frais_inscription + self.frais_scolarite + self.frais_examen


class TypeCollecte(models.Model):
    CIBLES = [('TOUS', 'Tous'), ('NIVEAU', 'Par niveau'), ('SALLE', 'Par salle')]
    nom = models.CharField(max_length=100)
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True)
    cible = models.CharField(max_length=10, choices=CIBLES, default='TOUS')
    niveau = models.ForeignKey(
        'academic.Niveau', on_delete=models.SET_NULL, null=True, blank=True)
    salle = models.ForeignKey(
        'academic.SalleClasse', on_delete=models.SET_NULL, null=True, blank=True)
    annee = models.ForeignKey('academic.AnneeScolaire', on_delete=models.CASCADE)
    est_active = models.BooleanField(default=True)
    creee_par = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self): return f"{self.nom} — {self.montant} FCFA"


class FraisEleve(models.Model):
    eleve = models.ForeignKey(
        'students.Eleve', on_delete=models.CASCADE, related_name='frais')
    type_frais = models.ForeignKey(TypeFrais, on_delete=models.CASCADE)
    annee = models.ForeignKey('academic.AnneeScolaire', on_delete=models.CASCADE)
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    montant_paye = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['eleve', 'type_frais', 'annee']

    @property
    def solde(self): return self.montant - self.montant_paye


class Paiement(models.Model):
    MOYENS = [
        ('ESPECES', 'Espèces'), ('VIREMENT', 'Virement'),
        ('MOBILE_MONEY', 'Mobile Money'), ('CHEQUE', 'Chèque'),
    ]
    eleve = models.ForeignKey(
        'students.Eleve', on_delete=models.CASCADE, related_name='paiements')
    frais = models.ForeignKey(
        FraisEleve, on_delete=models.CASCADE, related_name='paiements')
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    moyen = models.CharField(max_length=20, choices=MOYENS, default='ESPECES')
    reference = models.CharField(max_length=50, blank=True)
    date_paiement = models.DateField(auto_now_add=True)
    recu_par = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.SET_NULL, null=True)
    numero_recu = models.CharField(max_length=30, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.numero_recu:
            from django.utils import timezone
            self.numero_recu = f"REC{timezone.now().strftime('%Y%m%d%H%M%S')}"
        super().save(*args, **kwargs)


class Depense(models.Model):
    TYPES = [
        ('SALAIRE', 'Salaire'), ('FOURNITURE', 'Fourniture'),
        ('ENTRETIEN', 'Entretien'), ('EQUIPEMENT', 'Équipement'), ('AUTRE', 'Autre'),
    ]
    libelle = models.CharField(max_length=200)
    type = models.CharField(max_length=20, choices=TYPES, default='AUTRE')
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField()
    description = models.TextField(blank=True)
    enregistre_par = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self): return f"{self.libelle} — {self.montant} FCFA"