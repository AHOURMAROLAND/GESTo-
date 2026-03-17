from django.test import TestCase
from apps.authentication.models import CustomUser
from apps.communication.models import Notification, Message
from apps.communication.bots import (
    valider_numero_wa, _est_spam, TEMPLATES
)


class NotificationTestCase(TestCase):

    def setUp(self):
        self.user1 = CustomUser.objects.create_user(
            username='user1', password='test1234', role='DIRECTEUR'
        )
        self.user2 = CustomUser.objects.create_user(
            username='user2', password='test1234', role='PROFESSEUR'
        )

    def test_creation_notification(self):
        """Creation d'une notification via classmethod creer."""
        notif = Notification.creer(
            destinataire=self.user1,
            titre='Test notification',
            message='Message de test',
            type='INFO',
        )
        self.assertEqual(notif.titre, 'Test notification')
        self.assertFalse(notif.est_lue)
        self.assertEqual(notif.destinataire, self.user1)

    def test_notification_non_lue_par_defaut(self):
        """Notification non lue par defaut."""
        notif = Notification.creer(
            destinataire=self.user1,
            titre='Test',
            message='Test',
        )
        self.assertFalse(notif.est_lue)

    def test_marquer_notification_lue(self):
        """Marquer une notification comme lue."""
        notif = Notification.creer(
            destinataire=self.user1,
            titre='Test',
            message='Test',
        )
        notif.est_lue = True
        notif.save()
        notif.refresh_from_db()
        self.assertTrue(notif.est_lue)

    def test_message_interne(self):
        """Creation d'un message interne."""
        msg = Message.objects.create(
            expediteur=self.user1,
            destinataire=self.user2,
            sujet='Test message',
            contenu='Contenu du message',
        )
        self.assertFalse(msg.est_lu)
        self.assertEqual(msg.expediteur, self.user1)
        self.assertEqual(msg.destinataire, self.user2)


class BotsTestCase(TestCase):

    def test_valider_numero_wa_format_correct(self):
        """Numero WA valide retourne True."""
        valide, num, msg = valider_numero_wa('+22890000001')
        self.assertTrue(valide)
        self.assertEqual(num, '+22890000001')

    def test_valider_numero_wa_format_sans_plus(self):
        """Numero sans + est corrige automatiquement."""
        valide, num, msg = valider_numero_wa('22890000001')
        self.assertTrue(valide)
        self.assertEqual(num, '+22890000001')

    def test_valider_numero_wa_format_invalide(self):
        """Numero trop court retourne False."""
        valide, num, msg = valider_numero_wa('123')
        self.assertFalse(valide)

    def test_valider_numero_wa_format_local_togo(self):
        """Numero local togolais (09XXXXXXX) converti avec +228."""
        valide, num, msg = valider_numero_wa('090000001')
        self.assertTrue(valide)
        self.assertIn('+228', num)

    def test_31_templates_definis(self):
        """Les 31 templates de bots sont bien definis."""
        self.assertEqual(len(TEMPLATES), 31)
        codes_attendus = [f'B{i:02d}' for i in range(1, 32)]
        for code in codes_attendus:
            self.assertIn(
                code, TEMPLATES,
                f"Template {code} manquant"
            )

    def test_templates_ont_categorie_et_message(self):
        """Chaque template a une categorie et un message."""
        for code, template in TEMPLATES.items():
            self.assertIn(
                'categorie', template,
                f"{code} n'a pas de categorie"
            )
            self.assertIn(
                'message', template,
                f"{code} n'a pas de message"
            )

    def test_anti_spam(self):
        """Anti-spam bloque le meme bot envoye deux fois en 1h."""
        from apps.communication.models import LogBot
        user = CustomUser.objects.create_user(
            username='user_spam', password='test1234', role='PARENT'
        )
        LogBot.objects.create(
            code_bot='B01',
            destinataire=user,
            canal='WA',
            statut='ENVOYE',
        )
        self.assertTrue(_est_spam('B01', user))
        self.assertFalse(_est_spam('B02', user))

class CalendrierTestCase(TestCase):

    def setUp(self):
        from apps.academic.models import AnneeScolaire
        self.annee = AnneeScolaire.objects.create(
            nom='2025-2026', est_active=True
        )
        self.directeur = CustomUser.objects.create_user(
            username='dir_cal', password='test1234',
            role='DIRECTEUR'
        )
        from django.test import Client
        self.client = Client()
        self.client.login(
            username='dir_cal', password='test1234'
        )

    def test_creer_evenement_calendrier(self):
        from apps.communication.models import EvenementCalendrier
        from datetime import date
        ev = EvenementCalendrier.objects.create(
            titre='Toussaint',
            type='FERIE',
            date_debut=date(2025, 11, 1),
            annee=self.annee,
            creee_par=self.directeur,
        )
        self.assertEqual(ev.titre, 'Toussaint')
        self.assertEqual(ev.type, 'FERIE')

    def test_evenement_passe(self):
        from apps.communication.models import EvenementCalendrier
        from datetime import date
        ev = EvenementCalendrier.objects.create(
            titre='Test passé',
            type='EVENEMENT',
            date_debut=date(2020, 1, 1),
            annee=self.annee,
            creee_par=self.directeur,
        )
        self.assertTrue(ev.est_passe)

    def test_calendrier_accessible(self):
        from django.urls import reverse
        response = self.client.get(
            reverse('calendrier')
        )
        self.assertEqual(response.status_code, 200)

    def test_nouvel_evenement_accessible_directeur(self):
        from django.urls import reverse
        response = self.client.get(
            reverse('nouvel_evenement')
        )
        self.assertEqual(response.status_code, 200)

    def test_reunion_parent_creation(self):
        from apps.communication.models import ReunionParent
        from datetime import date, time
        r = ReunionParent.objects.create(
            titre='Réunion T1',
            date=date(2025, 12, 22),
            heure=time(9, 0),
            lieu='Salle polyvalente',
            statut='PLANIFIEE',
            organisee_par=self.directeur,
            annee=self.annee,
        )
        self.assertEqual(r.statut, 'PLANIFIEE')
        self.assertEqual(r.titre, 'Réunion T1')
