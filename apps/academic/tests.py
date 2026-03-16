from django.test import TestCase, Client
from django.urls import reverse
from apps.authentication.models import CustomUser
from apps.academic.models import (
    AnneeScolaire, Periode, Niveau, GroupeMatiere,
    SalleClasse, Matiere, MatiereSalle
)


class AnneeScolaireTestCase(TestCase):

    def test_creation_annee(self):
        """Creation d'une annee scolaire."""
        annee = AnneeScolaire.objects.create(nom='2025-2026')
        self.assertEqual(str(annee), '2025-2026')

    def test_activation_annee(self):
        """Activer une annee desactive les autres."""
        a1 = AnneeScolaire.objects.create(nom='2024-2025', est_active=True)
        a2 = AnneeScolaire.objects.create(nom='2025-2026')
        a2.est_active = True
        a2.save()
        a1.refresh_from_db()
        self.assertFalse(a1.est_active)
        self.assertTrue(a2.est_active)

    def test_annee_active_classmethod(self):
        """AnneeScolaire.active() retourne la bonne annee."""
        a = AnneeScolaire.objects.create(nom='2025-2026', est_active=True)
        self.assertEqual(AnneeScolaire.active(), a)

    def test_annee_active_aucune(self):
        """AnneeScolaire.active() retourne None si aucune active."""
        self.assertIsNone(AnneeScolaire.active())

    def test_periode_active(self):
        """Periode.active() retourne la bonne periode."""
        annee = AnneeScolaire.objects.create(nom='2025-2026', est_active=True)
        p1 = Periode.objects.create(
            annee=annee, type='TRIMESTRE', numero=1, est_active=True
        )
        p2 = Periode.objects.create(
            annee=annee, type='TRIMESTRE', numero=2
        )
        self.assertEqual(Periode.active(annee), p1)

    def test_activation_periode(self):
        """Activer une periode desactive les autres de la meme annee."""
        annee = AnneeScolaire.objects.create(nom='2025-2026', est_active=True)
        p1 = Periode.objects.create(
            annee=annee, type='TRIMESTRE', numero=1, est_active=True
        )
        p2 = Periode.objects.create(
            annee=annee, type='TRIMESTRE', numero=2
        )
        p2.est_active = True
        p2.save()
        p1.refresh_from_db()
        self.assertFalse(p1.est_active)
        self.assertTrue(p2.est_active)

    def test_niveau_nb_periodes(self):
        """Niveau.nb_periodes retourne 3 pour trimestriel, 2 pour semestriel."""
        n_tri = Niveau.objects.create(
            nom='6eme', systeme='TRIMESTRIEL'
        )
        n_sem = Niveau.objects.create(
            nom='2nde', systeme='SEMESTRIEL'
        )
        self.assertEqual(n_tri.nb_periodes, 3)
        self.assertEqual(n_sem.nb_periodes, 2)

    def test_creation_salle(self):
        """Creation d'une salle avec niveau et annee."""
        annee = AnneeScolaire.objects.create(nom='2025-2026', est_active=True)
        niveau = Niveau.objects.create(nom='6eme', ordre=1)
        salle = SalleClasse.objects.create(
            niveau=niveau,
            annee=annee,
            nom='6eme1',
            capacite=40,
        )
        self.assertEqual(str(salle), '6eme1 (2025-2026)')

    def test_effectif_salle(self):
        """Effectif salle retourne le bon nombre d'inscrits."""
        annee = AnneeScolaire.objects.create(nom='2025-2026', est_active=True)
        niveau = Niveau.objects.create(nom='6eme', ordre=1)
        salle = SalleClasse.objects.create(
            niveau=niveau, annee=annee, nom='6eme1'
        )
        self.assertEqual(salle.effectif, 0)

    def test_salle_systeme_herite_niveau(self):
        """Salle.systeme retourne le systeme du niveau."""
        annee = AnneeScolaire.objects.create(nom='2025-2026')
        niveau = Niveau.objects.create(
            nom='6eme', systeme='TRIMESTRIEL'
        )
        salle = SalleClasse.objects.create(
            niveau=niveau, annee=annee, nom='6eme1'
        )
        self.assertEqual(salle.systeme, 'TRIMESTRIEL')

    def test_matiere_salle_unique(self):
        """Une matiere ne peut etre assignee deux fois a la meme salle."""
        from django.db import IntegrityError
        annee = AnneeScolaire.objects.create(nom='2025-2026')
        niveau = Niveau.objects.create(nom='6eme')
        salle = SalleClasse.objects.create(
            niveau=niveau, annee=annee, nom='6eme1'
        )
        matiere = Matiere.objects.create(nom='Mathematiques')
        MatiereSalle.objects.create(
            salle=salle, matiere=matiere, coefficient=3
        )
        with self.assertRaises(IntegrityError):
            MatiereSalle.objects.create(
                salle=salle, matiere=matiere, coefficient=2
            )
