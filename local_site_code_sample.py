"""Sample Local Site Code custom functions for QATrack+.

To enable this sample in local_settings.py:

    LOCAL_SITE_CODE_FUNCTION_MODULES = ("local_site_code_sample",)
"""


def is_prime(value):
    """Return True if value is a prime integer greater than 1."""

    if not isinstance(value, int):
        raise TypeError("is_prime expects an int")

    if value < 2:
        return False

    if value == 2:
        return True

    if value % 2 == 0:
        return False

    factor = 3
    while factor * factor <= value:
        if value % factor == 0:
            return False
        factor += 2

    return True


def factorial(value):
    """Return factorial for a non-negative integer."""

    if not isinstance(value, int):
        raise TypeError("factorial expects an int")

    if value < 0:
        raise ValueError("factorial expects a non-negative integer")

    result = 1
    for n in range(2, value + 1):
        result *= n
    return result


LOCAL_SITE_CODE_FUNCTIONS = {
    "is_prime": is_prime,
    "factorial": factorial,
}
