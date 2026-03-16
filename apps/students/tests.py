from django.test import TestCase, Client
from django.urls import reverse
from apps.authentication.models import CustomUser
from apps.academic.models import AnneeScolaire, Niveau, SalleClasse
from apps.students.models import Eleve, Parent, EleveParent, Inscription


class EleveTestCase(TestCase):

    def setUp(self):
        self.annee = AnneeScolaire.objects.create(
            nom='2025-2026', est_active=True
        )
        self.niveau = Niveau.objects.create(nom='6eme', ordre=1)
        self.salle = SalleClasse.objects.create(
            niveau=self.niveau,
            annee=self.annee,
            nom='6eme1',
            capacite=40,
        )
        self.user_dir = CustomUser.objects.create_user(
            username='dir', password='test1234', role='DIRECTEUR'
        )
        self.user_eleve = CustomUser.objects.create_user(
            username='eleve_test', password='test1234', role='ELEVE'
        )
        self.eleve = Eleve.objects.create(
            user=self.user_eleve,
            matricule='BKT-2025-0001',
            nom='KOFFI',
            prenom='Jean',
            sexe='M',
        )
        self.inscription = Inscription.objects.create(
            eleve=self.eleve,
            salle=self.salle,
            annee=self.annee,
            statut='ACTIVE',
        )
        self.client = Client()

    def test_nom_complet(self):
        """Property nom_complet retourne le bon format."""
        self.assertEqual(self.eleve.nom_complet, 'KOFFI Jean')

    def test_inscription_active(self):
        """Property inscription_active retourne la bonne inscription."""
        self.assertEqual(
            self.eleve.inscription_active, self.inscription
        )

    def test_salle_active(self):
        """Property salle_active retourne la bonne salle."""
        self.assertEqual(self.eleve.salle_active, self.salle)

    def test_effectif_salle_apres_inscription(self):
        """Effectif salle augmente apres inscription."""
        self.assertEqual(self.salle.effectif, 1)

    def test_eleve_parent_lien(self):
        """Lien eleve-parent cree correctement."""
        user_parent = CustomUser.objects.create_user(
            username='parent1', password='test1234', role='PARENT'
        )
        parent = Parent.objects.create(
            user=user_parent,
            nom='AGBEKO',
            prenom='Marie',
            telephone='+22890000002',
        )
        ep = EleveParent.objects.create(
            eleve=self.eleve,
            parent=parent,
            lien='MERE',
            est_contact_principal=True,
        )
        self.assertEqual(ep.get_lien_display(), 'Mère')
        self.assertEqual(self.eleve.parents.count(), 1)

    def test_liste_eleves_accessible_directeur(self):
        """Directeur peut voir la liste des eleves."""
        self.client.login(username='dir', password='test1234')
        response = self.client.get(reverse('liste_eleves'))
        self.assertEqual(response.status_code, 200)

    def test_liste_eleves_refusee_eleve(self):
        """Eleve ne peut pas voir la liste des eleves."""
        self.client.login(username='eleve_test', password='test1234')
        response = self.client.get(reverse('liste_eleves'))
        self.assertEqual(response.status_code, 302)

    def test_detail_eleve_accessible(self):
        """Detail eleve accessible par directeur."""
        self.client.login(username='dir', password='test1234')
        response = self.client.get(
            reverse('detail_eleve', args=[self.eleve.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_export_excel_accessible(self):
        """Export Excel accessible par directeur."""
        self.client.login(username='dir', password='test1234')
        response = self.client.get(reverse('export_eleves_excel'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.openxmlformats-officedocument'
            '.spreadsheetml.sheet'
        )

    def test_inscription_unique_par_annee(self):
        """Un eleve ne peut etre inscrit qu'une fois par annee."""
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Inscription.objects.create(
                eleve=self.eleve,
                salle=self.salle,
                annee=self.annee,
                statut='ACTIVE',
            )
