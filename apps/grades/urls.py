from django.urls import path
from . import views
from . import views_examens
from . import views_bulletins

urlpatterns = [
    # Evaluations
    path('', views.liste_evaluations, name='liste_evaluations'),
    path('nouvelle/', views.nouvelle_evaluation, name='nouvelle_evaluation'),
    path('<int:pk>/', views.detail_evaluation, name='detail_evaluation'),
    path('<int:pk>/valider/', views.valider_evaluation,
         name='valider_evaluation'),
    path('<int:pk>/assigner/', views.assigner_saisisseur,
         name='assigner_saisisseur'),
    path('<int:pk>/saisir/', views.saisir_notes, name='saisir_notes'),
    path('<int:pk>/valider-notes/', views.valider_notes, name='valider_notes'),
    path('<int:pk>/supprimer/', views.supprimer_evaluation,
         name='supprimer_evaluation'),
    path('mes-taches/', views.mes_taches_saisie, name='mes_taches_saisie'),
    # Examens
    path('examens/', views_examens.liste_examens, name='liste_examens'),
    path('examens/nouveau/', views_examens.nouvel_examen, name='nouvel_examen'),
    path('examens/<int:pk>/', views_examens.detail_examen,
         name='detail_examen'),
    path('examens/<int:pk>/demarrer/', views_examens.demarrer_examen,
         name='demarrer_examen'),
    path('examens/<int:pk>/assigner/', views_examens.assigner_saisie_examen,
         name='assigner_saisie_examen'),
    path('examens/<int:examen_pk>/matiere/<int:matiere_pk>/saisir/',
         views_examens.saisir_notes_examen, name='saisir_notes_examen'),
    path('examens/<int:pk>/valider/', views_examens.valider_examen,
         name='valider_examen'),
    path('examens/<int:pk>/supprimer/', views_examens.supprimer_examen,
         name='supprimer_examen'),
    # Bulletins
    path('bulletins/', views.bulletins_salle, name='bulletins_salle'),
    path('bulletins/eleve/<int:eleve_pk>/periode/<int:periode_pk>/pdf/',
         views.bulletin_pdf, name='bulletin_pdf'),
    path('bulletins/salle/<int:salle_pk>/periode/<int:periode_pk>/pdf/',
         views.bulletins_salle_pdf, name='bulletins_salle_pdf'),
    path('proclamation/', views.proclamation, name='proclamation'),
    path('proclamation/<int:salle_pk>/<int:periode_pk>/pdf/',
         views.proclamation_pdf, name='proclamation_pdf'),
    # Gestion bulletins (views_bulletins)
    path('bulletins/gestion/', views_bulletins.gestion_bulletins, name='gestion_bulletins'),
    path('bulletins/calculer/', views_bulletins.calculer_moyennes, name='calculer_moyennes'),
    path('bulletins/salle/<int:salle_pk>/periode/<int:periode_pk>/',
         views_bulletins.liste_bulletins_salle, name='liste_bulletins_salle'),
    path('bulletins/eleve/<int:eleve_pk>/periode/<int:periode_pk>/apercu/',
         views_bulletins.apercu_bulletin, name='apercu_bulletin'),
    path('bulletins/eleve/<int:eleve_pk>/periode/<int:periode_pk>/generer/',
         views_bulletins.generer_bulletin_pdf, name='generer_bulletin_pdf'),
    path('bulletins/salle/<int:salle_pk>/periode/<int:periode_pk>/generer/',
         views_bulletins.generer_bulletins_salle_pdf, name='generer_bulletins_salle_pdf'),
]