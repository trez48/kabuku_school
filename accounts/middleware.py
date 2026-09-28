from django.shortcuts import redirect
from django.urls import reverse


class ForcePasswordChangeMiddleware:
    """
    After admin sets a password for a new user, that user is forced to
    change it before accessing any other page.
    Skips: logout, the change-password page itself, and static/media files.
    """
    EXEMPT_URLS = [
        '/accounts/logout/',
        '/accounts/change-password/',
        '/accounts/login/',
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.user.is_authenticated
            and not request.user.is_superuser
            and not any(request.path.startswith(url) for url in self.EXEMPT_URLS)
            and not request.path.startswith('/static/')
            and not request.path.startswith('/media/')
            and not request.path.startswith('/student-photos/')
        ):
            try:
                profile = request.user.userprofile
                if profile.must_change_password:
                    return redirect('change_password')
            except Exception:
                pass  # No profile — let it through

        return self.get_response(request)
