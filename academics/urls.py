from django.urls import path
from . import views

urlpatterns = [
    path('', views.academics, name='academics'),
    path('admissions/', views.admissions, name='admissions'),
    path('events/', views.events, name='events'),
    path('results/', views.results, name='results'),
]
