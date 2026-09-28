from django.contrib import admin
from .models import UserProfile

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'admission_number']
    list_filter = ['role']
    search_fields = ['user__first_name', 'user__last_name', 'admission_number']
