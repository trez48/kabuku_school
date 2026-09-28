from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('student', 'Student'),
        ('parent', 'Parent'),
        ('teacher', 'Teacher'),
        ('admin', 'Admin'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    phone = models.CharField(max_length=20, blank=True)
    admission_number = models.CharField(max_length=50, blank=True, null=True, unique=True)
    parent_of = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        limit_choices_to={'role': 'student'}
    )
    # Forces user to change password on first login
    must_change_password = models.BooleanField(
        default=True,
        help_text='If True, user will be required to change password on next login.'
    )

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.role})"
