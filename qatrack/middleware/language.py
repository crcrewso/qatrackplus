from django.conf import settings
from django.utils import translation


class EnforceSupportedLanguageMiddleware:
    """Restrict active language to settings.LANGUAGES and fallback to default."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.supported = {code.lower() for code, _ in settings.LANGUAGES}
        self.default = settings.LANGUAGE_CODE

    def __call__(self, request):
        active = (translation.get_language() or '').lower()
        base = active.split('-')[0] if active else ''

        if active and active not in self.supported and base not in self.supported:
            translation.activate(self.default)
            request.LANGUAGE_CODE = translation.get_language()

        return self.get_response(request)