from django.db import models


class ConfigurationDocument(models.Model):
    nom_ecole = models.CharField(max_length=200, default='GESTo')
    slogan = models.CharField(max_length=200, blank=True)
    adresse = models.CharField(max_length=300, blank=True)
    telephone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    site_web = models.CharField(max_length=100, blank=True)
    logo = models.ImageField(upload_to='documents/logos/', null=True, blank=True)
    signature_directeur = models.ImageField(
        upload_to='documents/signatures/', null=True, blank=True)
    cachet = models.ImageField(upload_to='documents/cachets/', null=True, blank=True)
    pied_page = models.CharField(max_length=300, blank=True)
    ministre_tutelle = models.CharField(max_length=200, blank=True)
    devise_nationale = models.CharField(
        max_length=100, blank=True, default='Travail – Liberté – Patrie')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuration document'

    def __str__(self): return self.nom_ecole

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class CertificatScolarite(models.Model):
    eleve = models.ForeignKey(
        'students.Eleve', on_delete=models.CASCADE, related_name='certificats')
    annee = models.ForeignKey('academic.AnneeScolaire', on_delete=models.CASCADE)
    numero = models.CharField(max_length=30, unique=True)
    delivre_par = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.SET_NULL, null=True)
    date_delivrance = models.DateField(auto_now_add=True)
    motif = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['-date_delivrance']

    def save(self, *args, **kwargs):
        if not self.numero:
            from django.utils import timezone
            self.numero = f"CERT{timezone.now().strftime('%Y%m%d%H%M%S')}"
        super().save(*args, **kwargs)