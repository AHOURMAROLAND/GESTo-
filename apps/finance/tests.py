from django.test import TestCase
from django.utils import timezone
from apps.authentication.models import CustomUser
from apps.academic.models import AnneeScolaire, Niveau
from apps.students.models import Eleve, Inscription
from apps.academic.models import SalleClasse
from apps.finance.models import (
    TypeFrais, TarifNiveau, FraisEleve, Paiement
)
from apps.finance.views import generer_numero_recu


class FinanceTestCase(TestCase):

    def setUp(self):
        self.annee = AnneeScolaire.objects.create(
            nom='2025-2026', est_active=True
        )
        self.niveau = Niveau.objects.create(nom='6eme')
        self.salle = SalleClasse.objects.create(
            niveau=self.niveau, annee=self.annee, nom='6eme1'
        )
        self.type_frais = TypeFrais.objects.create(
            nom='Frais de scolarite', est_obligatoire=True
        )
        self.tarif = TarifNiveau.objects.create(
            niveau=self.niveau,
            annee=self.annee,
            frais_inscription=50000,
            frais_scolarite=150000,
            frais_examen=25000,
        )
        self.comptable = CustomUser.objects.create_user(
            username='compta1', password='test1234', role='COMPTABLE'
        )
        user_eleve = CustomUser.objects.create_user(
            username='eleve_fin', password='test1234', role='ELEVE'
        )
        self.eleve = Eleve.objects.create(
            user=user_eleve,
            matricule='BKT-2025-0010',
            nom='AGBEKO', prenom='Afi', sexe='F',
        )
        Inscription.objects.create(
            eleve=self.eleve, salle=self.salle,
            annee=self.annee, statut='ACTIVE'
        )
        self.frais = FraisEleve.objects.create(
            eleve=self.eleve,
            type_frais=self.type_frais,
            annee=self.annee,
            montant=150000,
            montant_paye=0,
        )

    def test_tarif_total(self):
        """Tarif total = inscription + scolarite + examen."""
        self.assertEqual(float(self.tarif.total), 225000)

    def test_solde_frais(self):
        """Solde = montant - montant_paye."""
        self.assertEqual(float(self.frais.solde), 150000)

    def test_solde_apres_paiement_partiel(self):
        """Solde diminue apres paiement partiel."""
        self.frais.montant_paye = 75000
        self.frais.save()
        self.assertEqual(float(self.frais.solde), 75000)

    def test_solde_zero_apres_paiement_complet(self):
        """Solde = 0 apres paiement complet."""
        self.frais.montant_paye = 150000
        self.frais.save()
        self.assertEqual(float(self.frais.solde), 0)

    def test_numero_recu_sequentiel(self):
        """Numeros de recu incrementaux."""
        annee_str = str(timezone.now().year)
        n1 = generer_numero_recu(annee_str)
        self.assertEqual(n1, f"REC-{annee_str}-0001")

        Paiement.objects.create(
            eleve=self.eleve,
            frais=self.frais,
            montant=50000,
            moyen='ESPECES',
            recu_par=self.comptable,
            numero_recu=n1,
        )
        n2 = generer_numero_recu(annee_str)
        self.assertEqual(n2, f"REC-{annee_str}-0002")

    def test_format_numero_recu(self):
        """Format numero recu correct REC-YYYY-NNNN."""
        import re
        annee_str = str(timezone.now().year)
        numero = generer_numero_recu(annee_str)
        self.assertRegex(
            numero,
            rf'^REC-{annee_str}-\d{{4}}$'
        )

class RecouvrementTestCase(TestCase):

    def setUp(self):
        from django.test import Client
        self.annee = AnneeScolaire.objects.create(
            nom='2025-2026', est_active=True
        )
        self.niveau = Niveau.objects.create(nom='6eme')
        self.salle = SalleClasse.objects.create(
            niveau=self.niveau, annee=self.annee, nom='6eme1'
        )
        self.type_frais = TypeFrais.objects.create(
            nom='Scolarité', est_obligatoire=True
        )
        self.comptable = CustomUser.objects.create_user(
            username='compta_rec', password='test1234',
            role='COMPTABLE'
        )
        self.directeur = CustomUser.objects.create_user(
            username='dir_rec', password='test1234',
            role='DIRECTEUR'
        )
        user_eleve = CustomUser.objects.create_user(
            username='eleve_rec', password='test1234',
            role='ELEVE'
        )
        self.eleve = Eleve.objects.create(
            user=user_eleve,
            matricule='BKT-2025-REC',
            nom='TOGBE', prenom='Kofi', sexe='M',
        )
        Inscription.objects.create(
            eleve=self.eleve, salle=self.salle,
            annee=self.annee, statut='ACTIVE'
        )
        self.frais = FraisEleve.objects.create(
            eleve=self.eleve,
            type_frais=self.type_frais,
            annee=self.annee,
            montant=150000,
        )
        self.client = Client()

    def test_dashboard_finance_accessible_comptable(self):
        from django.urls import reverse
        self.client.login(
            username='compta_rec', password='test1234'
        )
        response = self.client.get(
            reverse('dashboard_finance')
        )
        self.assertEqual(response.status_code, 200)

    def test_dashboard_finance_accessible_directeur(self):
        from django.urls import reverse
        self.client.login(
            username='dir_rec', password='test1234'
        )
        response = self.client.get(
            reverse('dashboard_finance')
        )
        self.assertEqual(response.status_code, 200)

    def test_liste_paiements_accessible(self):
        from django.urls import reverse
        self.client.login(
            username='compta_rec', password='test1234'
        )
        response = self.client.get(
            reverse('liste_paiements')
        )
        self.assertEqual(response.status_code, 200)

    def test_etat_recouvrement_accessible(self):
        from django.urls import reverse
        self.client.login(
            username='dir_rec', password='test1234'
        )
        response = self.client.get(
            reverse('etat_recouvrement')
        )
        self.assertEqual(response.status_code, 200)

    def test_frais_eleve_solde_initial(self):
        self.assertEqual(float(self.frais.solde), 150000)

    def test_paiement_partiel_reduit_solde(self):
        from apps.finance.views import generer_numero_recu
        from django.utils import timezone
        numero = generer_numero_recu(str(timezone.now().year))
        Paiement.objects.create(
            eleve=self.eleve,
            frais=self.frais,
            montant=75000,
            moyen='ESPECES',
            recu_par=self.comptable,
            numero_recu=numero,
        )
        self.frais.montant_paye = 75000
        self.frais.save()
        self.assertEqual(float(self.frais.solde), 75000)

    def test_liste_tarifs_accessible(self):
        from django.urls import reverse
        self.client.login(
            username='dir_rec', password='test1234'
        )
        response = self.client.get(reverse('liste_tarifs'))
        self.assertEqual(response.status_code, 200)

    def test_finance_refuse_eleve(self):
        from django.urls import reverse
        self.client.login(
            username='eleve_rec', password='test1234'
        )
        response = self.client.get(
            reverse('dashboard_finance')
        )
        self.assertEqual(response.status_code, 302)
