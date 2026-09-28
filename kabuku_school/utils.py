"""
Shared utilities: decorators, validators, notification helpers.
"""
import os
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.conf import settings


# ── Decorators ──────────────────────────────────────────────────────────────

def admin_required(view_func):
    """Allow only superusers or admin-role users."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        from accounts.models import UserProfile
        profile = UserProfile.objects.filter(user=request.user, role='admin').first()
        if not profile:
            messages.error(request, 'You do not have permission to access that page.')
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def teacher_required(view_func):
    """Allow only teacher-role users."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not (hasattr(request.user, 'userprofile') and
                request.user.userprofile.role == 'teacher'):
            messages.error(request, 'Access restricted to teachers.')
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


# ── File upload validation ───────────────────────────────────────────────────

ALLOWED_EXTENSIONS = getattr(
    settings, 'ALLOWED_UPLOAD_EXTENSIONS',
    ['.pdf', '.doc', '.docx', '.png', '.jpg', '.jpeg']
)
MAX_UPLOAD_BYTES = getattr(settings, 'MAX_UPLOAD_SIZE_MB', 10) * 1024 * 1024


def validate_upload(file_obj):
    """
    Returns (True, None) if valid, (False, error_message) if not.
    """
    if file_obj is None:
        return True, None  # optional file — caller decides

    ext = os.path.splitext(file_obj.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, (
            f'File type "{ext}" is not allowed. '
            f'Allowed: {", ".join(ALLOWED_EXTENSIONS)}'
        )
    if file_obj.size > MAX_UPLOAD_BYTES:
        mb = MAX_UPLOAD_BYTES // (1024 * 1024)
        return False, f'File is too large. Maximum size is {mb} MB.'
    return True, None


# ── Notification helper ──────────────────────────────────────────────────────

def send_notification(recipient, title, message, notification_type='announcement'):
    """
    Create a Notification record for a user.
    Silently ignored if the Notification model is unavailable.
    """
    try:
        from teacher.models import Notification
        Notification.objects.create(
            recipient=recipient,
            title=title,
            message=message,
            notification_type=notification_type,
        )
    except Exception:
        pass  # Never crash the main flow over a notification


def notify_parents_of_student(student_user, title, message, notification_type='announcement'):
    """Send a notification to all parents linked to this student."""
    try:
        from accounts.models import UserProfile
        student_profile = UserProfile.objects.filter(user=student_user).first()
        if not student_profile:
            return
        parents = UserProfile.objects.filter(
            role='parent', parent_of=student_profile
        ).select_related('user')
        for parent in parents:
            send_notification(parent.user, title, message, notification_type)
    except Exception:
        pass
