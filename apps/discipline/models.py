from django.db import models


class TypeSanction(models.Model):
    nom = models.CharField(max_length=100)
    gravite = models.IntegerField(
        choices=[(1, 'Légère'), (2, 'Moyenne'), (3, 'Grave')], default=1)
    description = models.CharField(max_length=200, blank=True)

    def __str__(self): return self.nom


class Sanction(models.Model):
    STATUTS = [
        ('EN_ATTENTE', 'En attente'), ('APPROUVEE', 'Approuvée'),
        ('REJETEE', 'Rejetée'), ('LEVEE', 'Levée'),
    ]
    eleve = models.ForeignKey(
        'students.Eleve', on_delete=models.CASCADE, related_name='sanctions')
    type_sanction = models.ForeignKey(TypeSanction, on_delete=models.CASCADE)
    motif = models.TextField()
    date_faits = models.DateField()
    statut = models.CharField(max_length=15, choices=STATUTS, default='EN_ATTENTE')
    signale_par = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.SET_NULL,
        null=True, related_name='sanctions_signalees')
    approuve_par = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='sanctions_approuvees')
    commentaire = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class DemandeExclusion(models.Model):
    STATUTS = [
        ('EN_ATTENTE', 'En attente du directeur'),
        ('APPROUVEE', 'Approuvée'),
        ('REJETEE', 'Rejetée'),
    ]
    eleve = models.ForeignKey(
        'students.Eleve', on_delete=models.CASCADE, related_name='exclusions')
    motif = models.TextField()
    statut = models.CharField(max_length=15, choices=STATUTS, default='EN_ATTENTE')
    demandee_par = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.SET_NULL,
        null=True, related_name='exclusions_demandees')
    traitee_par = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='exclusions_traitees')
    commentaire_directeur = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    traitee_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']