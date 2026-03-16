from django.urls import path
from . import views_edt

urlpatterns = [
    path('grilles/', views_edt.liste_grilles, name='liste_grilles'),
    path('grilles/creer/', views_edt.creer_grille, name='creer_grille'),
    path('grilles/<int:pk>/', views_edt.detail_grille, name='detail_grille'),
    path('grilles/<int:grille_pk>/creneau/', views_edt.ajouter_creneau,
         name='ajouter_creneau'),
    path('creneaux/<int:pk>/supprimer/', views_edt.supprimer_creneau,
         name='supprimer_creneau'),
    path('salle/<int:salle_pk>/', views_edt.edt_salle, name='edt_salle'),
    path('salle/<int:salle_pk>/modifier/', views_edt.modifier_slot_edt,
         name='modifier_slot_edt'),
    path('salle/<int:salle_pk>/publier/', views_edt.publier_edt,
         name='publier_edt'),
    path('salle/<int:salle_pk>/reinitialiser/', views_edt.reinitialiser_edt,
         name='reinitialiser_edt'),
    path('professeur/', views_edt.edt_professeur, name='edt_professeur'),
    path('professeur/<int:prof_pk>/', views_edt.edt_professeur,
         name='edt_professeur_detail'),
    path('professeur/<int:prof_pk>/disponibilites/',
         views_edt.disponibilites_prof, name='disponibilites_prof'),
]