from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('parametres/', views.parametres, name='parametres'),
    path('parametres/ecole/modifier/', views.modifier_config_ecole,
         name='modifier_config_ecole'),
    path('parametres/annees/', views.liste_annees, name='liste_annees'),
    path('parametres/annees/nouvelle/', views.nouvelle_annee, name='nouvelle_annee'),
    path('parametres/annees/<int:pk>/activer/', views.activer_annee,
         name='activer_annee'),
    path('parametres/periodes/', views.liste_periodes, name='liste_periodes'),
    path('parametres/periodes/nouvelle/', views.nouvelle_periode,
         name='nouvelle_periode'),
    path('parametres/periodes/<int:pk>/activer/', views.activer_periode,
         name='activer_periode'),
    path('parametres/niveaux/', views.liste_niveaux, name='liste_niveaux'),
    path('parametres/niveaux/nouveau/', views.nouveau_niveau, name='nouveau_niveau'),
    path('parametres/niveaux/<int:pk>/modifier/', views.modifier_niveau,
         name='modifier_niveau'),
    path('parametres/niveaux/<int:pk>/supprimer/', views.supprimer_niveau,
         name='supprimer_niveau'),
    path('parametres/niveaux/<int:niveau_pk>/groupes/', views.groupes_matieres,
         name='groupes_matieres'),
]