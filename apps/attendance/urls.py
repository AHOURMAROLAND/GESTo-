from django.urls import path
from . import views

urlpatterns = [
    path('', views.liste_seances, name='liste_seances'),
    path('nouvelle/', views.nouvelle_seance, name='nouvelle_seance'),
    path('<int:pk>/', views.detail_seance, name='detail_seance'),
    path('<int:pk>/pointer/', views.pointer_presence, name='pointer_presence'),
    path('absences/', views.liste_absences, name='liste_absences'),
    path('absences/<int:pk>/justifier/', views.justifier_absence,
         name='justifier_absence'),
    path('eleve/<int:eleve_pk>/', views.absences_eleve, name='absences_eleve'),
    path('rapport/', views.rapport_journalier, name='rapport_journalier'),
]