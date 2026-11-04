"""Guard against numpy APIs that numpy 2.0 removed.

QATrack+ pins ``numpy<2.0`` and that is deliberate - the pin is not what this
file is about. The problem it addresses is that nothing stops a deprecated name
being *added*, because the suite does not turn ``DeprecationWarning`` into an
error (``setup.cfg``), so a removed-in-2.0 alias keeps working silently for as
long as the pin holds and surfaces only on the day someone lifts it.

That is how a version bump turns into a pile of unrelated fixes. Each one of
these is a two-character change when it is written and an archaeology exercise a
year later, so they are caught here instead.

Asserted statically rather than by exercising the code, because most of these
names have no caller the suite reaches: ``np.NaN`` sat in
``leastsquaresfit.gauss_pdf`` behind a guard no test triggers, which is why it
survived four years.
"""

import ast
import os
import textwrap
import re

import pytest
from django.conf import settings

# Names that numpy 2.x no longer provides. The expired aliases are the common
# ones - np.float_, np.NaN and friends - and the rest are functions that were
# renamed or folded into another API.
#
# This list is a floor, not a ceiling: the numpy 2 migration guide's table is
# longer, and a name missing here is a gap in the guard rather than a name that
# is safe. Adding one costs nothing, so add it when you meet it. nsmela raised
# that on q#904, along with the np.object_ mistake noted below.
#
# np.object_ is deliberately absent. It was *not* removed - it is still the
# object scalar type in numpy 2 - so listing it would make this guard reject
# working code. Four more entries were wrong the same way and are gone:
# Bytes0, Str0, Datetime64 and Uint32 never existed in any numpy. The real
# names are lowercase, and test_every_listed_name_exists_in_the_pinned_numpy
# below now makes that class of mistake impossible to commit.
#
# `qatrack/qa/calculation_check.py`, on the check-calculations branch, carries
# a longer list derived from numpy's own `_expired_attrs_2_0.py` rather than
# transcribed. The two should become one derived list; that is a 4.1 job,
# because this one has a different target - this guards *our* source, that one
# scans a site's stored calculation procedures.
REMOVED_IN_NUMPY_2 = [
    # expired aliases for scalar types
    'float_', 'complex_', 'unicode_', 'string_', 'int0', 'uint0',
    'bool8', 'bytes0', 'str0', 'object0', 'void0',
    'cfloat', 'longfloat', 'singlecomplex',
    # expired constants
    'NaN', 'NAN', 'Inf', 'Infinity', 'infty', 'NINF', 'PINF',
    'NZERO', 'PZERO',
    # renamed or removed functions
    'alltrue', 'sometrue', 'cumproduct', 'product', 'round_', 'msort',
    'find_common_type', 'issctype', 'set_string_function',
    'asfarray', 'byte_bounds', 'cast', 'source', 'lookfor', 'who', 'disp',
    'safe_eval', 'recfromcsv', 'recfromtxt', 'sctypes', 'deprecate', 'mat',
    'add_newdoc', 'fastCopyAndTranspose', 'get_array_wrap', 'maximum_sctype',
    'issubsctype', 'set_numeric_ops', 'compare_chararrays',
    # Deprecated in 2.0 and removed later in the 2.x series rather than in 2.0
    # itself. Kept here on purpose: the point of the guard is that a name is
    # gone by the time the pin is lifted, not that it went in one exact release.
    'in1d', 'row_stack', 'trapz',
]

REPLACEMENTS = {
    'float_': 'np.float64',
    'complex_': 'np.complex128',
    'NaN': 'np.nan',
    'NAN': 'np.nan',
    'Inf': 'np.inf',
    'Infinity': 'np.inf',
    'infty': 'np.inf',
    'NINF': '-np.inf',
    'PINF': 'np.inf',
    'alltrue': 'np.all',
    'sometrue': 'np.any',
    'cumproduct': 'np.cumprod',
    'product': 'np.prod',
    'round_': 'np.round',
    'in1d': 'np.isin',
    'row_stack': 'np.vstack',
    'trapz': 'np.trapezoid',
    'cfloat': 'np.complex128',
    'longfloat': 'np.longdouble',
    'singlecomplex': 'np.complex64',
    'NZERO': '-0.0',
    'PZERO': '0.0',
    'asfarray': 'np.asarray(x, dtype=float)',
}

FORBIDDEN = re.compile(
    r'\b(?:np|numpy)\.(%s)\b' % '|'.join(REMOVED_IN_NUMPY_2)
)


def _removed_api_uses(path):
    """Every *use* of a removed NumPy name in one file, found with `ast`.

    This was line-based, stripping everything after the first ``#``, and the
    docstring said so: *"crude on purpose ... the names here appear in code far
    more often than in strings."* That held until a file arrived whose whole job
    is to name them. `qa/calculation_check.py` scans a site's stored calculation
    procedures for exactly these APIs, so it mentions `np.NaN` and `np.product`
    in its module docstring, in a comment about NumPy 1.26's deprecation, and -
    in its tests - as the input strings being scanned. All eight were reported as
    violations, and none was one.

    A mention is not a use, and only a parser can tell them apart. This yields
    attribute accesses on `np`/`numpy` and `from numpy import <name>`, and
    ignores comments, docstrings and string literals by construction.

    A file that cannot be parsed is reported rather than skipped: a syntax error
    in the tree is worth knowing about on its own.
    """
    with open(path, encoding='utf-8') as f:
        source = f.read()
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        yield exc.lineno or 0, '<unparseable: %s>' % exc.msg
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in REMOVED_IN_NUMPY_2:
            base = node.value
            if isinstance(base, ast.Name) and base.id in ('np', 'numpy'):
                yield node.lineno, node.attr
        elif isinstance(node, ast.ImportFrom) and node.module == 'numpy':
            for alias in node.names:
                if alias.name in REMOVED_IN_NUMPY_2:
                    yield node.lineno, alias.name


