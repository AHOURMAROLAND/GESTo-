from django.urls import path
from . import views

urlpatterns = [
    # Notifications
    path('notifications/', views.liste_notifications,
         name='liste_notifications'),
    path('notifications/<int:pk>/lue/', views.marquer_lue,
         name='marquer_lue'),
    path('notifications/tout-lire/', views.tout_marquer_lu,
         name='tout_marquer_lu'),
    path('api/notifications/nb/', views.nb_notifications,
         name='nb_notifications'),
    # Session
    path('api/session/prolonger/', views.prolonger_session,
         name='prolonger_session'),
    # Messagerie
    path('', views.messagerie, name='messagerie'),
    path('nouveau/', views.nouveau_message, name='nouveau_message'),
    path('message/<int:pk>/', views.detail_message, name='detail_message'),
    path('communique/nouveau/', views.nouveau_communique,
         name='nouveau_communique'),
    # Bots
    path('bots/logs/', views.logs_bots, name='logs_bots'),
    path('api/verifier-wa/', views.verifier_wa_view, name='verifier_wa'),
    # Calendrier
    path('calendrier/', views.calendrier, name='calendrier'),
    path('calendrier/nouveau/', views.nouvel_evenement,
         name='nouvel_evenement'),
    path('calendrier/<int:pk>/supprimer/', views.supprimer_evenement,
         name='supprimer_evenement'),
    # Reunions
    path('reunions/', views.liste_reunions, name='liste_reunions'),
    path('reunions/nouvelle/', views.nouvelle_reunion,
         name='nouvelle_reunion'),
    path('reunions/<int:pk>/statut/', views.changer_statut_reunion,
         name='changer_statut_reunion'),
]