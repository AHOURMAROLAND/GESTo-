from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_finance, name='dashboard_finance'),
    path('tarifs/', views.liste_tarifs, name='liste_tarifs'),
    path('tarifs/creer/', views.creer_tarif, name='creer_tarif'),
    path('tarifs/init/', views.initialiser_types_frais, name='init_types_frais'),
    path('collectes/', views.liste_collectes, name='liste_collectes'),
    path('collectes/nouvelle/', views.nouvelle_collecte,
         name='nouvelle_collecte'),
    path('paiements/', views.liste_paiements, name='liste_paiements'),
    path('paiements/nouveau/', views.nouveau_paiement,
         name='nouveau_paiement'),
    path('recu/<int:pk>/', views.recu_paiement, name='recu_paiement'),
    path('recu/<int:pk>/pdf/', views.recu_pdf, name='recu_pdf'),
    path('depenses/', views.liste_depenses, name='liste_depenses'),
    path('depenses/nouvelle/', views.nouvelle_depense,
         name='nouvelle_depense'),
    path('recouvrement/', views.etat_recouvrement,
         name='etat_recouvrement'),
    path('eleve/<int:eleve_pk>/', views.frais_eleve, name='frais_eleve'),
    path('eleve/<int:eleve_pk>/ajouter/', views.ajouter_frais,
         name='ajouter_frais'),
    path('api/frais/', views.api_frais_eleve, name='api_frais_eleve'),
    path('api/eleves/', views.api_eleves_salle, name='api_eleves_salle'),
]