def _source_files():
    root = settings.PROJECT_ROOT
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames
            if d not in ('migrations', '__pycache__', 'south_migrations', 'static')
        ]
        for name in filenames:
            if name.endswith('.py') and name != os.path.basename(__file__):
                yield os.path.join(dirpath, name)


class TestNoRemovedNumpyApis:
    """No numpy name that 2.0 removed appears in qatrack/.

    Migrations are excluded: they are a historical record and are not rerun
    against a new numpy in any way that would reach this code.
    """

    def test_no_source_file_uses_an_api_numpy_2_removed(self):
        offenders = []
        for path in _source_files():
            for n, name in _removed_api_uses(path):
                rel = os.path.relpath(path, settings.BASE_DIR)
                hint = REPLACEMENTS.get(name, 'see the numpy 2 migration guide')
                offenders.append('%s:%d uses np.%s - use %s' % (rel, n, name, hint))

        assert not offenders, (
            "numpy 2.0 removed these, and the pin on numpy<2.0 is the only reason "
            "they still work:\n  " + "\n  ".join(offenders)
        )

    def test_the_guard_can_actually_see_an_offender(self):
        """A negative control: a scan that matches nothing proves nothing."""
        assert FORBIDDEN.findall('    return np.NaN') == ['NaN']
        assert FORBIDDEN.findall('np.float_,') == ['float_']
        assert FORBIDDEN.findall('np.float64, np.nan, np.prod') == []

    def test_every_listed_name_exists_in_the_pinned_numpy(self):
        """A name that never existed cannot have been removed.

        np.object_ was listed and was never removed; Bytes0, Str0, Datetime64
        and Uint32 were listed and never existed at all. Both mistakes are the
        same one - a transcribed list nobody checked - and both are caught here
        by asking the pinned numpy what it actually has.

        Skipped once the pin is lifted, when these names are gone by design.
        """
        import numpy

        if int(numpy.__version__.split('.')[0]) >= 2:
            pytest.skip("the names are removed in numpy 2, which is the point of the list")

        missing = [name for name in REMOVED_IN_NUMPY_2 if not hasattr(numpy, name)]
        assert not missing, (
            "these are listed as removed by numpy 2.0 but do not exist in numpy %s, "
            "so they were never real names:\n  %s" % (numpy.__version__, ', '.join(missing))
        )

    def test_object_is_not_treated_as_removed(self):
        """np.object_ survives in numpy 2, so the guard must not reject it.

        nsmela, q#904. Listing it would have failed a file for writing working
        code, which is worse than missing a name: a guard that cries wolf gets
        switched off.
        """
        assert FORBIDDEN.findall('dtype=np.object_') == []

    def test_a_name_added_from_the_migration_guide_is_caught(self):
        """The names added after review are really in the pattern."""
        assert FORBIDDEN.findall('np.cfloat') == ['cfloat']
        assert FORBIDDEN.findall('x = np.NZERO') == ['NZERO']
        assert FORBIDDEN.findall('np.sctypes["float"]') == ['sctypes']
        assert FORBIDDEN.findall('np.bytes0') == ['bytes0']

    def test_a_mention_is_not_a_use(self, tmp_path):
        """Comments, docstrings and string literals may all name a removed alias.

        Comments could before, by truncating each line at the first `#`.
        Docstrings and string literals could not, and that is what reported
        eight violations in `qa/calculation_check.py` and its tests - a file
        whose job is to scan a site's procedures for these very names.
        """
        f = tmp_path / 'mentions.py'
        f.write_text(textwrap.dedent("""
            \"\"\"Scans for np.NaN and np.product, which numpy 2 removed.\"\"\"
            x = 1  # np.NaN was here
            PATTERN = 'result = numpy.NaN'
            MESSAGE = "use np.prod instead of np.product"
            def scan(src):
                \"\"\"Reports np.float_ by name.\"\"\"
                return src
        """), encoding='utf-8')

        assert list(_removed_api_uses(str(f))) == []

    def test_a_real_use_is_still_caught(self, tmp_path):
        """The control. A guard that reports nothing would pass the test above."""
        f = tmp_path / 'uses.py'
        f.write_text(textwrap.dedent("""
            import numpy as np
            from numpy import NaN
            a = np.NaN
            b = numpy.product([1, 2])
            c = np.prod([1, 2])
        """), encoding='utf-8')

        found = sorted(name for _, name in _removed_api_uses(str(f)))

        assert found == ['NaN', 'NaN', 'product'], found

    def test_an_unparseable_file_is_reported_rather_than_skipped(self, tmp_path):
        """Otherwise a syntax error would read as a clean bill of health."""
        f = tmp_path / 'broken.py'
        f.write_text('def f(:\n', encoding='utf-8')

        found = list(_removed_api_uses(str(f)))

        assert len(found) == 1 and 'unparseable' in found[0][1], found
