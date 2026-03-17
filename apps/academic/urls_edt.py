from django.urls import path
from . import views_edt

urlpatterns = [
    path('', views_edt.vue_edt, name='vue_edt'),
    path('gestion/', views_edt.gestion_edt, name='gestion_edt'),
    path('assigner/', views_edt.assigner_creneau, name='assigner_creneau'),
    path('assigner/slot/', views_edt.modifier_slot_edt, name='modifier_slot_edt'),
    path('init/<int:salle_pk>/', views_edt.initialiser_grille, name='initialiser_grille'),
    path('pdf/<int:salle_pk>/', views_edt.edt_pdf, name='edt_pdf'),
    path('salle/<int:salle_pk>/publier/', views_edt.publier_edt, name='publier_edt'),
    path('salle/<int:salle_pk>/reinitialiser/', views_edt.reinitialiser_edt, name='reinitialiser_edt'),

    # Grilles (Time slot grids for levels)
    path('grilles/', views_edt.liste_grilles, name='liste_grilles'),
    path('grilles/creer/', views_edt.creer_grille, name='creer_grille'),
    path('grilles/<int:pk>/', views_edt.detail_grille, name='detail_grille'),
    path('grilles/<int:pk>/ajouter-creneau/', views_edt.ajouter_creneau, name='ajouter_creneau'),
    path('creneaux/<int:pk>/supprimer/', views_edt.supprimer_creneau, name='supprimer_creneau'),

    # Salle & Prof shortcuts
    path('salle/<int:pk>/', views_edt.edt_salle, name='edt_salle'),
    path('mon-edt/', views_edt.edt_professeur, name='edt_professeur'),
    path('prof/<int:prof_pk>/', views_edt.edt_professeur_detail, name='edt_professeur_detail'),
    path('prof/<int:prof_pk>/disponibilites/', views_edt.disponibilites_prof, name='disponibilites_prof'),
]