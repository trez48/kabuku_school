from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Combination, ExamResult, Event, AdmissionApplication


def academics(request):
    combinations = Combination.objects.all()
    return render(request, 'academics/academics.html', {'combinations': combinations})


def admissions(request):
    combinations = Combination.objects.all()
    if request.method == 'POST':
        # Validate required fields before saving
        required_fields = ['full_name', 'date_of_birth', 'gender',
                           'previous_school', 'index_number', 'combination',
                           'parent_name', 'parent_phone', 'address']
        missing = [f for f in required_fields if not request.POST.get(f, '').strip()]
        if missing:
            messages.error(request, 'Please fill in all required fields.')
            return render(request, 'academics/admissions.html', {'combinations': combinations})

        # Validate combination_id is a real Combination (prevents object spoofing)
        combination_id = request.POST.get('combination', '')
        if not Combination.objects.filter(pk=combination_id).exists():
            messages.error(request, 'Invalid combination selected.')
            return render(request, 'academics/admissions.html', {'combinations': combinations})

        AdmissionApplication.objects.create(
            full_name=request.POST['full_name'].strip(),
            date_of_birth=request.POST['date_of_birth'].strip(),
            gender=request.POST['gender'].strip(),
            previous_school=request.POST['previous_school'].strip(),
            index_number=request.POST['index_number'].strip(),
            combination_choice_id=combination_id,
            parent_name=request.POST['parent_name'].strip(),
            parent_phone=request.POST['parent_phone'].strip(),
            parent_email=request.POST.get('parent_email', '').strip(),
            address=request.POST['address'].strip(),
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
