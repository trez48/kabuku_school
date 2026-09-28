from django.contrib import admin
from .models import Subject, ClassRoom, StudentEnrollment, Mark, Attendance, Assignment, Note, Timetable


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'combination', 'teacher']
    list_filter = ['combination']


@admin.register(ClassRoom)
class ClassRoomAdmin(admin.ModelAdmin):
    list_display = ['name', 'combination', 'class_teacher', 'year']


@admin.register(StudentEnrollment)
class StudentEnrollmentAdmin(admin.ModelAdmin):
    list_display = ['student', 'classroom']
    list_filter = ['classroom']


@admin.register(Mark)
class MarkAdmin(admin.ModelAdmin):
    list_display = ['student', 'subject', 'exam_type', 'score', 'term', 'year']
    list_filter = ['exam_type', 'subject', 'year']


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ['student', 'classroom', 'date', 'status']
    list_filter = ['status', 'date']


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ['title', 'subject', 'classroom', 'deadline']


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ['title', 'subject', 'classroom', 'uploaded_at']


@admin.register(Timetable)
class TimetableAdmin(admin.ModelAdmin):
    list_display = ['classroom', 'subject', 'teacher', 'day', 'start_time', 'end_time']
    list_filter = ['day', 'teacher']
