from django.urls import path
from . import views

urlpatterns = [
    # Public — sans login
    path('', views.formulaire_preinscription,
         name='formulaire_preinscription'),
    path('confirmation/<str:ref>/',
         views.confirmation_preinscription,
         name='confirmation_preinscription'),
    # Admin — avec login
    path('admin/', views.liste_preinscriptions,
         name='liste_preinscriptions'),
    path('admin/<int:pk>/', views.detail_preinscription,
         name='detail_preinscription'),
    path('admin/<int:pk>/valider/', views.valider_preinscription,
         name='valider_preinscription'),
    path('admin/<int:pk>/rejeter/', views.rejeter_preinscription,
         name='rejeter_preinscription'),
]
