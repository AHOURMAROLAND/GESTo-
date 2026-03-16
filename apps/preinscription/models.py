from django.db import models


class PreInscription(models.Model):
    STATUTS = [
        ('EN_ATTENTE', 'En attente de validation'),
        ('VALIDEE', 'Validee — compte cree'),
        ('REJETEE', 'Rejetee'),
    ]
    SEXES = [('M', 'Masculin'), ('F', 'Feminin')]

    # Infos eleve
    nom_eleve = models.CharField(max_length=100)
    prenom_eleve = models.CharField(max_length=100)
    sexe_eleve = models.CharField(max_length=1, choices=SEXES)
    date_naissance = models.DateField(null=True, blank=True)
    lieu_naissance = models.CharField(max_length=100, blank=True)
    niveau_souhaite = models.CharField(max_length=50)
    est_redoublant = models.BooleanField(default=False)
    ancienne_ecole = models.CharField(max_length=200, blank=True)

    # Infos parent/tuteur
    nom_parent = models.CharField(max_length=100)
    prenom_parent = models.CharField(max_length=100, blank=True)
    telephone_parent = models.CharField(max_length=20)
    telephone_wa_parent = models.CharField(max_length=20, blank=True)
    email_parent = models.EmailField(blank=True)
    profession_parent = models.CharField(max_length=100, blank=True)
    adresse_parent = models.CharField(max_length=200, blank=True)
    lien_parent = models.CharField(
        max_length=10,
        choices=[
            ('PERE', 'Pere'), ('MERE', 'Mere'),
            ('TUTEUR', 'Tuteur legal'), ('AUTRE', 'Autre'),
        ],
        default='TUTEUR',
    )

    # Suivi
    statut = models.CharField(
        max_length=15, choices=STATUTS, default='EN_ATTENTE'
    )
    reference = models.CharField(max_length=20, unique=True, blank=True)
    date_soumission = models.DateTimeField(auto_now_add=True)
    traitee_par = models.ForeignKey(
        'authentication.CustomUser',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='preinscriptions_traitees',
    )
    date_traitement = models.DateTimeField(null=True, blank=True)
    commentaire = models.TextField(blank=True)

    # Lien vers le compte cree
    eleve_cree = models.ForeignKey(
        'students.Eleve',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='preinscription',
    )

    class Meta:
        ordering = ['-date_soumission']
        verbose_name = 'Pre-inscription'

    def __str__(self):
        return f"{self.nom_eleve} {self.prenom_eleve} ({self.reference})"

    def save(self, *args, **kwargs):
        if not self.reference:
            from django.utils import timezone
            import random
            self.reference = (
                f"PI-{timezone.now().strftime('%Y%m')}"
                f"-{random.randint(1000, 9999)}"
            )
        super().save(*args, **kwargs)
