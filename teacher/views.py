from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone

from .models import Subject, ClassRoom, StudentEnrollment, Mark, Attendance, Assignment, Note, Timetable
from kabuku_school.utils import teacher_required, validate_upload, send_notification, notify_parents_of_student, safe_filename


def _teacher_classroom(teacher, class_pk):
    """Return classroom only if this teacher teaches in it, else None."""
    classroom = get_object_or_404(ClassRoom, pk=class_pk)
    teaches_here = (
        classroom.class_teacher == teacher or
        Subject.objects.filter(teacher=teacher, combination=classroom.combination).exists()
    )
    return classroom if teaches_here else None


@login_required
@teacher_required
def teacher_dashboard(request):
    subjects = Subject.objects.filter(teacher=request.user)
    classrooms = ClassRoom.objects.filter(class_teacher=request.user)
    teaching_classes = ClassRoom.objects.filter(
        combination__subjects_list__teacher=request.user
    ).distinct()
    timetable_today = Timetable.objects.filter(
        teacher=request.user,
        day=timezone.now().strftime('%a').lower()[:3]
    )
    recent_assignments = Assignment.objects.filter(created_by=request.user)[:5]
    from .models import Notification
    notifications = Notification.objects.filter(recipient=request.user, read=False)[:5]
    context = {
        'subjects': subjects,
        'classrooms': classrooms,
        'teaching_classes': teaching_classes,
        'timetable_today': timetable_today,
        'recent_assignments': recent_assignments,
        'total_students': StudentEnrollment.objects.filter(classroom__in=teaching_classes).count(),
        'notifications': notifications,
        'unread_count': notifications.count(),
    }
    return render(request, 'teacher/dashboard.html', context)


@login_required
@teacher_required
def my_classes(request):
    classes = ClassRoom.objects.filter(
        combination__subjects_list__teacher=request.user
    ).distinct()
    return render(request, 'teacher/classes.html', {'classes': classes})


@login_required
@teacher_required
def class_students(request, pk):
    classroom = _teacher_classroom(request.user, pk)
    if not classroom:
        messages.error(request, 'You do not have access to that class.')
        return redirect('teacher_classes')
    enrollments = StudentEnrollment.objects.filter(classroom=classroom).select_related('student')
    return render(request, 'teacher/class_students.html',
                  {'classroom': classroom, 'enrollments': enrollments})


@login_required
@teacher_required
def enter_marks(request, class_pk):
    classroom = _teacher_classroom(request.user, class_pk)
    if not classroom:
        messages.error(request, 'You do not have access to that class.')
        return redirect('teacher_classes')

    subjects = Subject.objects.filter(teacher=request.user, combination=classroom.combination)
    enrollments = StudentEnrollment.objects.filter(classroom=classroom).select_related('student')

    if request.method == 'POST':
        subject_id = request.POST.get('subject', '')
        exam_type = request.POST.get('exam_type', '')
        term = request.POST.get('term', '')
        year_val = request.POST.get('year', '')
        max_score_val = request.POST.get('max_score', '')

        if not all([subject_id, exam_type, term, year_val, max_score_val]):
            messages.error(request, 'All fields are required before saving marks.')
            return redirect('enter_marks', class_pk=class_pk)

        subject = get_object_or_404(Subject, pk=subject_id, teacher=request.user)
        year = int(year_val)
        max_score = float(max_score_val)

        count = 0
        for enrollment in enrollments:
            score_key = f"score_{enrollment.student.pk}"
            score_val = request.POST.get(score_key, '').strip()
            if score_val:
                try:
                    score = float(score_val)
                    if score < 0 or score > max_score:
                        messages.warning(
                            request,
                            f'Score {score} for {enrollment.student.get_full_name()} '
                            f'is out of range (0–{max_score}). Skipped.'
                        )
                        continue
                except ValueError:
                    continue

                Mark.objects.update_or_create(
                    student=enrollment.student,
                    subject=subject,
                    exam_type=exam_type,
                    term=term,
                    year=year,
                    defaults={
                        'score': score,
                        'max_score': max_score,
                        'classroom': classroom,
                        'entered_by': request.user,
                    }
                )
                count += 1

                # 🔔 Notify student
                send_notification(
                    recipient=enrollment.student,
                    title=f'New {subject.get_exam_type_display() if hasattr(subject, "get_exam_type_display") else exam_type} result posted',
                    message=(
                        f'Your {exam_type} result for {subject.name} has been recorded: '
                        f'{score}/{max_score} ({round((score/max_score)*100, 1)}%). '
                        f'Term: {term} {year}.'
                    ),
                    notification_type='result',
                )
                # 🔔 Notify parent(s)
                notify_parents_of_student(
                    student_user=enrollment.student,
                    title=f"{enrollment.student.get_full_name()}'s result posted",
                    message=(
                        f'{enrollment.student.get_full_name()} scored {score}/{max_score} '
                        f'in {subject.name} ({exam_type}, {term} {year}).'
                    ),
                    notification_type='result',
                )

        messages.success(request, f'{count} marks saved for {subject.name} ({exam_type}).')
        return redirect('enter_marks', class_pk=class_pk)

    context = {
        'classroom': classroom,
        'subjects': subjects,
        'enrollments': enrollments,
    }
    return render(request, 'teacher/enter_marks.html', context)


