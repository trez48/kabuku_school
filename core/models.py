from django.db import models


class SliderImage(models.Model):
    title = models.CharField(max_length=200)
    image = models.ImageField(upload_to='slider/')
    caption = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.title


class Staff(models.Model):
    ROLE_CHOICES = [
        ('headmaster', 'Headmaster'),
        ('teacher', 'Teacher'),
        ('admin_staff', 'Administrative Staff'),
    ]
    name = models.CharField(max_length=200)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    subject = models.CharField(max_length=100, blank=True)
    qualification = models.CharField(max_length=200, blank=True, help_text="e.g. B.Sc Physics, M.Ed")
    experience = models.CharField(max_length=100, blank=True, help_text="e.g. 10 years")
    bio = models.TextField(blank=True, help_text="Short biography")
    photo = models.ImageField(upload_to='staff/', blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)

    class Meta:
        verbose_name_plural = "Staff"
        ordering = ['role', 'name']

    def __str__(self):
        return f"{self.name} - {self.get_role_display()}"


class ContactMessage(models.Model):
    name = models.CharField(max_length=200)
    email = models.EmailField()
    subject = models.CharField(max_length=300)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} - {self.subject}"
