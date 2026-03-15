from django.utils import timezone

class SessionTimeoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            from django.conf import settings
            now = timezone.now().timestamp()
            last = request.session.get('last_activity')
            warning_sec = getattr(settings, 'SESSION_WARNING_SECONDS', 300)
            session_age = getattr(settings, 'SESSION_COOKIE_AGE', 3600)
            if last:
                elapsed = now - last
                remaining = session_age - elapsed
                request.session['session_remaining'] = int(remaining)
                request.session['session_warning'] = remaining <= warning_sec
            request.session['last_activity'] = now
        return self.get_response(request)