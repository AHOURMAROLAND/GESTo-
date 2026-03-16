from django.urls import path
from . import views

urlpatterns = [
    path('', views.liste_evaluations, name='liste_evaluations'),
    path('nouvelle/', views.nouvelle_evaluation, name='nouvelle_evaluation'),
    path('<int:pk>/', views.detail_evaluation, name='detail_evaluation'),
    path('<int:pk>/valider/', views.valider_evaluation, name='valider_evaluation'),
    path('<int:pk>/assigner/', views.assigner_saisisseur,
         name='assigner_saisisseur'),
    path('<int:pk>/saisir/', views.saisir_notes, name='saisir_notes'),
    path('<int:pk>/valider-notes/', views.valider_notes, name='valider_notes'),
    path('<int:pk>/supprimer/', views.supprimer_evaluation,
         name='supprimer_evaluation'),
]