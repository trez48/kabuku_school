from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('staff/', views.staff_list, name='staff'),
    path('contact/', views.contact, name='contact'),
]
