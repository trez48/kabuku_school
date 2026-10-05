from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse

from .models import UserProfile
from academics.models import ExamResult, Combination, Event, AdmissionApplication
from news.models import NewsPost
from core.models import Staff, ContactMessage, SliderImage
from gallery.models import Album, Photo
from teacher.models import ClassRoom, Subject, StudentEnrollment, Timetable, FeeRecord, Notification
from kabuku_school.utils import admin_required, validate_upload, safe_filename


# ── Shared helper ─────────────────────────────────────────────────────────────

_SUBJECT_COLORS = {
    'PHY': '#4361ee', 'MAT': '#f72585', 'GEO': '#0077b6',
    'CHE': '#7209b7', 'BIO': '#06d6a0', 'ENG': '#fb8500',
}
_PRINT_PERIODS = [
    {'label': '07:30-08:30', 'start': '07:30', 'is_break': False},
    {'label': '08:30-09:30', 'start': '08:30', 'is_break': False},
    {'label': '09:30-10:30', 'start': '09:30', 'is_break': False},
    {'label': '☕ Break — 10:30 to 11:00', 'is_break': True},
    {'label': '11:00-12:00', 'start': '11:00', 'is_break': False},
    {'label': '12:00-13:00', 'start': '12:00', 'is_break': False},
    {'label': '🍽️ Lunch — 13:00 to 14:00', 'is_break': True},
    {'label': '14:00-15:00', 'start': '14:00', 'is_break': False},
    {'label': '15:00-16:00', 'start': '15:00', 'is_break': False},
]
_DAYS = ['mon', 'tue', 'wed', 'thu', 'fri']


def _build_print_periods(timetable_qs):
    """Build grid rows for printable timetable. Each row has 5 cells (Mon-Fri)."""
    # Index: (day, start_time_str) → slot
    slot_index = {}
    for s in timetable_qs:
        slot_index[(s.day, s.start_time.strftime('%H:%M'))] = s

    rows = []
    for period in _PRINT_PERIODS:
        if period['is_break']:
            rows.append({'is_break': True, 'label': period['label']})
        else:
            cells = []
            for day in _DAYS:
                slot = slot_index.get((day, period['start']))
                if slot:
                    cells.append({
                        'code': slot.subject.code,
                        'name': slot.subject.name,
                        'teacher': slot.teacher.get_full_name(),
                        'color': _SUBJECT_COLORS.get(slot.subject.code, '#6c757d'),
                    })
                else:
                    cells.append(None)
            rows.append({'is_break': False, 'label': period['label'], 'cells': cells})
    return rows


# ── Auth ─────────────────────────────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        if not username or not password:
            messages.error(request, 'Please enter both username and password.')
            return render(request, 'accounts/login.html')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('dashboard')
        messages.error(request, 'Invalid username or password.')
    return render(request, 'accounts/login.html')


def logout_view(request):
    logout(request)
    return redirect('home')


@login_required
def change_password(request):
    """
    Handles both:
    - Forced first-login password change (must_change_password=True)
    - Voluntary password change from any dashboard
    """
    profile = UserProfile.objects.filter(user=request.user).first()
    is_forced = profile and profile.must_change_password

    if request.method == 'POST':
        current_password = request.POST.get('current_password', '')
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')

        # For forced change, skip current password check only if it's first login
        if not is_forced:
            if not request.user.check_password(current_password):
                messages.error(request, 'Your current password is incorrect.')
                return render(request, 'accounts/change_password.html', {'is_forced': is_forced})

        if len(new_password) < 8:
            messages.error(request, 'New password must be at least 8 characters long.')
            return render(request, 'accounts/change_password.html', {'is_forced': is_forced})

        if new_password != confirm_password:
            messages.error(request, 'New passwords do not match.')
            return render(request, 'accounts/change_password.html', {'is_forced': is_forced})

        if is_forced and new_password == current_password:
            messages.error(request, 'Your new password must be different from the temporary password.')
            return render(request, 'accounts/change_password.html', {'is_forced': is_forced})

        # Save new password
        request.user.set_password(new_password)
        request.user.save()

        # Clear the forced flag
        if profile:
            profile.must_change_password = False
            profile.save()

        # Re-authenticate so session stays valid after password change
        from django.contrib.auth import update_session_auth_hash
        update_session_auth_hash(request, request.user)

        messages.success(request, 'Password changed successfully!')
        return redirect('dashboard')

    return render(request, 'accounts/change_password.html', {'is_forced': is_forced})


