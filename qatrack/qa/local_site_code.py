from functools import lru_cache
from importlib import import_module
from types import SimpleNamespace

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


REGISTRY_ATTR = "LOCAL_SITE_CODE_FUNCTIONS"


@lru_cache(maxsize=1)
def get_local_site_code_calculation_context():
    """Load and validate configured Local Site Code function registries."""

    module_paths = getattr(settings, "LOCAL_SITE_CODE_FUNCTION_MODULES", ())
    if not module_paths:
        return {}

    if not isinstance(module_paths, (list, tuple)):
        raise ImproperlyConfigured("LOCAL_SITE_CODE_FUNCTION_MODULES must be a list or tuple of module paths")

    merged = {}
    for module_path in module_paths:
        module = import_module(module_path)
        registry = getattr(module, REGISTRY_ATTR, None)

        if registry is None:
            raise ImproperlyConfigured(f"Module '{module_path}' must define {REGISTRY_ATTR}")

        if not isinstance(registry, dict):
            raise ImproperlyConfigured(f"{REGISTRY_ATTR} in '{module_path}' must be a dict")

        for name, func in registry.items():
            if not callable(func):
                raise ImproperlyConfigured(
                    f"{REGISTRY_ATTR}['{name}'] in '{module_path}' must be callable"
                )
            if name in merged:
                raise ImproperlyConfigured(
                    f"Duplicate Local Site Code function name '{name}' found in '{module_path}'"
                )
            merged[name] = func

    namespace = SimpleNamespace(**merged)
    return {
        "LOCAL_SITE_CODE": namespace,
        "LSC": namespace,
    }
