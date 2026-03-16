from django.test import TestCase
from django.utils import timezone
from apps.authentication.models import CustomUser
from apps.academic.models import (
    AnneeScolaire, Periode, Niveau, SalleClasse,
    Matiere, MatiereSalle
)
from apps.students.models import Eleve, Inscription
from apps.grades.models import (
    Evaluation, AutorisationSaisie, Note,
    MoyenneMatiere, MoyenneGenerale
)


class EvaluationTestCase(TestCase):

    def setUp(self):
        self.annee = AnneeScolaire.objects.create(
            nom='2025-2026', est_active=True
        )
        self.periode = Periode.objects.create(
            annee=self.annee, type='TRIMESTRE',
            numero=1, est_active=True
        )
        self.niveau = Niveau.objects.create(nom='6eme')
        self.salle = SalleClasse.objects.create(
            niveau=self.niveau, annee=self.annee, nom='6eme1'
        )
        self.matiere = Matiere.objects.create(nom='Mathematiques')
        self.prof = CustomUser.objects.create_user(
            username='prof1', password='test1234', role='PROFESSEUR'
        )
        self.censeur = CustomUser.objects.create_user(
            username='censeur1', password='test1234', role='CENSEUR'
        )
        self.ms = MatiereSalle.objects.create(
            salle=self.salle,
            matiere=self.matiere,
            professeur=self.prof,
            coefficient=3,
        )
        user_eleve = CustomUser.objects.create_user(
            username='eleve1', password='test1234', role='ELEVE'
        )
        self.eleve = Eleve.objects.create(
            user=user_eleve,
            matricule='BKT-2025-0001',
            nom='KOFFI', prenom='Jean', sexe='M',
        )
        Inscription.objects.create(
            eleve=self.eleve, salle=self.salle,
            annee=self.annee, statut='ACTIVE'
        )

    def test_creation_evaluation_brouillon(self):
        """Evaluation creee en statut BROUILLON."""
        ev = Evaluation.objects.create(
            matiere_salle=self.ms,
            periode=self.periode,
            titre='Devoir 1',
            type='DEVOIR',
            date=timezone.now().date(),
            note_sur=20,
            statut='BROUILLON',
            creee_par=self.prof,
        )
        self.assertEqual(ev.statut, 'BROUILLON')

    def test_workflow_validation_evaluation(self):
        """Workflow BROUILLON -> VALIDEE -> EN_SAISIE."""
        ev = Evaluation.objects.create(
            matiere_salle=self.ms,
            periode=self.periode,
            titre='Devoir 1',
            type='DEVOIR',
            date=timezone.now().date(),
            note_sur=20,
            statut='BROUILLON',
            creee_par=self.prof,
        )
        self.assertEqual(ev.statut, 'BROUILLON')

        # Validation par censeur
        ev.statut = 'VALIDEE'
        ev.validee_par = self.censeur
        ev.save()
        self.assertEqual(ev.statut, 'VALIDEE')

        # Autorisation saisie
        autorisation = AutorisationSaisie.objects.create(
            evaluation=ev,
            autorise_par=self.censeur,
            saisie_par=self.prof,
            est_autorisee=True,
        )
        ev.statut = 'EN_SAISIE'
        ev.save()
        self.assertEqual(ev.statut, 'EN_SAISIE')
        self.assertEqual(
            autorisation.saisisseur_effectif, self.prof
        )

    def test_autorisation_saisisseur_effectif_sans_assignation(self):
        """
        Si pas de saisisseur assigne,
        saisisseur_effectif retourne le prof de la matiere.
        """
        ev = Evaluation.objects.create(
            matiere_salle=self.ms,
            periode=self.periode,
            titre='Devoir 2',
            type='DEVOIR',
            date=timezone.now().date(),
            note_sur=20,
            statut='VALIDEE',
            creee_par=self.prof,
        )
        autorisation = AutorisationSaisie.objects.create(
            evaluation=ev,
            autorise_par=self.censeur,
            saisie_par=None,
            est_autorisee=True,
        )
        self.assertEqual(
            autorisation.saisisseur_effectif, self.prof
        )

    def test_saisie_note_valide(self):
        """Saisie d'une note valide."""
        ev = Evaluation.objects.create(
            matiere_salle=self.ms,
            periode=self.periode,
            titre='Devoir 1',
            type='DEVOIR',
            date=timezone.now().date(),
            note_sur=20,
            statut='EN_SAISIE',
            creee_par=self.prof,
        )
        note = Note.objects.create(
            evaluation=ev,
            eleve=self.eleve,
            valeur=15.5,
            saisie_par=self.prof,
        )
        self.assertEqual(float(note.valeur), 15.5)
        self.assertFalse(note.est_absent)

    def test_saisie_note_absent(self):
        """Saisie d'un absent."""
        ev = Evaluation.objects.create(
            matiere_salle=self.ms,
            periode=self.periode,
            titre='Devoir 1',
            type='DEVOIR',
            date=timezone.now().date(),
            note_sur=20,
            statut='EN_SAISIE',
            creee_par=self.prof,
        )
        note = Note.objects.create(
            evaluation=ev,
            eleve=self.eleve,
            valeur=None,
            est_absent=True,
            saisie_par=self.prof,
        )
        self.assertTrue(note.est_absent)
        self.assertIsNone(note.valeur)

    def test_historique_note(self):
        """Modification d'une note cree un historique."""
        ev = Evaluation.objects.create(
            matiere_salle=self.ms,
            periode=self.periode,
            titre='Devoir 1',
            type='DEVOIR',
            date=timezone.now().date(),
            note_sur=20,
            statut='EN_SAISIE',
            creee_par=self.prof,
        )
        note = Note.objects.create(
            evaluation=ev,
            eleve=self.eleve,
            valeur=14,
            saisie_par=self.prof,
        )
        # Modifier la note
        note.valeur = 16
        note.save()
        self.assertEqual(note.historique.count(), 1)
        historique = note.historique.first()
        self.assertEqual(float(historique.ancienne_valeur), 14)
        self.assertEqual(float(historique.nouvelle_valeur), 16)

    def test_note_unique_par_evaluation_eleve(self):
        """Une seule note par evaluation par eleve."""
        from django.db import IntegrityError
        ev = Evaluation.objects.create(
            matiere_salle=self.ms,
            periode=self.periode,
            titre='Devoir 1',
            type='DEVOIR',
            date=timezone.now().date(),
            note_sur=20,
            statut='EN_SAISIE',
            creee_par=self.prof,
        )
        Note.objects.create(
            evaluation=ev, eleve=self.eleve,
            valeur=15, saisie_par=self.prof
        )
        with self.assertRaises(IntegrityError):
            Note.objects.create(
                evaluation=ev, eleve=self.eleve,
                valeur=12, saisie_par=self.prof
            )