# ── Dashboard router ──────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    profile = UserProfile.objects.filter(user=request.user).first()
    context = {'profile': profile}

    if request.user.is_superuser or (profile and profile.role == 'admin'):
        from teacher.models import Mark, Attendance, StudentEnrollment, ClassRoom, Subject
        import json
        from django.utils import timezone

        # ── Filter params ─────────────────────────────────────────────────────
        current_year = timezone.now().year
        available_years = sorted(
            set(Mark.objects.values_list('year', flat=True)),
            reverse=True
        ) or [current_year]
        available_terms = sorted(
            set(Mark.objects.values_list('term', flat=True))
        )

        sel_year = request.GET.get('year', '')
        sel_term = request.GET.get('term', '')

        # Base mark queryset — apply filters when selected
        marks_base = Mark.objects.all()
        if sel_year:
            marks_base = marks_base.filter(year=sel_year)
        if sel_term:
            marks_base = marks_base.filter(term=sel_term)

        context['available_years'] = available_years
        context['available_terms'] = list(available_terms)
        context['sel_year'] = sel_year
        context['sel_term'] = sel_term

        # ── Basic counts ──────────────────────────────────────────────────────
        context['total_students'] = UserProfile.objects.filter(role='student').count()
        context['total_staff'] = Staff.objects.count()
        context['total_applications'] = AdmissionApplication.objects.count()
        context['pending_applications'] = AdmissionApplication.objects.filter(status='pending').count()
        context['unread_messages'] = ContactMessage.objects.filter(read=False).count()
        context['total_news'] = NewsPost.objects.count()

        # ── School-wide attendance rate (filtered by year if selected) ────────
        att_all = Attendance.objects.all()
        if sel_year:
            att_all = att_all.filter(date__year=sel_year)
        att_total = att_all.count()
        att_present = att_all.filter(status='present').count()
        context['school_attendance'] = round((att_present / att_total) * 100, 1) if att_total > 0 else 0

        # ── Grade distribution (filtered) ─────────────────────────────────────
        grade_counts = {'A': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0}
        for mark in marks_base:
            grade_counts[mark.grade] = grade_counts.get(mark.grade, 0) + 1
        context['grade_data_json'] = json.dumps(list(grade_counts.values()))
        context['grade_labels_json'] = json.dumps(list(grade_counts.keys()))
        context['grade_counts'] = grade_counts

        # ── Exam results by subject: pass/fail/absent (filtered) ──────────────
        subjects = Subject.objects.all()[:6]
        bar_labels, bar_pass, bar_fail, bar_absent = [], [], [], []
        for subj in subjects:
            marks_qs = marks_base.filter(subject=subj)
            enrolled = StudentEnrollment.objects.filter(
                classroom__combination=subj.combination
            ).count()
            passed = sum(1 for m in marks_qs if m.grade in ('A', 'B', 'C'))
            failed = sum(1 for m in marks_qs if m.grade in ('D', 'F'))
            not_attended = max(0, enrolled - marks_qs.count())
            bar_labels.append(subj.code)
            bar_pass.append(passed)
            bar_fail.append(failed)
            bar_absent.append(not_attended)
        context['bar_labels_json'] = json.dumps(bar_labels)
        context['bar_pass_json'] = json.dumps(bar_pass)
        context['bar_fail_json'] = json.dumps(bar_fail)
        context['bar_absent_json'] = json.dumps(bar_absent)

        # ── Average score per subject (filtered) ──────────────────────────────
        subject_avgs = []
        for subj in subjects:
            marks_qs = marks_base.filter(subject=subj)
            if marks_qs.exists():
                avg = sum(m.percentage for m in marks_qs) / marks_qs.count()
                subject_avgs.append({'name': subj.name, 'code': subj.code, 'avg': round(avg, 1)})
        context['subject_avgs'] = subject_avgs

        # ── Students detail table (filtered) ──────────────────────────────────
        student_profiles = UserProfile.objects.filter(role='student').select_related('user')[:20]
        students_detail = []
        for sp in student_profiles:
            user_marks = marks_base.filter(student=sp.user)
            enrollment = StudentEnrollment.objects.filter(student=sp.user).first()
            att_records = Attendance.objects.filter(student=sp.user)
            if sel_year:
                att_records = att_records.filter(date__year=sel_year)
            att_t = att_records.count()
            att_p = att_records.filter(status='present').count()
            att_rate = round((att_p / att_t) * 100, 0) if att_t > 0 else None

            if user_marks.exists():
                avg_pct = sum(m.percentage for m in user_marks) / user_marks.count()
                if avg_pct >= 75: grade = 'A'
                elif avg_pct >= 65: grade = 'B'
                elif avg_pct >= 45: grade = 'C'
                elif avg_pct >= 30: grade = 'D'
                else: grade = 'F'
            else:
                avg_pct, grade = None, '—'

            students_detail.append({
                'name': sp.user.get_full_name() or sp.user.username,
                'admission': sp.admission_number,
                'classroom': enrollment.classroom.name if enrollment else '—',
                'avg': round(avg_pct, 1) if avg_pct is not None else None,
                'grade': grade,
                'attendance': att_rate,
            })
        context['students_detail'] = students_detail

        return render(request, 'accounts/admin_dashboard.html', context)

    elif profile and profile.role == 'teacher':
        return redirect('teacher_dashboard')

    elif profile and profile.role == 'parent' and profile.parent_of:
        from teacher.models import Mark, StudentEnrollment, Assignment, Note, Attendance, FeeRecord, Notification, Timetable

        # ── All children linked to this parent ────────────────────────────────
        all_children = UserProfile.objects.filter(
            role='student', parent_of=profile
        ).select_related('user')
        context['children'] = all_children

        # ── Child switcher: URL ?child=<pk>, default to parent_of ─────────────
        selected_child_pk = request.GET.get('child')
        if selected_child_pk:
            child_profile = all_children.filter(pk=selected_child_pk).first() or profile.parent_of
        else:
            child_profile = profile.parent_of
        child_user = child_profile.user

        context['child'] = child_profile
        context['selected_child_pk'] = str(child_profile.pk)

        # ── Academic results ──────────────────────────────────────────────────
        context['results'] = ExamResult.objects.filter(
            admission_number=child_profile.admission_number, published=True
        )
        context['total_exams'] = context['results'].count()
        context['combination'] = Combination.objects.filter(
            examresult__admission_number=child_profile.admission_number
        ).first()

        # ── Enrollment-based data ─────────────────────────────────────────────
        enrollment = StudentEnrollment.objects.filter(student=child_user).first()
        if enrollment:
            context['classroom'] = enrollment.classroom
            context['combination'] = context.get('combination') or enrollment.classroom.combination
            context['marks'] = Mark.objects.filter(student=child_user).select_related('subject')
            context['assignments'] = Assignment.objects.filter(
                classroom=enrollment.classroom).order_by('-created_at')[:8]
            context['notes'] = Note.objects.filter(
                classroom=enrollment.classroom).order_by('-uploaded_at')[:5]

            # Attendance breakdown
            att_records = Attendance.objects.filter(student=child_user, classroom=enrollment.classroom)
            total_days = att_records.count()
            present_days = att_records.filter(status='present').count()
            absent_days = att_records.filter(status='absent').count()
            late_days = att_records.filter(status='late').count()
            context['attendance_rate'] = round((present_days / total_days) * 100, 1) if total_days > 0 else None
            context['total_days'] = total_days
            context['present_days'] = present_days
            context['absent_days'] = absent_days
            context['late_days'] = late_days

            # Timetable
            days = ['mon', 'tue', 'wed', 'thu', 'fri']
            timetable_qs = Timetable.objects.filter(
                classroom=enrollment.classroom
            ).select_related('subject', 'teacher').order_by('day', 'start_time')
            context['timetable'] = {day: list(timetable_qs.filter(day=day)) for day in days}
            context['print_periods'] = _build_print_periods(timetable_qs)

        # ── Fees ──────────────────────────────────────────────────────────────
        fee_records = FeeRecord.objects.filter(student=child_user)
        context['fees'] = fee_records
        total_fee = sum(f.amount for f in fee_records)
        total_paid = sum(f.paid for f in fee_records)
        context['total_fee'] = total_fee
        context['total_paid'] = total_paid
        context['fee_balance'] = total_fee - total_paid

        # ── Notifications (for the parent account) ────────────────────────────
        context['notifications'] = Notification.objects.filter(recipient=request.user)[:10]
        context['unread_count'] = Notification.objects.filter(recipient=request.user, read=False).count()

        context['events'] = Event.objects.order_by('date')[:5]
        context['news'] = NewsPost.objects.filter(published=True)[:3]
        return render(request, 'accounts/parent_dashboard.html', context)

    else:
        # Student
        from teacher.models import Mark, StudentEnrollment, Assignment, Note, Attendance, FeeRecord, Timetable, Notification
        if profile:
            context['results'] = ExamResult.objects.filter(
                admission_number=profile.admission_number, published=True
            )
            context['total_exams'] = context['results'].count()
            context['combination'] = Combination.objects.filter(
                examresult__admission_number=profile.admission_number
            ).first()
            enrollment = StudentEnrollment.objects.filter(student=request.user).first()
            if enrollment:
                context['classroom'] = enrollment.classroom
                context['combination'] = context.get('combination') or enrollment.classroom.combination
                context['marks'] = Mark.objects.filter(student=request.user).select_related('subject')
                context['assignments'] = Assignment.objects.filter(
                    classroom=enrollment.classroom).order_by('-created_at')[:5]
                context['notes'] = Note.objects.filter(
                    classroom=enrollment.classroom).order_by('-uploaded_at')[:5]
                # Attendance breakdown
                att_records = Attendance.objects.filter(student=request.user, classroom=enrollment.classroom)
                total_days = att_records.count()
                present_days = att_records.filter(status='present').count()
                absent_days = att_records.filter(status='absent').count()
                late_days = att_records.filter(status='late').count()
                context['attendance_rate'] = round((present_days / total_days) * 100, 1) if total_days > 0 else None
                context['total_days'] = total_days
                context['present_days'] = present_days
                context['absent_days'] = absent_days
                context['late_days'] = late_days
                # Timetable
                days = ['mon', 'tue', 'wed', 'thu', 'fri']
                timetable_qs = Timetable.objects.filter(
                    classroom=enrollment.classroom
                ).select_related('subject', 'teacher').order_by('day', 'start_time')
                context['timetable'] = {day: list(timetable_qs.filter(day=day)) for day in days}
                context['print_periods'] = _build_print_periods(timetable_qs)
            # Fees
            fee_records = FeeRecord.objects.filter(student=request.user)
            context['fees'] = fee_records
            total_fee = sum(f.amount for f in fee_records)
            total_paid = sum(f.paid for f in fee_records)
            context['total_fee'] = total_fee
            context['total_paid'] = total_paid
            context['fee_balance'] = total_fee - total_paid
            # Notifications
            context['notifications'] = Notification.objects.filter(recipient=request.user)[:10]
            context['unread_count'] = Notification.objects.filter(recipient=request.user, read=False).count()
        context['events'] = Event.objects.order_by('date')[:5]
        context['news'] = NewsPost.objects.filter(published=True)[:3]
        return render(request, 'accounts/student_dashboard.html', context)


