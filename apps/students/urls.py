from django.urls import path
from . import views

urlpatterns = [
    path('', views.liste_eleves, name='liste_eleves'),
    path('nouveau/', views.nouvel_eleve, name='nouvel_eleve'),
    path('nouveau/', views.nouvel_eleve, name='nouveau_eleve'),  # alias
    path('<int:pk>/', views.detail_eleve, name='detail_eleve'),
    path('<int:pk>/modifier/', views.modifier_eleve, name='modifier_eleve'),
    path('<int:pk>/transferer/', views.transferer_eleve, name='transferer_eleve'),
    path('<int:eleve_pk>/parents/ajouter/', views.ajouter_parent,
         name='ajouter_parent'),
    path('<int:eleve_pk>/parents/<int:parent_pk>/retirer/', views.retirer_parent,
         name='retirer_parent'),
    path('export/excel/', views.export_eleves_excel, name='export_eleves_excel'),
    path('export/pdf/', views.export_eleves_pdf, name='export_eleves_pdf'),
    path('mes-enfants/', views.mes_enfants, name='mes_enfants'),
    path('api/verifier-wa/', views.verifier_numero_wa, name='verifier_numero_wa'),
]