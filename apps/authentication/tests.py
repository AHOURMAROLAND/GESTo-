from django.test import TestCase, Client
from django.urls import reverse
from apps.authentication.models import CustomUser


class AuthTestCase(TestCase):

    def setUp(self):
        self.client = Client()
        self.directeur = CustomUser.objects.create_user(
            username='directeur_test',
            password='test1234',
            role='DIRECTEUR',
            first_name='Roland',
            last_name='TEST',
        )
        self.professeur = CustomUser.objects.create_user(
            username='prof_test',
            password='test1234',
            role='PROFESSEUR',
        )
        self.parent = CustomUser.objects.create_user(
            username='parent_test',
            password='test1234',
            role='PARENT',
            telephone_wa='+22890000001',
        )

    def test_login_correct_role(self):
        """Login avec bon role doit reussir."""
        response = self.client.post(reverse('login'), {
            'username': 'directeur_test',
            'password': 'test1234',
            'role': 'DIRECTEUR',
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, '/')

    def test_login_mauvais_role(self):
        """Login avec mauvais role doit echouer."""
        response = self.client.post(reverse('login'), {
            'username': 'directeur_test',
            'password': 'test1234',
            'role': 'PROFESSEUR',
        })
        self.assertEqual(response.status_code, 200)
        # Utiliser assertContains avec le texte sans apostrophe
        self.assertContains(response, "Ce compte n")
        self.assertContains(response, "est pas un compte Professeur")

    def test_login_mauvais_password(self):
        """Login avec mauvais mot de passe doit echouer."""
        response = self.client.post(reverse('login'), {
            'username': 'directeur_test',
            'password': 'mauvais',
            'role': 'DIRECTEUR',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "incorrect")

    def test_dashboard_sans_connexion(self):
        """Dashboard sans connexion doit rediriger vers login."""
        response = self.client.get('/')
        self.assertRedirects(response, '/login/?next=/')

    def test_dashboard_avec_connexion(self):
        """Dashboard avec connexion doit afficher la page."""
        self.client.login(username='directeur_test', password='test1234')
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_profil_accessible(self):
        """Page profil accessible apres connexion."""
        self.client.login(username='directeur_test', password='test1234')
        response = self.client.get(reverse('profil'))
        self.assertEqual(response.status_code, 200)

    def test_liste_personnel_acces_refuse_professeur(self):
        """Professeur ne peut pas voir la liste du personnel."""
        self.client.login(username='prof_test', password='test1234')
        response = self.client.get(reverse('liste_personnel'))
        self.assertEqual(response.status_code, 302)

    def test_liste_personnel_accessible_directeur(self):
        """Directeur peut voir la liste du personnel."""
        self.client.login(username='directeur_test', password='test1234')
        response = self.client.get(reverse('liste_personnel'))
        self.assertEqual(response.status_code, 200)

    def test_creation_personnel(self):
        """Creation d'un membre du personnel."""
        self.client.login(username='directeur_test', password='test1234')
        response = self.client.post(reverse('nouveau_personnel'), {
            'first_name': 'Jean',
            'last_name': 'DUPONT',
            'role': 'PROFESSEUR',
            'telephone': '+22890000000',
            'telephone_wa': '',
            'specialite': 'Mathematiques',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            CustomUser.objects.filter(last_name='DUPONT').exists()
        )

    def test_has_role(self):
        """Methode has_role fonctionne correctement."""
        self.assertTrue(
            self.directeur.has_role('DIRECTEUR')
        )
        self.assertFalse(
            self.directeur.has_role('PROFESSEUR')
        )
        self.assertTrue(
            self.directeur.has_role('DIRECTEUR', 'CENSEUR')
        )

    def test_nom_complet(self):
        """Property nom_complet retourne le bon format."""
        self.assertEqual(
            self.directeur.nom_complet,
            'Roland TEST'
        )
