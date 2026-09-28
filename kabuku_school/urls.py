from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('accounts/', include('accounts.urls')),
    path('academics/', include('academics.urls')),
    path('news/', include('news.urls')),
    path('gallery/', include('gallery.urls')),
    path('teacher/', include('teacher.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static('/student-photos/', document_root=settings.STUDENT_PHOTOS_DIR)

# Custom error handlers
handler404 = 'kabuku_school.views.error_404'
handler500 = 'kabuku_school.views.error_500'
