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
]