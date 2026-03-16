from django.test import TestCase
from django.utils import timezone
from apps.authentication.models import CustomUser
from apps.academic.models import (
    AnneeScolaire, Niveau, SalleClasse, Matiere, MatiereSalle
)
from apps.students.models import Eleve, Inscription
from apps.attendance.models import SeancePointage, Presence


class PresenceTestCase(TestCase):

    def setUp(self):
        self.annee = AnneeScolaire.objects.create(
            nom='2025-2026', est_active=True
        )
        self.niveau = Niveau.objects.create(nom='6eme')
        self.salle = SalleClasse.objects.create(
            niveau=self.niveau, annee=self.annee, nom='6eme1'
        )
        self.matiere = Matiere.objects.create(nom='Maths')
        self.prof = CustomUser.objects.create_user(
            username='prof_att', password='test1234', role='PROFESSEUR'
        )
        self.ms = MatiereSalle.objects.create(
            salle=self.salle, matiere=self.matiere,
            professeur=self.prof, coefficient=3
        )
        user_eleve = CustomUser.objects.create_user(
            username='eleve_att', password='test1234', role='ELEVE'
        )
        self.eleve = Eleve.objects.create(
            user=user_eleve,
            matricule='BKT-2025-0020',
            nom='KPODO', prenom='Kofi', sexe='M',
        )
        Inscription.objects.create(
            eleve=self.eleve, salle=self.salle,
            annee=self.annee, statut='ACTIVE'
        )

    def test_seance_modifiable_en_cours(self):
        """Seance EN_COURS est modifiable."""
        seance = SeancePointage.objects.create(
            matiere_salle=self.ms,
            date=timezone.now().date(),
            statut='EN_COURS',
        )
        self.assertTrue(seance.est_modifiable_par_prof)

    def test_seance_verrouillee_non_modifiable(self):
        """Seance VERROUILLEE n'est pas modifiable."""
        seance = SeancePointage.objects.create(
            matiere_salle=self.ms,
            date=timezone.now().date(),
            statut='VERROUILLE',
        )
        self.assertFalse(seance.est_modifiable_par_prof)

    def test_seance_soumise_modifiable_dans_10min(self):
        """Seance SOUMISE depuis moins de 10 min est modifiable."""
        seance = SeancePointage.objects.create(
            matiere_salle=self.ms,
            date=timezone.now().date(),
            statut='SOUMIS',
            date_soumission=timezone.now() - timezone.timedelta(minutes=5),
        )
        self.assertTrue(seance.est_modifiable_par_prof)

    def test_seance_soumise_non_modifiable_apres_10min(self):
        """Seance SOUMISE depuis plus de 10 min n'est plus modifiable."""
        seance = SeancePointage.objects.create(
            matiere_salle=self.ms,
            date=timezone.now().date(),
            statut='SOUMIS',
            date_soumission=timezone.now() - timezone.timedelta(minutes=11),
        )
        self.assertFalse(seance.est_modifiable_par_prof)

    def test_presence_statuts(self):
        """Tous les statuts de presence sont valides."""
        seance = SeancePointage.objects.create(
            matiere_salle=self.ms,
            date=timezone.now().date(),
            statut='EN_COURS',
        )
        statuts_valides = [
            'PRESENT', 'ABSENT', 'RETARD',
            'ABSENT_JUSTIFIE', 'RETARD_JUSTIFIE'
        ]
        for statut in statuts_valides:
            p = Presence.objects.create(
                eleve=self.eleve,
                seance=seance,
                statut=statut,
                pointe_par=self.prof,
            )
            self.assertEqual(p.statut, statut)
            p.delete()

    def test_presence_unique_par_seance_eleve(self):
        """Un eleve ne peut etre pointe qu'une fois par seance."""
        from django.db import IntegrityError
        seance = SeancePointage.objects.create(
            matiere_salle=self.ms,
            date=timezone.now().date(),
            statut='EN_COURS',
        )
        Presence.objects.create(
            eleve=self.eleve, seance=seance,
            statut='PRESENT', pointe_par=self.prof
        )
        with self.assertRaises(IntegrityError):
            Presence.objects.create(
                eleve=self.eleve, seance=seance,
                statut='ABSENT', pointe_par=self.prof
            )
