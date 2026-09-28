from django.db import models


class Combination(models.Model):
    code = models.CharField(max_length=10)
    name = models.CharField(max_length=200)
    subjects = models.TextField(help_text="Comma-separated list of subjects")

    def __str__(self):
        return f"{self.code} - {self.name}"


class ExamResult(models.Model):
    student_name = models.CharField(max_length=200)
    admission_number = models.CharField(max_length=50)
    combination = models.ForeignKey(Combination, on_delete=models.CASCADE)
    exam_name = models.CharField(max_length=200)
    year = models.IntegerField()
    results = models.TextField(help_text="Subject:Grade pairs, one per line")
    gpa = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    published = models.BooleanField(default=False)

    class Meta:
        ordering = ['-year', 'student_name']

    def __str__(self):
        return f"{self.student_name} - {self.exam_name} ({self.year})"


class Event(models.Model):
    title = models.CharField(max_length=300)
    description = models.TextField()
    date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    location = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.title} - {self.date}"


class AdmissionApplication(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    full_name = models.CharField(max_length=200)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=10, choices=[('M', 'Male'), ('F', 'Female')])
    previous_school = models.CharField(max_length=200)
    index_number = models.CharField(max_length=50)
    combination_choice = models.ForeignKey(Combination, on_delete=models.CASCADE)
    parent_name = models.CharField(max_length=200)
    parent_phone = models.CharField(max_length=20)
    parent_email = models.EmailField(blank=True)
    address = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    gepg_control_number = models.CharField(max_length=50, blank=True)
    payment_status = models.BooleanField(default=False)
    applied_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.full_name} - {self.status}"
