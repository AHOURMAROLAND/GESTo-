from django.test import TestCase, Client
from django.urls import reverse
from apps.authentication.models import CustomUser
from apps.academic.models import AnneeScolaire, Niveau, SalleClasse
from apps.students.models import Eleve, Inscription
from apps.discipline.models import TypeSanction, Sanction, DemandeExclusion
from django.utils import timezone


class DisciplineTestCase(TestCase):

    def setUp(self):
        self.annee = AnneeScolaire.objects.create(
            nom='2025-2026', est_active=True
        )
        self.niveau = Niveau.objects.create(nom='6eme', ordre=1)
        self.salle = SalleClasse.objects.create(
            niveau=self.niveau, annee=self.annee, nom='6eme1'
        )
        self.directeur = CustomUser.objects.create_user(
            username='dir_disc', password='test1234',
            role='DIRECTEUR'
        )
        self.censeur = CustomUser.objects.create_user(
            username='cens_disc', password='test1234',
            role='CENSEUR'
        )
        self.surveillant = CustomUser.objects.create_user(
            username='surv_disc', password='test1234',
            role='SURVEILLANT'
        )
        user_eleve = CustomUser.objects.create_user(
            username='eleve_disc', password='test1234',
            role='ELEVE'
        )
        self.eleve = Eleve.objects.create(
            user=user_eleve,
            matricule='BKT-2025-DISC',
            nom='KOFFI', prenom='Jean', sexe='M',
        )
        Inscription.objects.create(
            eleve=self.eleve, salle=self.salle,
            annee=self.annee, statut='ACTIVE'
        )
        self.type_sanction = TypeSanction.objects.create(
            nom='Avertissement', gravite=1
        )
        self.client = Client()

    def test_creation_type_sanction(self):
        ts = TypeSanction.objects.create(
            nom='Blâme', gravite=2
        )
        self.assertEqual(ts.nom, 'Blâme')
        self.assertEqual(ts.gravite, 2)

    def test_sanction_statut_defaut(self):
        s = Sanction.objects.create(
            eleve=self.eleve,
            type_sanction=self.type_sanction,
            motif='Bavardage',
            date_faits=timezone.now().date(),
            signale_par=self.surveillant,
        )
        self.assertEqual(s.statut, 'EN_ATTENTE')

    def test_approbation_sanction(self):
        s = Sanction.objects.create(
            eleve=self.eleve,
            type_sanction=self.type_sanction,
            motif='Retard répété',
            date_faits=timezone.now().date(),
            statut='EN_ATTENTE',
            signale_par=self.surveillant,
        )
        s.statut = 'APPROUVEE'
        s.approuve_par = self.censeur
        s.save()
        self.assertEqual(s.statut, 'APPROUVEE')
        self.assertEqual(s.approuve_par, self.censeur)

    def test_demande_exclusion_creation(self):
        de = DemandeExclusion.objects.create(
            eleve=self.eleve,
            motif='Violence répétée',
            statut='EN_ATTENTE',
            demandee_par=self.surveillant,
        )
        self.assertEqual(de.statut, 'EN_ATTENTE')
        self.assertEqual(de.demandee_par, self.surveillant)

    def test_liste_sanctions_accessible_censeur(self):
        self.client.login(
            username='cens_disc', password='test1234'
        )
        response = self.client.get(reverse('liste_sanctions'))
        self.assertEqual(response.status_code, 200)

    def test_nouvelle_sanction_accessible_surveillant(self):
        self.client.login(
            username='surv_disc', password='test1234'
        )
        response = self.client.get(
            reverse('nouvelle_sanction')
        )
        self.assertEqual(response.status_code, 200)

    def test_exclusion_refusee_sans_droits(self):
        user = CustomUser.objects.create_user(
            username='prof_disc', password='test1234',
            role='PROFESSEUR'
        )
        self.client.login(
            username='prof_disc', password='test1234'
        )
        response = self.client.get(
            reverse('liste_exclusions')
        )
        self.assertEqual(response.status_code, 302)