# ── Admin: Students ───────────────────────────────────────────────────────────

@login_required
@admin_required
def admin_students(request):
    q = request.GET.get('q', '').strip()
    students = UserProfile.objects.filter(role='student').select_related('user')
    if q:
        students = students.filter(
            Q(user__first_name__icontains=q) |
            Q(user__last_name__icontains=q) |
            Q(admission_number__icontains=q) |
            Q(user__email__icontains=q)
        )
    paginator = Paginator(students.order_by('user__last_name'), 20)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'accounts/admin/students.html', {'students': page, 'q': q})


@login_required
@admin_required
def admin_add_student(request):
    combinations = Combination.objects.all()
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        admission_number = request.POST.get('admission_number', '').strip()
        password = request.POST.get('password', '')
        email = request.POST.get('email', '').strip()

        if not all([first_name, last_name, admission_number, password]):
            messages.error(request, 'First name, last name, admission number and password are required.')
            return render(request, 'accounts/admin/add_student.html', {'combinations': combinations})

        # Unique admission number
        if UserProfile.objects.filter(admission_number=admission_number).exists():
            messages.error(request, f'Admission number "{admission_number}" is already assigned to another student.')
            return render(request, 'accounts/admin/add_student.html', {'combinations': combinations})

        # Username same as admission number — must be unique
        if User.objects.filter(username=admission_number).exists():
            messages.error(request, f'Admission number "{admission_number}" already exists as a username.')
            return render(request, 'accounts/admin/add_student.html', {'combinations': combinations})

        # Unique email (if provided)
        if email and User.objects.filter(email=email).exists():
            messages.error(request, f'Email "{email}" is already registered to another user.')
            return render(request, 'accounts/admin/add_student.html', {'combinations': combinations})

        user = User.objects.create_user(
            username=admission_number,
            password=password,
            first_name=first_name,
            last_name=last_name,
            email=email,
        )
        UserProfile.objects.create(
            user=user,
            role='student',
            admission_number=admission_number,
            phone=request.POST.get('phone', ''),
            must_change_password=True,  # Force password change on first login
        )
        messages.success(request, f'Student {user.get_full_name()} added. They will be prompted to change their password on first login.')
        return redirect('admin_students')
    return render(request, 'accounts/admin/add_student.html', {'combinations': combinations})


