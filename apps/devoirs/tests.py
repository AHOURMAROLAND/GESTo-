from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from apps.authentication.models import CustomUser
from apps.academic.models import (
    AnneeScolaire, Niveau, SalleClasse, Matiere, MatiereSalle
)
from apps.students.models import Eleve, Inscription
from apps.devoirs.models import Devoir, SoumissionDevoir


class DevoirsTestCase(TestCase):

    def setUp(self):
        self.annee = AnneeScolaire.objects.create(
            nom='2025-2026', est_active=True
        )
        self.niveau = Niveau.objects.create(nom='6eme', ordre=1)
        self.salle = SalleClasse.objects.create(
            niveau=self.niveau, annee=self.annee, nom='6eme1'
        )
        self.matiere = Matiere.objects.create(nom='Mathématiques')
        self.prof = CustomUser.objects.create_user(
            username='prof_dev', password='test1234',
            role='PROFESSEUR'
        )
        self.ms = MatiereSalle.objects.create(
            salle=self.salle, matiere=self.matiere,
            professeur=self.prof, coefficient=3
        )
        user_eleve = CustomUser.objects.create_user(
            username='eleve_dev', password='test1234',
            role='ELEVE'
        )
        self.eleve = Eleve.objects.create(
            user=user_eleve,
            matricule='BKT-2025-DEV',
            nom='AGBEKO', prenom='Ama', sexe='F',
        )
        Inscription.objects.create(
            eleve=self.eleve, salle=self.salle,
            annee=self.annee, statut='ACTIVE'
        )
        self.client = Client()
        self.today = timezone.now().date()

    def test_creation_devoir(self):
        devoir = Devoir.objects.create(
            matiere_salle=self.ms,
            titre='DM1 — Maths',
            type='DEVOIR',
            description='Exercices du chapitre 1.',
            date_limite=self.today + timedelta(days=7),
            note_sur=20,
            statut='PUBLIE',
            publie_par=self.prof,
        )
        self.assertEqual(devoir.titre, 'DM1 — Maths')
        self.assertEqual(devoir.statut, 'PUBLIE')

    def test_devoir_en_retard(self):
        devoir = Devoir.objects.create(
            matiere_salle=self.ms,
            titre='DM ancien',
            description='Test.',
            date_limite=self.today - timedelta(days=1),
            note_sur=20,
            statut='PUBLIE',
            publie_par=self.prof,
        )
        self.assertTrue(devoir.est_en_retard)

    def test_devoir_pas_en_retard(self):
        devoir = Devoir.objects.create(
            matiere_salle=self.ms,
            titre='DM futur',
            description='Test.',
            date_limite=self.today + timedelta(days=5),
            note_sur=20,
            statut='PUBLIE',
            publie_par=self.prof,
        )
        self.assertFalse(devoir.est_en_retard)

    def test_soumission_devoir(self):
        devoir = Devoir.objects.create(
            matiere_salle=self.ms,
            titre='DM test',
            description='Test.',
            date_limite=self.today + timedelta(days=7),
            note_sur=20,
            statut='PUBLIE',
            publie_par=self.prof,
        )
        soumission = SoumissionDevoir.objects.create(
            devoir=devoir,
            eleve=self.eleve,
            contenu_texte='Mon travail.',
            statut='SOUMIS',
        )
        self.assertEqual(soumission.statut, 'SOUMIS')
        self.assertEqual(soumission.eleve, self.eleve)

    def test_correction_soumission(self):
        devoir = Devoir.objects.create(
            matiere_salle=self.ms,
            titre='DM corrige',
            description='Test.',
            date_limite=self.today + timedelta(days=7),
            note_sur=20,
            statut='PUBLIE',
            publie_par=self.prof,
        )
        soumission = SoumissionDevoir.objects.create(
            devoir=devoir,
            eleve=self.eleve,
            contenu_texte='Mon travail.',
            statut='SOUMIS',
        )
        soumission.note = Decimal('15.5')
        soumission.commentaire_prof = 'Bon travail'
        soumission.statut = 'CORRIGE'
        soumission.corrige_par = self.prof
        soumission.save()

        self.assertEqual(soumission.statut, 'CORRIGE')
        self.assertEqual(float(soumission.note), 15.5)

    def test_soumission_unique_par_devoir_eleve(self):
        from django.db import IntegrityError
        devoir = Devoir.objects.create(
            matiere_salle=self.ms,
            titre='DM unique',
            description='Test.',
            date_limite=self.today + timedelta(days=7),
            note_sur=20,
            statut='PUBLIE',
            publie_par=self.prof,
        )
        SoumissionDevoir.objects.create(
            devoir=devoir, eleve=self.eleve,
            contenu_texte='Premier envoi.', statut='SOUMIS',
        )
        with self.assertRaises(IntegrityError):
            SoumissionDevoir.objects.create(
                devoir=devoir, eleve=self.eleve,
                contenu_texte='Deuxième envoi.', statut='SOUMIS',
            )

    def test_taux_remise_devoir(self):
        devoir = Devoir.objects.create(
            matiere_salle=self.ms,
            titre='DM taux',
            description='Test.',
            date_limite=self.today + timedelta(days=7),
            note_sur=20,
            statut='PUBLIE',
            publie_par=self.prof,
        )
        self.assertEqual(devoir.taux_remise, 0)
        SoumissionDevoir.objects.create(
            devoir=devoir, eleve=self.eleve,
            contenu_texte='Travail.', statut='SOUMIS',
        )
        self.assertGreater(devoir.taux_remise, 0)

    def test_liste_devoirs_accessible_prof(self):
        self.client.login(
            username='prof_dev', password='test1234'
        )
        response = self.client.get(reverse('liste_devoirs'))
        self.assertEqual(response.status_code, 200)

    def test_liste_devoirs_accessible_eleve(self):
        self.client.login(
            username='eleve_dev', password='test1234'
        )
        response = self.client.get(reverse('liste_devoirs'))
        self.assertEqual(response.status_code, 200)

    def test_nouveau_devoir_accessible_prof(self):
        self.client.login(
            username='prof_dev', password='test1234'
        )
        response = self.client.get(reverse('nouveau_devoir'))
        self.assertEqual(response.status_code, 200)