@login_required
@teacher_required
def view_marks(request, class_pk):
    classroom = _teacher_classroom(request.user, class_pk)
    if not classroom:
        messages.error(request, 'You do not have access to that class.')
        return redirect('teacher_classes')

    subjects = Subject.objects.filter(teacher=request.user, combination=classroom.combination)
    marks = Mark.objects.filter(
        classroom=classroom, subject__in=subjects
    ).select_related('student', 'subject')

    subject_filter = request.GET.get('subject')
    exam_filter = request.GET.get('exam_type')
    if subject_filter:
        marks = marks.filter(subject_id=subject_filter)
    if exam_filter:
        marks = marks.filter(exam_type=exam_filter)

    context = {
        'classroom': classroom,
        'subjects': subjects,
        'marks': marks,
        'subject_filter': subject_filter,
        'exam_filter': exam_filter,
    }
    return render(request, 'teacher/view_marks.html', context)


@login_required
@teacher_required
def take_attendance(request, class_pk):
    classroom = _teacher_classroom(request.user, class_pk)
    if not classroom:
        messages.error(request, 'You do not have access to that class.')
        return redirect('teacher_classes')

    enrollments = StudentEnrollment.objects.filter(classroom=classroom).select_related('student')
    today = timezone.now().date()

    if request.method == 'POST':
        date_str = request.POST.get('date', str(today))
        count = 0
        absent_students = []

        for enrollment in enrollments:
            status_key = f"status_{enrollment.student.pk}"
            status = request.POST.get(status_key, 'present')
            Attendance.objects.update_or_create(
                student=enrollment.student,
                classroom=classroom,
                date=date_str,
                defaults={'status': status, 'recorded_by': request.user}
            )
            count += 1

            # 🔔 Notify parents if student is absent
            if status == 'absent':
                absent_students.append(enrollment.student)
                notify_parents_of_student(
                    student_user=enrollment.student,
                    title=f'{enrollment.student.get_full_name()} was absent',
                    message=(
                        f'Your child {enrollment.student.get_full_name()} was marked absent '
                        f'on {date_str} in {classroom.name}.'
                    ),
                    notification_type='absence',
                )

        messages.success(request, f'Attendance recorded for {count} students.')
        if absent_students:
            messages.warning(
                request,
                f'{len(absent_students)} student(s) marked absent — parents notified.'
            )
        return redirect('take_attendance', class_pk=class_pk)

    existing = {
        a.student_id: a.status
        for a in Attendance.objects.filter(classroom=classroom, date=today)
    }
    context = {
        'classroom': classroom,
        'enrollments': enrollments,
        'today': today,
        'existing': existing,
    }
    return render(request, 'teacher/attendance.html', context)


@login_required
@teacher_required
def attendance_report(request, class_pk):
    classroom = _teacher_classroom(request.user, class_pk)
    if not classroom:
        messages.error(request, 'You do not have access to that class.')
        return redirect('teacher_classes')

    enrollments = StudentEnrollment.objects.filter(classroom=classroom).select_related('student')
    stats = []
    for e in enrollments:
        records = Attendance.objects.filter(student=e.student, classroom=classroom)
        total = records.count()
        present = records.filter(status='present').count()
        absent = records.filter(status='absent').count()
        late = records.filter(status='late').count()
        rate = round((present / total) * 100, 1) if total > 0 else 0
        stats.append({
            'student': e.student,
            'total': total,
            'present': present,
            'absent': absent,
            'late': late,
            'rate': rate,
        })
    return render(request, 'teacher/attendance_report.html',
                  {'classroom': classroom, 'stats': stats})


