from django.contrib import admin
from .models import SliderImage, Staff, ContactMessage

admin.site.site_header = "Kabuku Secondary School Admin"
admin.site.site_title = "Kabuku Admin"


@admin.register(SliderImage)
class SliderImageAdmin(admin.ModelAdmin):
    list_display = ['title', 'active']


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ['name', 'role', 'subject']
    list_filter = ['role']


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ['name', 'subject', 'created_at', 'read']
    list_filter = ['read']
