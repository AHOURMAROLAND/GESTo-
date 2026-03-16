from django.db import models


class Message(models.Model):
    expediteur = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.CASCADE,
        related_name='messages_envoyes')
    destinataire = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.CASCADE,
        related_name='messages_recus')
    sujet = models.CharField(max_length=200)
    contenu = models.TextField()
    est_lu = models.BooleanField(default=False)
    date_lecture = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    en_reponse_a = models.ForeignKey(
        'self', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reponses')

    class Meta:
        ordering = ['-created_at']


class Communique(models.Model):
    CIBLES = [
        ('TOUS', 'Tout le monde'), ('PROFESSEURS', 'Professeurs'),
        ('PARENTS', 'Parents'), ('ELEVES', 'Élèves'), ('PERSONNEL', 'Personnel'),
    ]
    expediteur = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.CASCADE)
    sujet = models.CharField(max_length=200)
    contenu = models.TextField()
    cible = models.CharField(max_length=15, choices=CIBLES, default='TOUS')
    created_at = models.DateTimeField(auto_now_add=True)


class Notification(models.Model):
    TYPES = [
        ('INFO', 'Information'), ('SUCCES', 'Succès'),
        ('ALERTE', 'Alerte'), ('AVERTISSEMENT', 'Avertissement'),
    ]
    destinataire = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.CASCADE,
        related_name='notifications')
    type = models.CharField(max_length=15, choices=TYPES, default='INFO')
    titre = models.CharField(max_length=200)
    message = models.TextField()
    lien = models.CharField(max_length=200, blank=True)
    est_lue = models.BooleanField(default=False)
    wa_envoye = models.BooleanField(default=False)
    push_envoye = models.BooleanField(default=False)
    email_envoye = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    @classmethod
    def creer(cls, destinataire, titre, message, type='INFO', lien=''):
        return cls.objects.create(
            destinataire=destinataire, titre=titre,
            message=message, type=type, lien=lien)


class LogBot(models.Model):
    """Historique de tous les messages bots envoyés — anti-spam."""
    code_bot = models.CharField(max_length=10)
    destinataire = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.CASCADE,
        related_name='logs_bots')
    canal = models.CharField(
        max_length=10,
        choices=[('WA', 'WhatsApp'), ('PUSH', 'Push'), ('EMAIL', 'Email')])
    statut = models.CharField(
        max_length=10,
        choices=[('ENVOYE', 'Envoyé'), ('ECHEC', 'Échec'), ('SKIP', 'Anti-spam')])
    message = models.TextField(blank=True)
    erreur = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class EvenementCalendrier(models.Model):
    TYPES = [
        ('FERIE', 'Jour ferie'),
        ('VACANCES', 'Vacances'),
        ('EXAMEN', 'Examen'),
        ('REUNION', 'Reunion'),
        ('EVENEMENT', 'Evenement scolaire'),
        ('AUTRE', 'Autre'),
    ]
    titre = models.CharField(max_length=200)
    type = models.CharField(max_length=15, choices=TYPES, default='EVENEMENT')
    date_debut = models.DateField()
    date_fin = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)
    concerne_tous = models.BooleanField(default=True)
    annee = models.ForeignKey(
        'academic.AnneeScolaire',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='evenements',
    )
    creee_par = models.ForeignKey(
        'authentication.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date_debut']
        verbose_name = 'Evenement calendrier'

    def __str__(self):
        return f"{self.titre} — {self.date_debut}"

    @property
    def est_passe(self):
        from django.utils import timezone
        return self.date_debut < timezone.now().date()

    @property
    def date_fin_effective(self):
        return self.date_fin or self.date_debut


class ReunionParent(models.Model):
    STATUTS = [
        ('PLANIFIEE', 'Planifiee'),
        ('EN_COURS', 'En cours'),
        ('TERMINEE', 'Terminee'),
        ('ANNULEE', 'Annulee'),
    ]
    titre = models.CharField(max_length=200)
    date = models.DateField()
    heure = models.TimeField()
    lieu = models.CharField(max_length=200, default='Salle de conference')
    description = models.TextField(blank=True)
    statut = models.CharField(
        max_length=15, choices=STATUTS, default='PLANIFIEE'
    )
    organisee_par = models.ForeignKey(
        'authentication.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        related_name='reunions_organisees',
    )
    annee = models.ForeignKey(
        'academic.AnneeScolaire',
        on_delete=models.CASCADE,
        null=True, blank=True,
    )
    nb_convocations_envoyees = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']
        verbose_name = 'Reunion parents'

    def __str__(self):
        return f"{self.titre} — {self.date}"