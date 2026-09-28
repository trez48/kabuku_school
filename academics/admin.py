from django.contrib import admin
from .models import Combination, ExamResult, Event, AdmissionApplication


@admin.register(Combination)
class CombinationAdmin(admin.ModelAdmin):
    list_display = ['code', 'name']


@admin.register(ExamResult)
class ExamResultAdmin(admin.ModelAdmin):
    list_display = ['student_name', 'admission_number', 'combination', 'exam_name', 'year', 'published']
    list_filter = ['year', 'combination', 'published']
    search_fields = ['student_name', 'admission_number']


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['title', 'date', 'location']
    list_filter = ['date']


@admin.register(AdmissionApplication)
class AdmissionApplicationAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'combination_choice', 'status', 'payment_status', 'applied_at']
    list_filter = ['status', 'payment_status']
    search_fields = ['full_name', 'index_number']
