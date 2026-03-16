from django.urls import path
from . import views

urlpatterns = [
    path('', views.liste_devoirs, name='liste_devoirs'),
    path('nouveau/', views.nouveau_devoir, name='nouveau_devoir'),
    path('<int:pk>/', views.detail_devoir, name='detail_devoir'),
    path('<int:pk>/soumettre/', views.soumettre_devoir,
         name='soumettre_devoir'),
    path('<int:pk>/clore/', views.clore_devoir, name='clore_devoir'),
    path('soumission/<int:pk>/corriger/', views.corriger_soumission,
         name='corriger_soumission'),
    path('mes-soumissions/', views.mes_soumissions,
         name='mes_soumissions'),
]
