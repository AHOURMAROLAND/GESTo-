from django.core.management.base import BaseCommand
from apps.core.backup import sauvegarde_automatique

class Command(BaseCommand):
    help = "Déclenche une sauvegarde automatique de la base de données et des fichiers media."

    def handle(self, *args, **options):
        self.stdout.write("Démarrage de la sauvegarde...")
        success = sauvegarde_automatique()
        if success:
            self.stdout.write(self.style.SUCCESS("Sauvegarde terminée avec succès."))
        else:
            self.stdout.write(self.style.ERROR("La sauvegarde a échoué. Consultez les logs."))