# ── Admin: Parents ────────────────────────────────────────────────────────────

@login_required
@admin_required
def admin_parents(request):
    q = request.GET.get('q', '').strip()
    parents = UserProfile.objects.filter(role='parent').select_related('user', 'parent_of__user')
    if q:
        parents = parents.filter(
            Q(user__first_name__icontains=q) |
            Q(user__last_name__icontains=q) |
            Q(user__username__icontains=q)
        )
    paginator = Paginator(parents.order_by('user__last_name'), 20)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'accounts/admin/parents.html', {'parents': page, 'q': q})


@login_required
@admin_required
def admin_add_parent(request):
    students = UserProfile.objects.filter(role='student').select_related('user')
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        email = request.POST.get('email', '').strip()

        if not all([first_name, last_name, username, password]):
            messages.error(request, 'All required fields must be filled.')
            return render(request, 'accounts/admin/add_parent.html', {'students': students})

        if User.objects.filter(username=username).exists():
            messages.error(request, f'Username "{username}" already taken.')
            return render(request, 'accounts/admin/add_parent.html', {'students': students})

        # Unique email
        if email and User.objects.filter(email=email).exists():
            messages.error(request, f'Email "{email}" is already registered to another user.')
            return render(request, 'accounts/admin/add_parent.html', {'students': students})

        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=first_name,
            last_name=last_name,
            email=email,
        )
        UserProfile.objects.create(
            user=user,
            role='parent',
            phone=request.POST.get('phone', ''),
            parent_of_id=request.POST.get('student_id') or None,
            must_change_password=True,
        )
        messages.success(request, 'Parent account created. They will be prompted to change their password on first login.')
        return redirect('admin_parents')
    return render(request, 'accounts/admin/add_parent.html', {'students': students})


# ── Admin: Results ────────────────────────────────────────────────────────────

@login_required
@admin_required
def admin_results(request):
    q = request.GET.get('q', '').strip()
    results = ExamResult.objects.all()
    if q:
        results = results.filter(
            Q(student_name__icontains=q) | Q(admission_number__icontains=q)
        )
    paginator = Paginator(results.order_by('-year', 'student_name'), 20)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'accounts/admin/results.html', {'results': page, 'q': q})


@login_required
@admin_required
def admin_add_result(request):
    combinations = Combination.objects.all()
    if request.method == 'POST':
        student_name = request.POST.get('student_name', '').strip()
        admission_number = request.POST.get('admission_number', '').strip()
        combination_id = request.POST.get('combination', '')
        exam_name = request.POST.get('exam_name', '').strip()
        year = request.POST.get('year', '').strip()

        if not all([student_name, admission_number, combination_id, exam_name, year]):
            messages.error(request, 'All required fields must be filled.')
            return render(request, 'accounts/admin/add_result.html', {'combinations': combinations})

        ExamResult.objects.create(
            student_name=student_name,
            admission_number=admission_number,
            combination_id=combination_id,
            exam_name=exam_name,
            year=year,
            results=request.POST.get('results', ''),
            gpa=request.POST.get('gpa') or None,
            published='published' in request.POST,
        )
        messages.success(request, 'Result added successfully.')
        return redirect('admin_results')
    return render(request, 'accounts/admin/add_result.html', {'combinations': combinations})


# ── Admin: News ───────────────────────────────────────────────────────────────

