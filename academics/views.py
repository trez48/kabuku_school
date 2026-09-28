from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Combination, ExamResult, Event, AdmissionApplication


def academics(request):
    combinations = Combination.objects.all()
    return render(request, 'academics/academics.html', {'combinations': combinations})


def admissions(request):
    combinations = Combination.objects.all()
    if request.method == 'POST':
        AdmissionApplication.objects.create(
            full_name=request.POST['full_name'],
            date_of_birth=request.POST['date_of_birth'],
            gender=request.POST['gender'],
            previous_school=request.POST['previous_school'],
            index_number=request.POST['index_number'],
            combination_choice_id=request.POST['combination'],
            parent_name=request.POST['parent_name'],
            parent_phone=request.POST['parent_phone'],
            parent_email=request.POST.get('parent_email', ''),
            address=request.POST['address'],
        )
        messages.success(request, 'Application submitted successfully! You will receive a GePG control number for payment.')
        return redirect('admissions')
    return render(request, 'academics/admissions.html', {'combinations': combinations})


def events(request):
    events_list = Event.objects.all()
    return render(request, 'academics/events.html', {'events': events_list})


def results(request):
    results_list = None
    if request.GET.get('admission_number'):
        results_list = ExamResult.objects.filter(
            admission_number=request.GET['admission_number'], published=True
        )
    return render(request, 'academics/results.html', {'results': results_list})
