from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.custom_login, name='login'),
    path('logout/', views.custom_logout, name='logout'),
    path('profil/', views.profil, name='profil'),
    path('changer-mot-de-passe/', views.changer_mot_de_passe, name='changer_mot_de_passe'),
    path('personnel/', views.liste_personnel, name='liste_personnel'),
    path('personnel/nouveau/', views.nouveau_personnel, name='nouveau_personnel'),
    path('personnel/<int:pk>/', views.detail_personnel, name='detail_personnel'),
    path('personnel/<int:pk>/modifier/', views.modifier_personnel, name='modifier_personnel'),
    path('personnel/<int:pk>/toggle/', views.toggle_actif, name='toggle_actif'),
]