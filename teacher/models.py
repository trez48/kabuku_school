from django.db import models
from django.contrib.auth.models import User
from academics.models import Combination


class Subject(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10)
    combination = models.ForeignKey(Combination, on_delete=models.CASCADE, related_name='subjects_list')
    teacher = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='subjects_taught')

    def __str__(self):
        return f"{self.name} ({self.code})"


class ClassRoom(models.Model):
    name = models.CharField(max_length=50)  # e.g. Form 5 PGM, Form 6 PCM
    combination = models.ForeignKey(Combination, on_delete=models.CASCADE)
    class_teacher = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    year = models.IntegerField(default=2026)

    def __str__(self):
        return self.name


class StudentEnrollment(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='enrollments')
    classroom = models.ForeignKey(ClassRoom, on_delete=models.CASCADE, related_name='students')
    enrolled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['student', 'classroom']

    def __str__(self):
        return f"{self.student.get_full_name()} - {self.classroom.name}"


class Mark(models.Model):
    EXAM_TYPE_CHOICES = [
        ('ca', 'Continuous Assessment'),
        ('midterm', 'Midterm Exam'),
        ('terminal', 'Terminal Exam'),
        ('mock', 'Mock Exam'),
        ('practical', 'Practical'),
    ]
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='marks')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    classroom = models.ForeignKey(ClassRoom, on_delete=models.CASCADE)
    exam_type = models.CharField(max_length=10, choices=EXAM_TYPE_CHOICES)
    score = models.DecimalField(max_digits=5, decimal_places=2)
    max_score = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    term = models.CharField(max_length=20, default='Term 1')
    year = models.IntegerField(default=2026)
    entered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='marks_entered')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['student', 'subject', 'exam_type', 'term', 'year']
        ordering = ['-year', 'term', 'student']

    def __str__(self):
        return f"{self.student.get_full_name()} - {self.subject.code} - {self.exam_type}: {self.score}"

    @property
    def percentage(self):
        return round((self.score / self.max_score) * 100, 1)

    @property
    def grade(self):
        pct = self.percentage
        if pct >= 75: return 'A'
        elif pct >= 65: return 'B'
        elif pct >= 45: return 'C'
        elif pct >= 30: return 'D'
        else: return 'F'


class Attendance(models.Model):
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
        ('excused', 'Excused'),
    ]
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attendance_records')
    classroom = models.ForeignKey(ClassRoom, on_delete=models.CASCADE)
    date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='present')
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='attendance_recorded')

    class Meta:
        unique_together = ['student', 'classroom', 'date']
        ordering = ['-date']

    def __str__(self):
        return f"{self.student.get_full_name()} - {self.date} - {self.status}"


class Assignment(models.Model):
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    classroom = models.ForeignKey(ClassRoom, on_delete=models.CASCADE)
    file = models.FileField(upload_to='assignments/', blank=True)
    deadline = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class Note(models.Model):
    title = models.CharField(max_length=300)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    classroom = models.ForeignKey(ClassRoom, on_delete=models.CASCADE)
    file = models.FileField(upload_to='notes/')
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return self.title


class Timetable(models.Model):
    DAY_CHOICES = [
        ('mon', 'Monday'), ('tue', 'Tuesday'), ('wed', 'Wednesday'),
        ('thu', 'Thursday'), ('fri', 'Friday'),
    ]
    classroom = models.ForeignKey(ClassRoom, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    teacher = models.ForeignKey(User, on_delete=models.CASCADE)
    day = models.CharField(max_length=3, choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ['day', 'start_time']

    def __str__(self):
        return f"{self.day} {self.start_time}-{self.end_time}: {self.subject.code}"


class FeeRecord(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='fee_records')
    description = models.CharField(max_length=200)  # e.g. "Term 1 Fees 2026"
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gepg_control_number = models.CharField(max_length=50, blank=True)
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def balance(self):
        return self.amount - self.paid

    @property
    def is_paid(self):
        return self.paid >= self.amount

    def __str__(self):
        return f"{self.student.get_full_name()} - {self.description}"


class Notification(models.Model):
    TYPE_CHOICES = [
        ('result', 'New Result'),
        ('absence', 'Absence Alert'),
        ('fee', 'Fee Reminder'),
        ('announcement', 'Announcement'),
        ('assignment', 'Assignment'),
    ]
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=300)
    message = models.TextField()
    notification_type = models.CharField(max_length=15, choices=TYPE_CHOICES, default='announcement')
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.recipient.get_full_name()} - {self.title}"
