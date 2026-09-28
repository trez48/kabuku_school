from django.urls import path
from . import views

urlpatterns = [
    path('', views.teacher_dashboard, name='teacher_dashboard'),
    path('classes/', views.my_classes, name='teacher_classes'),
    path('classes/<int:pk>/students/', views.class_students, name='class_students'),
    path('classes/<int:class_pk>/marks/', views.enter_marks, name='enter_marks'),
    path('classes/<int:class_pk>/marks/view/', views.view_marks, name='view_marks'),
    path('classes/<int:class_pk>/attendance/', views.take_attendance, name='take_attendance'),
    path('classes/<int:class_pk>/attendance/report/', views.attendance_report, name='attendance_report'),
    path('assignments/', views.teacher_assignments, name='teacher_assignments'),
    path('assignments/upload/', views.upload_assignment, name='upload_assignment'),
    path('notes/', views.teacher_notes, name='teacher_notes'),
    path('notes/upload/', views.upload_note, name='upload_note'),
    path('timetable/', views.timetable, name='teacher_timetable'),
]
