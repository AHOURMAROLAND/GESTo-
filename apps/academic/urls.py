from django.urls import path
from . import views

urlpatterns = [
    # Salles
    path('', views.liste_salles, name='liste_salles'),
    path('nouvelle/', views.nouvelle_salle, name='nouvelle_salle'),
    path('<int:pk>/', views.detail_salle, name='detail_salle'),
    path('<int:pk>/modifier/', views.modifier_salle, name='modifier_salle'),
    path('<int:pk>/supprimer/', views.supprimer_salle, name='supprimer_salle'),
    # Matieres globales
    path('matieres/', views.liste_matieres, name='liste_matieres'),
    path('matieres/nouvelle/', views.nouvelle_matiere, name='nouvelle_matiere'),
    path('matieres/<int:pk>/supprimer/', views.supprimer_matiere,
         name='supprimer_matiere'),
    # Matieres par salle
    path('<int:salle_pk>/matieres/ajouter/', views.ajouter_matiere_salle,
         name='ajouter_matiere_salle'),
    path('matieres-salle/<int:pk>/modifier/', views.modifier_matiere_salle,
         name='modifier_matiere_salle'),
    path('matieres-salle/<int:pk>/supprimer/', views.supprimer_matiere_salle,
         name='supprimer_matiere_salle'),
]