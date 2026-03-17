import os
import shutil
import json
from pathlib import Path
from django.conf import settings
from django.utils import timezone


def sauvegarde_automatique():
    """
    Sauvegarde quotidienne de la base de données et des media.
    Appele par django-q tous les jours a minuit.
    """
    try:
        from apps.core.models import SauvegardeAuto
        from apps.communication.models import Notification
        from apps.authentication.models import CustomUser

        today = timezone.now()
        backup_dir = Path(settings.BASE_DIR) / 'backups'
        backup_dir.mkdir(exist_ok=True)

        date_str = today.strftime('%Y%m%d_%H%M%S')

        # 1 — Sauvegarde SQLite
        db_path = settings.DATABASES['default']['NAME']
        backup_db = backup_dir / f"db_backup_{date_str}.sqlite3"

        if Path(db_path).exists():
            shutil.copy2(db_path, backup_db)
            taille_db = backup_db.stat().st_size / 1024 / 1024

        # 2 — Export JSON des données critiques
        backup_json = backup_dir / f"data_backup_{date_str}.json"
        _export_json(backup_json)

        # 3 — Nettoyer les anciennes sauvegardes (garder 7 jours)
        _nettoyer_vieilles_sauvegardes(backup_dir, jours=7)

        # 4 — Enregistrer dans SauvegardeAuto
        taille_totale = sum(
            f.stat().st_size for f in backup_dir.iterdir()
            if f.is_file()
        ) / 1024 / 1024

        sauvegarde = SauvegardeAuto.objects.create(
            type='AUTOMATIQUE',
            statut='SUCCES',
            fichier_db=str(backup_db.name),
            taille_mb=round(taille_totale, 2),
            notes=f"Sauvegarde automatique du {today.strftime('%d/%m/%Y %H:%M')}",
        )

        # 5 — Notifier le directeur
        directeurs = CustomUser.objects.filter(
            role='DIRECTEUR', is_active=True
        )
        for d in directeurs:
            Notification.creer(
                destinataire=d,
                titre='Sauvegarde automatique réussie',
                message=(
                    f"Sauvegarde du {today.strftime('%d/%m/%Y')} "
                    f"({taille_totale:.1f} Mo)"
                ),
                type='SUCCES',
                lien='/parametres/sauvegardes/',
            )

        print(f"[BACKUP] Sauvegarde réussie : {backup_db.name}")
        return True

    except Exception as e:
        print(f"[BACKUP] Erreur : {e}")
        try:
            SauvegardeAuto.objects.create(
                type='AUTOMATIQUE',
                statut='ECHEC',
                notes=str(e),
            )
        except Exception:
            pass
        return False


def _export_json(path):
    """Export JSON des tables critiques."""
    from apps.students.models import Eleve, Inscription
    from apps.grades.models import MoyenneGenerale
    from apps.finance.models import Paiement

    data = {
        'date': timezone.now().isoformat(),
        'nb_eleves': Eleve.objects.count(),
        'nb_inscriptions': Inscription.objects.count(),
        'nb_paiements': Paiement.objects.count(),
        'nb_moyennes': MoyenneGenerale.objects.count(),
    }

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _nettoyer_vieilles_sauvegardes(backup_dir, jours=7):
    """Supprime les sauvegardes plus vieilles que N jours."""
    limite = timezone.now().timestamp() - (jours * 86400)
    for fichier in backup_dir.iterdir():
        if fichier.is_file() and fichier.stat().st_mtime < limite:
            fichier.unlink()
            print(f"[BACKUP] Supprimé : {fichier.name}")


def sauvegarde_manuelle(user=None):
    """Sauvegarde manuelle declenchee depuis l'interface."""
    return sauvegarde_automatique()


def lister_sauvegardes():
    """Liste les fichiers de sauvegarde disponibles."""
    backup_dir = Path(settings.BASE_DIR) / 'backups'
    if not backup_dir.exists():
        return []

    fichiers = []
    for f in sorted(backup_dir.iterdir(), reverse=True):
        if f.is_file() and f.suffix in ['.sqlite3', '.json']:
            fichiers.append({
                'nom': f.name,
                'taille': round(f.stat().st_size / 1024 / 1024, 2),
                'date': timezone.datetime.fromtimestamp(
                    f.stat().st_mtime
                ).strftime('%d/%m/%Y %H:%M'),
                'type': 'Base de données' if f.suffix == '.sqlite3' else 'JSON',
                'chemin': str(f),
            })
    return fichiers