class MoyenneTestCase(TestCase):

    def setUp(self):
        self.annee = AnneeScolaire.objects.create(
            nom='2025-2026', est_active=True
        )
        self.periode = Periode.objects.create(
            annee=self.annee, type='TRIMESTRE',
            numero=1, est_active=True
        )
        self.niveau = Niveau.objects.create(nom='6eme')
        self.salle = SalleClasse.objects.create(
            niveau=self.niveau, annee=self.annee, nom='6eme1'
        )
        self.matiere = Matiere.objects.create(nom='Maths')
        self.prof = CustomUser.objects.create_user(
            username='prof2', password='test1234', role='PROFESSEUR'
        )
        self.ms = MatiereSalle.objects.create(
            salle=self.salle, matiere=self.matiere,
            professeur=self.prof, coefficient=3,
        )
        user_eleve = CustomUser.objects.create_user(
            username='eleve2', password='test1234', role='ELEVE'
        )
        self.eleve = Eleve.objects.create(
            user=user_eleve,
            matricule='BKT-2025-0002',
            nom='AMA', prenom='Kofi', sexe='M',
        )
        Inscription.objects.create(
            eleve=self.eleve, salle=self.salle,
            annee=self.annee, statut='ACTIVE'
        )

    def test_appreciation_moyenne_matiere(self):
        """Appreciation calculee correctement selon la moyenne."""
        cas = [
            (16.5, 'Très Bien'),
            (14.0, 'Bien'),
            (12.0, 'Assez Bien'),
            (10.0, 'Passable'),
            (8.0, 'Insuffisant'),
            (5.0, 'Très Insuffisant'),
        ]
        for moy, appreciation_attendue in cas:
            mm = MoyenneMatiere(
                eleve=self.eleve,
                matiere_salle=self.ms,
                periode=self.periode,
                moyenne_eleve=moy,
            )
            mm.save()
            self.assertEqual(
                mm.appreciation, appreciation_attendue,
                f"Moyenne {moy} devrait donner '{appreciation_attendue}'"
            )
            mm.delete()

    def test_points_calcules(self):
        """Points = moyenne * coefficient."""
        mm = MoyenneMatiere.objects.create(
            eleve=self.eleve,
            matiere_salle=self.ms,
            periode=self.periode,
            moyenne_eleve=14.0,
        )
        self.assertEqual(float(mm.points), 42.0)

    def test_mention_moyenne_generale(self):
        """Mention calculee correctement."""
        cas = [
            (16.0, 'Très Bien'),
            (14.0, 'Bien'),
            (12.0, 'Assez Bien'),
            (10.0, 'Passable'),
            (8.0, 'Insuffisant'),
            (4.0, 'Très Insuffisant'),
        ]
        for moy, mention_attendue in cas:
            mg = MoyenneGenerale(moyenne=moy)
            self.assertEqual(
                mg.mention, mention_attendue,
                f"Moy {moy} → '{mention_attendue}'"
            )