@login_required
@admin_required
def admin_news(request):
    posts = NewsPost.objects.all().order_by('-created_at')
    paginator = Paginator(posts, 15)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'accounts/admin/news.html', {'posts': page})


@login_required
@admin_required
def admin_add_news(request):
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        if not title or not content:
            messages.error(request, 'Title and content are required.')
            return render(request, 'accounts/admin/add_news.html')

        image_file = request.FILES.get('image')
        if image_file:
            ok, err = validate_upload(image_file)
            if not ok:
                messages.error(request, err)
                return render(request, 'accounts/admin/add_news.html')
            image_file.name = safe_filename(image_file.name)

        post = NewsPost(title=title, content=content, published='published' in request.POST)
        if image_file:
            post.image = image_file
        post.save()
        messages.success(request, 'News post created.')
        return redirect('admin_news')
    return render(request, 'accounts/admin/add_news.html')


# ── Admin: Events ─────────────────────────────────────────────────────────────

@login_required
@admin_required
def admin_events(request):
    events = Event.objects.all().order_by('-date')
    paginator = Paginator(events, 15)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'accounts/admin/events.html', {'events': page})


@login_required
@admin_required
def admin_add_event(request):
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        date = request.POST.get('date', '').strip()
        if not all([title, description, date]):
            messages.error(request, 'Title, description and date are required.')
            return render(request, 'accounts/admin/add_event.html')
        Event.objects.create(
            title=title,
            description=description,
            date=date,
            end_date=request.POST.get('end_date') or None,
            location=request.POST.get('location', ''),
        )
        messages.success(request, 'Event added.')
        return redirect('admin_events')
    return render(request, 'accounts/admin/add_event.html')


# ── Admin: Applications ───────────────────────────────────────────────────────

@login_required
@admin_required
def admin_applications(request):
    status_filter = request.GET.get('status', '')
    apps = AdmissionApplication.objects.all().order_by('-applied_at')
    if status_filter:
        apps = apps.filter(status=status_filter)
    paginator = Paginator(apps, 20)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'accounts/admin/applications.html', {
        'applications': page, 'status_filter': status_filter
    })


@login_required
@admin_required
def admin_application_action(request, pk, action):
    app = get_object_or_404(AdmissionApplication, pk=pk)
    if action == 'approve':
        app.status = 'approved'
        app.save()
        messages.success(request, f'Application for {app.full_name} approved.')
    elif action == 'reject':
        app.status = 'rejected'
        app.save()
        messages.warning(request, f'Application for {app.full_name} rejected.')
    return redirect('admin_applications')


# ── Admin: Messages ───────────────────────────────────────────────────────────

@login_required
@admin_required
def admin_messages(request):
    msgs = ContactMessage.objects.all().order_by('-created_at')
    paginator = Paginator(msgs, 20)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'accounts/admin/messages.html', {'contact_messages': page})


@login_required
@admin_required
def admin_message_read(request, pk):
    msg = get_object_or_404(ContactMessage, pk=pk)
    msg.read = True
    msg.save()
    return redirect('admin_messages')


# ── Admin: Staff ──────────────────────────────────────────────────────────────

@login_required
@admin_required
def admin_staff(request):
    q = request.GET.get('q', '').strip()
    staff = Staff.objects.all()
    if q:
        staff = staff.filter(Q(name__icontains=q) | Q(subject__icontains=q))
    paginator = Paginator(staff.order_by('role', 'name'), 20)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'accounts/admin/staff.html', {'staff': page, 'q': q})


