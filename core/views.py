import os
from django.shortcuts import render, redirect
from django.contrib import messages
from django.conf import settings
from .models import SliderImage, Staff, ContactMessage
from news.models import NewsPost
from academics.models import Event


def home(request):
    from django.db import connection, OperationalError as DjOperationalError
    try:
        sliders = list(SliderImage.objects.filter(active=True))
        latest_news = list(NewsPost.objects.filter(published=True)[:3])
        upcoming_events = list(Event.objects.order_by('date')[:5])
    except DjOperationalError:
        # Database not yet migrated (e.g. fresh Railway deploy)
        sliders = []
        latest_news = []
        upcoming_events = []
    # Student photos slideshow
    photos_dir = settings.STUDENT_PHOTOS_DIR
    student_photos = []
    if photos_dir.exists():
        student_photos = [f'/student-photos/{f}' for f in os.listdir(photos_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    return render(request, 'core/home.html', {
        'sliders': sliders,
        'latest_news': latest_news,
        'upcoming_events': upcoming_events,
        'student_photos': student_photos,
    })


def about(request):
    headmaster = Staff.objects.filter(role='headmaster').first()
    return render(request, 'core/about.html', {'headmaster': headmaster})


def staff_list(request):
    staff = Staff.objects.all()
    return render(request, 'core/staff.html', {'staff': staff})


def contact(request):
    if request.method == 'POST':
        ContactMessage.objects.create(
            name=request.POST['name'],
            email=request.POST['email'],
            subject=request.POST['subject'],
            message=request.POST['message'],
        )
        messages.success(request, 'Your message has been sent successfully!')
        return redirect('contact')
    return render(request, 'core/contact.html')
