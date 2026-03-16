from django.urls import path
from . import views

urlpatterns = [
    path('', views.liste_sanctions, name='liste_sanctions'),
    path('nouvelle/', views.nouvelle_sanction, name='nouvelle_sanction'),
    path('<int:pk>/', views.detail_sanction, name='detail_sanction'),
    path('<int:pk>/traiter/', views.traiter_sanction, name='traiter_sanction'),
    path('exclusions/', views.liste_exclusions, name='liste_exclusions'),
    path('exclusions/nouvelle/', views.nouvelle_exclusion,
         name='nouvelle_exclusion'),
    path('exclusions/<int:pk>/', views.detail_exclusion,
         name='detail_exclusion'),
    path('exclusions/<int:pk>/traiter/', views.traiter_exclusion,
         name='traiter_exclusion'),
    path('types/', views.liste_types_sanctions,
         name='liste_types_sanctions'),
    path('eleve/<int:eleve_pk>/', views.dossier_disciplinaire,
         name='dossier_disciplinaire'),
    path('<int:pk>/convocation/', views.convocation_parent,
         name='convocation_parent'),
]