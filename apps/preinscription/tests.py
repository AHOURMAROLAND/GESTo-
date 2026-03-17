from django.test import TestCase, Client
from django.urls import reverse
from apps.authentication.models import CustomUser
from apps.academic.models import AnneeScolaire, Niveau, SalleClasse
from apps.preinscription.models import PreInscription


class PreInscriptionTestCase(TestCase):

    def setUp(self):
        self.client = Client()
        self.annee = AnneeScolaire.objects.create(
            nom='2025-2026', est_active=True
        )
        self.niveau = Niveau.objects.create(nom='6eme', ordre=1)
        self.salle = SalleClasse.objects.create(
            niveau=self.niveau, annee=self.annee,
            nom='6eme1', capacite=40
        )
        self.secretaire = CustomUser.objects.create_user(
            username='secret1', password='test1234', role='SECRETAIRE'
        )
        self.censeur = CustomUser.objects.create_user(
            username='cens1', password='test1234', role='CENSEUR'
        )

    def test_formulaire_public_accessible_sans_login(self):
        """Formulaire public accessible sans connexion."""
        response = self.client.get(
            reverse('formulaire_preinscription')
        )
        self.assertEqual(response.status_code, 200)

    def test_soumission_formulaire(self):
        """Soumission formulaire cree une pre-inscription."""
        response = self.client.post(
            reverse('formulaire_preinscription'), {
                'nom_eleve': 'KOFFI',
                'prenom_eleve': 'Jean',
                'sexe_eleve': 'M',
                'niveau_souhaite': '6eme',
                'nom_parent': 'KOFFI',
                'prenom_parent': 'Maman',
                'telephone_parent': '+22890000001',
                'telephone_wa_parent': '+22890000001',
                'lien_parent': 'MERE',
            }
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            PreInscription.objects.filter(nom_eleve='KOFFI').exists()
        )

    def test_reference_generee_automatiquement(self):
        """Reference generee automatiquement a la creation."""
        pi = PreInscription.objects.create(
            nom_eleve='TEST',
            prenom_eleve='Eleve',
            sexe_eleve='M',
            niveau_souhaite='6eme',
            nom_parent='PARENT',
            telephone_parent='+22890000001',
        )
        self.assertTrue(pi.reference.startswith('PI-'))
        self.assertGreater(len(pi.reference), 5)

    def test_page_confirmation_accessible(self):
        """Page de confirmation accessible with la reference."""
        pi = PreInscription.objects.create(
            nom_eleve='TEST',
            prenom_eleve='Eleve',
            sexe_eleve='M',
            niveau_souhaite='6eme',
            nom_parent='PARENT',
            telephone_parent='+22890000001',
        )
        response = self.client.get(
            reverse(
                'confirmation_preinscription',
                args=[pi.reference]
            )
        )
        self.assertEqual(response.status_code, 200)

    def test_liste_preinscriptions_accessible_secretaire(self):
        """Secretaire peut voir la liste des pre-inscriptions."""
        self.client.login(username='secret1', password='test1234')
        response = self.client.get(
            reverse('liste_preinscriptions')
        )
        self.assertEqual(response.status_code, 200)

    def test_statut_par_defaut_en_attente(self):
        """Statut par defaut est EN_ATTENTE."""
        pi = PreInscription.objects.create(
            nom_eleve='TEST',
            prenom_eleve='Eleve',
            sexe_eleve='M',
            niveau_souhaite='6eme',
            nom_parent='PARENT',
            telephone_parent='+22890000001',
        )
        self.assertEqual(pi.statut, 'EN_ATTENTE')

    def test_validation_cree_eleve_et_parent(self):
        """Valider une pre-inscription cree les comptes eleve et parent."""
        pi = PreInscription.objects.create(
            nom_eleve='NOUVEAU',
            prenom_eleve='Eleve',
            sexe_eleve='M',
            niveau_souhaite='6eme',
            nom_parent='PARENT',
            prenom_parent='Papa',
            telephone_parent='+22890000002',
            telephone_wa_parent='+22890000002',
        )
        self.client.login(username='cens1', password='test1234')
        response = self.client.post(
            reverse('valider_preinscription', args=[pi.pk]),
            {'salle_id': self.salle.pk}
        )
        pi.refresh_from_db()
        self.assertEqual(pi.statut, 'VALIDEE')
        self.assertIsNotNone(pi.eleve_cree)
        self.assertTrue(
            CustomUser.objects.filter(role='ELEVE',
                                      last_name='NOUVEAU').exists()
        )
        self.assertTrue(
            CustomUser.objects.filter(role='PARENT',
                                      last_name='PARENT').exists()
        )
