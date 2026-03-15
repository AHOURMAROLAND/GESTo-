from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.authentication.urls')),
    path('', include('apps.core.urls')),
    path('eleves/', include('apps.students.urls')),
    path('salles/', include('apps.academic.urls')),
    path('notes/', include('apps.grades.urls')),
    path('presences/', include('apps.attendance.urls')),
    path('finance/', include('apps.finance.urls')),
    path('discipline/', include('apps.discipline.urls')),
    path('messagerie/', include('apps.communication.urls')),
    path('documents/', include('apps.documents.urls')),
    path('emploi-du-temps/', include('apps.academic.urls_edt')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)