@login_required
@teacher_required
def upload_assignment(request):
    subjects = Subject.objects.filter(teacher=request.user)
    classes = ClassRoom.objects.filter(
        combination__subjects_list__teacher=request.user
    ).distinct()

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        subject_id = request.POST.get('subject', '')
        classroom_id = request.POST.get('classroom', '')
        if not all([title, subject_id, classroom_id]):
            messages.error(request, 'Title, subject and class are required.')
            return render(request, 'teacher/upload_assignment.html',
                          {'subjects': subjects, 'classes': classes})

        file_obj = request.FILES.get('file')
        if file_obj:
            ok, err = validate_upload(file_obj)
            if not ok:
                messages.error(request, err)
                return render(request, 'teacher/upload_assignment.html',
                              {'subjects': subjects, 'classes': classes})
            file_obj.name = safe_filename(file_obj.name)

        assignment = Assignment.objects.create(
            title=title,
            description=request.POST.get('description', ''),
            subject_id=subject_id,
            classroom_id=classroom_id,
            file=file_obj,
            deadline=request.POST.get('deadline') or None,
            created_by=request.user,
        )

        # 🔔 Notify all students in the class
        classroom = assignment.classroom
        for enrollment in StudentEnrollment.objects.filter(classroom=classroom).select_related('student'):
            send_notification(
                recipient=enrollment.student,
                title=f'New assignment: {assignment.title}',
                message=(
                    f'A new assignment "{assignment.title}" has been posted for {classroom.name}.'
                    + (f' Deadline: {assignment.deadline.strftime("%d %b %Y %H:%M")}.'
                       if assignment.deadline else '')
                ),
                notification_type='assignment',
            )

        messages.success(request, 'Assignment uploaded and students notified.')
        return redirect('teacher_assignments')

    return render(request, 'teacher/upload_assignment.html',
                  {'subjects': subjects, 'classes': classes})


@login_required
@teacher_required
def teacher_assignments(request):
    assignments = Assignment.objects.filter(created_by=request.user)
    return render(request, 'teacher/assignments.html', {'assignments': assignments})


@login_required
@teacher_required
def upload_note(request):
    subjects = Subject.objects.filter(teacher=request.user)
    classes = ClassRoom.objects.filter(
        combination__subjects_list__teacher=request.user
    ).distinct()

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        subject_id = request.POST.get('subject', '')
        classroom_id = request.POST.get('classroom', '')
        file_obj = request.FILES.get('file')

        if not all([title, subject_id, classroom_id, file_obj]):
            messages.error(request, 'All fields including a file are required.')
            return render(request, 'teacher/upload_note.html',
                          {'subjects': subjects, 'classes': classes})

        ok, err = validate_upload(file_obj)
        if not ok:
            messages.error(request, err)
            return render(request, 'teacher/upload_note.html',
                          {'subjects': subjects, 'classes': classes})
        file_obj.name = safe_filename(file_obj.name)

        Note.objects.create(
            title=title,
            subject_id=subject_id,
            classroom_id=classroom_id,
            file=file_obj,
            uploaded_by=request.user,
        )
        messages.success(request, 'Notes uploaded.')
        return redirect('teacher_notes')

    return render(request, 'teacher/upload_note.html',
                  {'subjects': subjects, 'classes': classes})


@login_required
@teacher_required
def teacher_notes(request):
    notes = Note.objects.filter(uploaded_by=request.user)
    return render(request, 'teacher/notes.html', {'notes': notes})


@login_required
@teacher_required
def timetable(request):
    from accounts.views import _build_print_periods
    schedule = Timetable.objects.filter(teacher=request.user).select_related('subject', 'teacher', 'classroom')
    days = ['mon', 'tue', 'wed', 'thu', 'fri']
    timetable_data = {day: list(schedule.filter(day=day).order_by('start_time')) for day in days}
    return render(request, 'teacher/timetable.html', {
        'timetable': timetable_data,
        'print_periods': _build_print_periods(schedule),
    })
