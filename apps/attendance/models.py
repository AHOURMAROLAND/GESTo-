from django.db import models


class SeancePointage(models.Model):
    STATUTS = [
        ('EN_COURS', 'En cours'),
        ('SOUMIS', 'Soumis'),
        ('VERROUILLE', 'Verrouillé — 10min dépassées'),
    ]
    matiere_salle = models.ForeignKey(
        'academic.MatiereSalle', on_delete=models.CASCADE,
        related_name='seances_pointage')
    creneau = models.ForeignKey(
        'academic.CreneauType', on_delete=models.SET_NULL, null=True, blank=True)
    date = models.DateField()
    jour = models.CharField(max_length=10, blank=True)
    statut = models.CharField(max_length=15, choices=STATUTS, default='EN_COURS')
    soumis_par = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.SET_NULL,
        null=True, related_name='seances_soumises')
    date_soumission = models.DateTimeField(null=True, blank=True)
    date_verrou = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['matiere_salle', 'date', 'creneau']
        ordering = ['-date']

    def __str__(self):
        return f"Séance {self.matiere_salle} — {self.date}"

    @property
    def est_modifiable_par_prof(self):
        if self.statut == 'VERROUILLE':
            return False
        if self.statut == 'SOUMIS' and self.date_soumission:
            from django.utils import timezone
            delta = timezone.now() - self.date_soumission
            return delta.total_seconds() < 600
        return self.statut == 'EN_COURS'


class Presence(models.Model):
    STATUTS = [
        ('PRESENT', 'Présent'),
        ('ABSENT', 'Absent'),
        ('RETARD', 'En retard'),
        ('ABSENT_JUSTIFIE', 'Absent justifié'),
        ('RETARD_JUSTIFIE', 'Retard justifié'),
    ]
    eleve = models.ForeignKey(
        'students.Eleve', on_delete=models.CASCADE, related_name='presences')
    seance = models.ForeignKey(
        SeancePointage, on_delete=models.CASCADE, related_name='presences')
    statut = models.CharField(max_length=20, choices=STATUTS, default='PRESENT')
    heure_arrivee = models.TimeField(null=True, blank=True)
    motif = models.CharField(max_length=200, blank=True)
    est_justifiee = models.BooleanField(default=False)
    pointe_par = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.SET_NULL,
        null=True, related_name='pointages')
    date_pointage = models.DateTimeField(auto_now_add=True)
    modifie_par_surveillant = models.BooleanField(default=False)

    class Meta:
        unique_together = ['eleve', 'seance']
        ordering = ['eleve__nom']