from django.urls import path
from . import views

urlpatterns = [
    path('', views.liste_documents, name='liste_documents'),
    path('config/', views.modifier_config_documents,
         name='modifier_config_documents'),
    path('certificat/<int:eleve_pk>/', views.generer_certificat,
         name='generer_certificat'),
    path('certificat/reprint/<int:pk>/', views.reimprimer_certificat,
         name='reimprimer_certificat'),
    path('attestation/<int:eleve_pk>/', views.attestation_pdf,
         name='attestation_pdf'),
    path('eleves/pdf/', views.export_liste_eleves_pdf,
         name='export_liste_eleves_pdf'),
    path('eleves/excel/', views.export_liste_eleves_excel,
         name='export_liste_eleves_excel'),
    path('bilan/pdf/', views.bilan_annuel_pdf, name='bilan_annuel_pdf'),
]