================================
Local Site Code Custom Functions
================================

QATrack+ supports deployment-specific helper functions called Local Site Code.
These functions can be used from composite and upload calculation procedures
without patching core QATrack+ source files.

How it works
------------

1. Create a Python module that defines ``LOCAL_SITE_CODE_FUNCTIONS``.
2. Add your module path to ``LOCAL_SITE_CODE_FUNCTION_MODULES`` in
   ``local_settings.py``.
3. Use the functions in calculation procedures via ``LOCAL_SITE_CODE`` or
   ``LSC``.

Configuration
-------------

In ``local_settings.py``:

.. code-block:: python

    LOCAL_SITE_CODE_FUNCTION_MODULES = (
        "local_site_code_sample",
    )

Each module listed must expose:

.. code-block:: python

    LOCAL_SITE_CODE_FUNCTIONS = {
        "function_name": callable,
    }

Usage in a composite calculation
--------------------------------

.. code-block:: python

    result = LSC.factorial(6)

or

.. code-block:: python

    result = LOCAL_SITE_CODE.is_prime(test1)

Sample file
-----------

A ready-to-use sample module is included at:

- ``local_site_code_sample.py``

This sample provides:

- ``is_prime(value)``
- ``factorial(value)``

Operational guidance
--------------------

- Keep Local Site Code functions pure and deterministic.
- Avoid file, network, and database side effects in these helpers.
- Write unit tests for local functions in your deployment repository.
- If two modules define the same function name, QATrack+ will raise
  ``ImproperlyConfigured`` at runtime when loading calculation context.