@login_required
@admin_required
def admin_add_staff(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        role = request.POST.get('role', '').strip()
        email = request.POST.get('email', '').strip()

        if not name or not role:
            messages.error(request, 'Name and role are required.')
            return render(request, 'accounts/admin/add_staff.html')

        photo_file = request.FILES.get('photo')
        if photo_file:
            ok, err = validate_upload(photo_file)
            if not ok:
                messages.error(request, err)
                return render(request, 'accounts/admin/add_staff.html')
            photo_file.name = safe_filename(photo_file.name)

        s = Staff(
            name=name,
            role=role,
            subject=request.POST.get('subject', ''),
            email=email,
            phone=request.POST.get('phone', ''),
            qualification=request.POST.get('qualification', ''),
            experience=request.POST.get('experience', ''),
            bio=request.POST.get('bio', ''),
        )
        if photo_file:
            s.photo = photo_file
        s.save()

        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        if username and password:
            if User.objects.filter(username=username).exists():
                messages.warning(request, f'Username "{username}" already exists. Staff profile saved without a login account.')
            elif email and User.objects.filter(email=email).exists():
                messages.warning(request, f'Email "{email}" is already registered. Staff profile saved without a login account.')
            else:
                user = User.objects.create_user(
                    username=username,
                    password=password,
                    first_name=name.split()[0],
                    last_name=' '.join(name.split()[1:]),
                    email=email,
                )
                UserProfile.objects.create(
                    user=user,
                    role='teacher',
                    phone=request.POST.get('phone', ''),
                    must_change_password=True,
                )
        messages.success(request, 'Staff member added. They will be prompted to change their password on first login.')
        return redirect('admin_staff')
    return render(request, 'accounts/admin/add_staff.html')


# ── Admin: Gallery ────────────────────────────────────────────────────────────

@login_required
@admin_required
def admin_gallery(request):
    albums = Album.objects.all()
    return render(request, 'accounts/admin/gallery.html', {'albums': albums})


@login_required
@admin_required
def admin_add_album(request):
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        if not title:
            messages.error(request, 'Album title is required.')
            return render(request, 'accounts/admin/add_album.html')
        album = Album.objects.create(
            title=title,
            description=request.POST.get('description', ''),
        )
        for f in request.FILES.getlist('photos'):
            ok, err = validate_upload(f)
            if not ok:
                messages.warning(request, f'Skipped "{f.name}": {err}')
                continue
            f.name = safe_filename(f.name)
            Photo.objects.create(album=album, image=f)
        messages.success(request, 'Album created.')
        return redirect('admin_gallery')
    return render(request, 'accounts/admin/add_album.html')


# ── Admin: Delete ─────────────────────────────────────────────────────────────

@login_required
@admin_required
def admin_delete(request, model, pk):
    """Only processes POST requests (confirmed deletes)."""
    if request.method != 'POST':
        messages.error(request, 'Invalid request.')
        return redirect('dashboard')

    model_map = {
        'student': UserProfile,
        'result': ExamResult,
        'news': NewsPost,
        'event': Event,
        'staff': Staff,
        'album': Album,
        'parent': UserProfile,
        'feerecord': FeeRecord,
        'timetable': Timetable,
        'combination': Combination,
    }
    if model not in model_map:
        messages.error(request, 'Unknown record type.')
        return redirect('dashboard')

    obj = get_object_or_404(model_map[model], pk=pk)
    if model in ('student', 'parent'):
        obj.user.delete()  # cascades to UserProfile
    else:
        obj.delete()
    messages.success(request, 'Deleted successfully.')
    return redirect(request.POST.get('next', 'dashboard'))


# ── Admin: Classes ────────────────────────────────────────────────────────────

@login_required
@admin_required
def admin_classes(request):
    classes = ClassRoom.objects.all().select_related('combination', 'class_teacher')
    return render(request, 'accounts/admin/classes.html', {'classes': classes})


@login_required
@admin_required
def admin_add_class(request):
    combinations = Combination.objects.all()
    teachers = User.objects.filter(userprofile__role='teacher')
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        combination_id = request.POST.get('combination', '')
        if not name or not combination_id:
            messages.error(request, 'Class name and combination are required.')
            return render(request, 'accounts/admin/add_class.html',
                          {'combinations': combinations, 'teachers': teachers})
        ClassRoom.objects.create(
            name=name,
            combination_id=combination_id,
            class_teacher_id=request.POST.get('class_teacher') or None,
            year=request.POST.get('year', 2026),
        )
        messages.success(request, 'Class created.')
        return redirect('admin_classes')
    return render(request, 'accounts/admin/add_class.html',
                  {'combinations': combinations, 'teachers': teachers})


# ── Admin: Subjects ───────────────────────────────────────────────────────────

@login_required
@admin_required
def admin_subjects(request):
    subjects = Subject.objects.all().select_related('combination', 'teacher')
    return render(request, 'accounts/admin/subjects.html', {'subjects': subjects})


@login_required
@admin_required
def admin_add_subject(request):
    combinations = Combination.objects.all()
    teachers = User.objects.filter(userprofile__role='teacher')
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        code = request.POST.get('code', '').strip()
        combination_id = request.POST.get('combination', '')
        if not all([name, code, combination_id]):
            messages.error(request, 'Name, code and combination are required.')
            return render(request, 'accounts/admin/add_subject.html',
                          {'combinations': combinations, 'teachers': teachers})
        Subject.objects.create(
            name=name,
            code=code,
            combination_id=combination_id,
            teacher_id=request.POST.get('teacher') or None,
        )
        messages.success(request, 'Subject added.')
        return redirect('admin_subjects')
    return render(request, 'accounts/admin/add_subject.html',
                  {'combinations': combinations, 'teachers': teachers})


# ── Admin: Enroll ─────────────────────────────────────────────────────────────

@login_required
@admin_required
def admin_enroll_student(request):
    classes = ClassRoom.objects.all()
    students = User.objects.filter(userprofile__role='student')
    if request.method == 'POST':
        student_id = request.POST.get('student', '')
        classroom_id = request.POST.get('classroom', '')
        if not student_id or not classroom_id:
            messages.error(request, 'Student and classroom are required.')
        else:
            _, created = StudentEnrollment.objects.get_or_create(
                student_id=student_id, classroom_id=classroom_id
            )
            if created:
                messages.success(request, 'Student enrolled successfully.')
            else:
                messages.info(request, 'Student is already enrolled in that class.')
        return redirect('admin_enroll_student')
    enrollments = StudentEnrollment.objects.all().select_related('student', 'classroom')
    paginator = Paginator(enrollments, 25)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'accounts/admin/enroll.html',
                  {'classes': classes, 'students': students, 'enrollments': page})


# ── Admin: Timetable ──────────────────────────────────────────────────────────

@login_required
@admin_required
def admin_timetable(request):
    slots = Timetable.objects.all().select_related('classroom', 'subject', 'teacher').order_by('classroom', 'day', 'start_time')

    # Subject colour map
    COLORS = {
        'PHY': '#4361ee', 'MAT': '#f72585', 'GEO': '#0077b6',
        'CHE': '#7209b7', 'BIO': '#06d6a0', 'ENG': '#fb8500',
    }

    # Time periods for the grid rows
    PERIODS = [
        {'label': '07:30 – 08:30', 'start': '07:30', 'end': '08:30', 'is_break': False},
        {'label': '08:30 – 09:30', 'start': '08:30', 'end': '09:30', 'is_break': False},
        {'label': '09:30 – 10:30', 'start': '09:30', 'end': '10:30', 'is_break': False},
        {'label': '☕ Break — 10:30 to 11:00', 'is_break': True},
        {'label': '11:00 – 12:00', 'start': '11:00', 'end': '12:00', 'is_break': False},
        {'label': '12:00 – 13:00', 'start': '12:00', 'end': '13:00', 'is_break': False},
        {'label': '🍽️ Lunch — 13:00 to 14:00', 'is_break': True},
        {'label': '14:00 – 15:00', 'start': '14:00', 'end': '15:00', 'is_break': False},
        {'label': '15:00 – 16:00', 'start': '15:00', 'end': '16:00', 'is_break': False},
    ]
    DAYS = ['mon', 'tue', 'wed', 'thu', 'fri']

    # Build timetable_data: {classroom_name: [period_rows]}
    classrooms = ClassRoom.objects.all().order_by('name')
    timetable_data = {}

    for classroom in classrooms:
        # Index slots by (day, start_time_str)
        slot_index = {}
        for s in slots.filter(classroom=classroom):
            key = (s.day, s.start_time.strftime('%H:%M'))
            slot_index[key] = s

        week = []
        for period in PERIODS:
            if period['is_break']:
                week.append({'is_break': True, 'label': period['label']})
            else:
                cells = []
                for day in DAYS:
                    slot = slot_index.get((day, period['start']))
                    if slot:
                        cells.append({
                            'code': slot.subject.code,
                            'name': slot.subject.name,
                            'teacher': slot.teacher.get_full_name(),
                            'color': COLORS.get(slot.subject.code, '#6c757d'),
                        })
                    else:
                        cells.append(None)
                week.append({'is_break': False, 'label': period['label'], 'cells': cells})

        timetable_data[classroom.name] = week

    return render(request, 'accounts/admin/timetable.html', {
        'slots': slots,
        'timetable_data': timetable_data,
    })


@login_required
@admin_required
def admin_add_timetable(request):
    classes = ClassRoom.objects.all()
    subjects = Subject.objects.all()
    teachers = User.objects.filter(userprofile__role='teacher')
    if request.method == 'POST':
        required = ['classroom', 'subject', 'teacher', 'day', 'start_time', 'end_time']
        if not all(request.POST.get(f, '').strip() for f in required):
            messages.error(request, 'All fields are required.')
            return render(request, 'accounts/admin/add_timetable.html',
                          {'classes': classes, 'subjects': subjects, 'teachers': teachers})
        Timetable.objects.create(
            classroom_id=request.POST['classroom'],
            subject_id=request.POST['subject'],
            teacher_id=request.POST['teacher'],
            day=request.POST['day'],
            start_time=request.POST['start_time'],
            end_time=request.POST['end_time'],
        )
        messages.success(request, 'Timetable slot added.')
        return redirect('admin_timetable')
    return render(request, 'accounts/admin/add_timetable.html',
                  {'classes': classes, 'subjects': subjects, 'teachers': teachers})


# ── Admin: Fees ───────────────────────────────────────────────────────────────

@login_required
@admin_required
def admin_fees(request):
    q = request.GET.get('q', '').strip()
    fees = FeeRecord.objects.all().select_related('student')
    if q:
        fees = fees.filter(
            Q(student__first_name__icontains=q) |
            Q(student__last_name__icontains=q) |
            Q(description__icontains=q)
        )
    paginator = Paginator(fees.order_by('-created_at'), 20)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'accounts/admin/fees.html', {'fees': page, 'q': q})


@login_required
@admin_required
def admin_add_fee(request):
    students = User.objects.filter(userprofile__role='student').order_by('last_name')
    if request.method == 'POST':
        student_id = request.POST.get('student', '')
        description = request.POST.get('description', '').strip()
        amount = request.POST.get('amount', '').strip()
        if not all([student_id, description, amount]):
            messages.error(request, 'Student, description and amount are required.')
            return render(request, 'accounts/admin/add_fee.html', {'students': students})
        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError
        except ValueError:
            messages.error(request, 'Amount must be a positive number.')
            return render(request, 'accounts/admin/add_fee.html', {'students': students})

        FeeRecord.objects.create(
            student_id=student_id,
            description=description,
            amount=amount,
            paid=request.POST.get('paid', 0) or 0,
            gepg_control_number=request.POST.get('gepg_control_number', ''),
            due_date=request.POST.get('due_date') or None,
        )
        messages.success(request, 'Fee record added.')
        return redirect('admin_fees')
    return render(request, 'accounts/admin/add_fee.html', {'students': students})


# ── Search Autocomplete API ───────────────────────────────────────────────────

@login_required
@admin_required
def search_suggestions(request):
    """
    Returns JSON suggestions for the admin search fields.
    ?q=noel&type=students   → matches students by name or admission number
    ?q=noel&type=staff      → matches staff by name or subject
    ?q=noel&type=fees       → matches students linked to fee records
    ?q=noel&type=parents    → matches parents by name or username
    """
    q = request.GET.get('q', '').strip()
    search_type = request.GET.get('type', 'students')

    if len(q) < 2:
        return JsonResponse({'results': []})

    results = []

    if search_type == 'students':
        profiles = UserProfile.objects.filter(
            role='student'
        ).filter(
            Q(user__first_name__icontains=q) |
            Q(user__last_name__icontains=q) |
            Q(admission_number__icontains=q) |
            Q(user__email__icontains=q)
        ).select_related('user')[:8]

        for p in profiles:
            full_name = p.user.get_full_name() or p.user.username
            results.append({
                'label': f'{full_name} — {p.admission_number or "no admission no."}',
                'value': full_name,
            })

    elif search_type == 'staff':
        from core.models import Staff
        staff_qs = Staff.objects.filter(
            Q(name__icontains=q) |
            Q(subject__icontains=q) |
            Q(role__icontains=q)
        )[:8]
        for s in staff_qs:
            results.append({
                'label': f'{s.name} — {s.role}',
                'value': s.name,
            })

    elif search_type == 'fees':
        users = User.objects.filter(
            userprofile__role='student'
        ).filter(
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q)
        )[:8]
        for u in users:
            results.append({
                'label': u.get_full_name() or u.username,
                'value': u.get_full_name() or u.username,
            })

    elif search_type == 'parents':
        profiles = UserProfile.objects.filter(
            role='parent'
        ).filter(
            Q(user__first_name__icontains=q) |
            Q(user__last_name__icontains=q) |
            Q(user__username__icontains=q)
        ).select_related('user')[:8]
        for p in profiles:
            full_name = p.user.get_full_name() or p.user.username
            results.append({
                'label': full_name,
                'value': full_name,
            })

    return JsonResponse({'results': results})


# ── Admin: Combinations ───────────────────────────────────────────────────────

@login_required
@admin_required
def admin_combinations(request):
    combinations = Combination.objects.all().order_by('code')
    return render(request, 'accounts/admin/combinations.html', {'combinations': combinations})


@login_required
@admin_required
def admin_add_combination(request):
    if request.method == 'POST':
        code = request.POST.get('code', '').strip().upper()
        name = request.POST.get('name', '').strip()
        subjects = request.POST.get('subjects', '').strip()

        if not code or not name:
            messages.error(request, 'Code and name are required.')
            return render(request, 'accounts/admin/add_combination.html')

        if Combination.objects.filter(code=code).exists():
            messages.error(request, f'Combination code "{code}" already exists.')
            return render(request, 'accounts/admin/add_combination.html')

        Combination.objects.create(code=code, name=name, subjects=subjects)
        messages.success(request, f'Combination {code} added successfully.')
        return redirect('admin_combinations')

    return render(request, 'accounts/admin/add_combination.html')


@login_required
@admin_required
def admin_edit_combination(request, pk):
    combination = get_object_or_404(Combination, pk=pk)

    if request.method == 'POST':
        code = request.POST.get('code', '').strip().upper()
        name = request.POST.get('name', '').strip()
        subjects = request.POST.get('subjects', '').strip()

        if not code or not name:
            messages.error(request, 'Code and name are required.')
            return render(request, 'accounts/admin/edit_combination.html', {'combination': combination})

        # Check uniqueness — exclude self
        if Combination.objects.filter(code=code).exclude(pk=pk).exists():
            messages.error(request, f'Combination code "{code}" is already used by another combination.')
            return render(request, 'accounts/admin/edit_combination.html', {'combination': combination})

        combination.code = code
        combination.name = name
        combination.subjects = subjects
        combination.save()
        messages.success(request, f'Combination {code} updated.')
        return redirect('admin_combinations')

    return render(request, 'accounts/admin/edit_combination.html', {'combination': combination})


# ── Admin: Move Student to Another Class ─────────────────────────────────────

@login_required
@admin_required
def admin_move_student(request, pk):
    """
    Move a student from their current class to a new one.
    Used when student progresses from Form 5 → Form 6,
    or transfers between combinations.
    """
    student_profile = get_object_or_404(UserProfile, pk=pk, role='student')
    student_user = student_profile.user
    current_enrollment = StudentEnrollment.objects.filter(student=student_user).first()
    all_classes = ClassRoom.objects.all().order_by('name')

    if request.method == 'POST':
        new_class_id = request.POST.get('classroom', '')
        if not new_class_id:
            messages.error(request, 'Please select a class.')
            return render(request, 'accounts/admin/move_student.html', {
                'student': student_profile,
                'current_enrollment': current_enrollment,
                'classes': all_classes,
            })

        new_classroom = get_object_or_404(ClassRoom, pk=new_class_id)

        # Already in this class?
        if current_enrollment and current_enrollment.classroom.pk == new_classroom.pk:
            messages.warning(request, f'{student_user.get_full_name()} is already in {new_classroom.name}.')
            return redirect('admin_students')

        # Remove from current class
        if current_enrollment:
            old_class_name = current_enrollment.classroom.name
            current_enrollment.delete()
        else:
            old_class_name = 'none'

        # Enroll in new class
        StudentEnrollment.objects.create(student=student_user, classroom=new_classroom)

        messages.success(
            request,
            f'{student_user.get_full_name()} moved from {old_class_name} → {new_classroom.name}.'
        )
        return redirect('admin_students')

    return render(request, 'accounts/admin/move_student.html', {
        'student': student_profile,
        'current_enrollment': current_enrollment,
        'classes': all_classes,
    })
