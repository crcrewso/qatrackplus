"""
Check that tests' calculation procedures still run, and still give the results
they gave when the tests were performed.

Calculation procedures are Python snippets written by each clinic, and they run
with NumPy, SciPy, pydicom and friends available. Upgrading one of those
libraries (NumPy 2 is the one that prompted this) can break a procedure without
anything in QATrack+ itself changing, and until now the only way for a site to
find out was to perform every test list by hand.

Two independent checks are made:

* A **scan** of each procedure's source. It needs no data and takes
  milliseconds, and because it knows what NumPy 2 removed it can warn about a
  procedure *before* NumPy is upgraded (``np.NaN``, ``np.product``, ...).

* A **recalculation**. The most recent saved result of each test on each unit is
  calculated again, from the values saved alongside it, by the same code the
  Perform QC page uses - as if that test list instance had been opened for
  editing - and compared with the result that was saved. This is the
  definitive check once an upgrade is installed, and it catches what no scan
  can: a NumPy 2 scalar printing as ``np.float64(1.5)`` rather than ``1.5``
  inside a string composite, for instance.

  File upload tests are recalculated from their saved upload files. Any file
  attached to the test itself with a label starting ``check_calculations`` is
  run too, so a site can supply a sample file for an upload test that has never
  been performed (or whose uploads have since been deleted).

Nothing is saved. Files written with ``UTILS.write_file`` are discarded, and
each recalculation runs in a database transaction that is always rolled back.
Anything a procedure does outside the database (writing to a network share,
say) will happen again, exactly as it would on the Perform QC page.

Used by the ``check_calculations`` management command and by the "Check
Calculation Procedures" page of the admin.
"""

import ast
import contextlib
import copy
import datetime
import functools
import importlib.metadata
import inspect
import json
import math
import os
import platform
import re
import sys
import threading
import traceback
import warnings
from collections import defaultdict
from dataclasses import asdict, dataclass, field

import numpy
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import OuterRef, Q, Subquery
from django.utils import timezone
from django.utils.formats import get_format
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _l

from qatrack.attachments.models import Attachment
from qatrack.attachments.utils import imsave, to_bytes
from qatrack.qa import models
from qatrack.qa.views.perform import (
    CompositePerformer,
    CompositeUtils,
    UploadHandler,
    cleanup_matplotlib,
)
from qatrack.qatrack_core.dates import format_datetime
from qatrack.qatrack_core.serializers import QATrackJSONEncoder

# Statuses, most severe first. A test's status is the most severe of its checks.
ERROR = 'error'  # will not compile, raised an exception, or uses something the installed NumPy lacks
CHANGED = 'changed'  # ran, but gave a different result from the one saved
WARNING = 'warning'  # uses something NumPy 2 removed or changed
NOT_RUN = 'not_run'  # there was nothing to recalculate it from
OK = 'ok'

SEVERITY = (ERROR, CHANGED, WARNING, NOT_RUN, OK)

STATUS_DISPLAY = {
    ERROR: _l('Broken'),
    CHANGED: _l('Changed'),
    WARNING: _l('Warning'),
    NOT_RUN: _l('Not recalculated'),
    OK: _l('OK'),
}

# Label (prefix) of a file attached to an upload test that should be run
# through its procedure as a sample.
SAMPLE_FILE_LABEL = 'check_calculations'

# Recalculated numbers are compared with saved ones to about 9 significant
# figures. Recalculating with identical code and libraries reproduces a saved
# value exactly, but a new NumPy can legitimately change the last bit or two
# (e.g. by summing in a different order), which isn't worth reporting.
DEFAULT_RTOL = 1e-9
DEFAULT_ATOL = 1e-12

# Longest saved/recalculated value shown in a report.
DISPLAY_LIMIT = 300

# Warnings a library gives before removing or changing something. When a
# procedure's own code triggers one during a recalculation it's reported, which
# catches (for example) pandas changes that a scan of the source can't.
UPGRADE_WARNINGS = (DeprecationWarning, PendingDeprecationWarning, FutureWarning)

# The file name procedures are compiled with in views/perform.py, followed by
# the test's macro name (and ".py" for uploads).
PROCEDURE_FILE_PREFIX = '__QAT+COMP_'
PERFORM_FILE = os.path.normcase(inspect.getfile(CompositePerformer))

# warnings.catch_warnings() swaps process-wide state, so two checks running at
# once in a threaded server must not interleave their captures.
_WARNINGS_LOCK = threading.Lock()

NUMPY_VERSION = numpy.__version__
NUMPY_MAJOR = int(NUMPY_VERSION.split('.')[0])


def worst(statuses):
    """Return the most severe of `statuses` (OK if there are none)"""
    statuses = set(statuses)
    return next((s for s in SEVERITY if s in statuses), OK)


@dataclass
class Finding:
    """A problem found by scanning a procedure's source"""

    status: str
    message: str
    line: int = None

    def as_dict(self):
        return asdict(self)


@dataclass
class Recalculation:
    """The outcome of calculating one saved result (or sample file) again"""

    status: str
    source: str
    message: str = ''
    saved: str = ''
    recalculated: str = ''
    test_list_instance_id: int = None
    # deprecation warnings the procedure's own code raised while it ran
    warnings: list = field(default_factory=list)
    # the full traceback, when `message` summarises an error
    detail: str = ''

    @property
    def severity(self):
        """The status, raised to WARNING if it ran but a library warned about something it did"""
        return WARNING if self.status == OK and self.warnings else self.status

    def as_dict(self):
        return asdict(self)


@dataclass
class TestCheck:
    """Everything found out about one test"""

    __test__ = False  # not a pytest test class, despite the name

    test: models.Test
    findings: list = field(default_factory=list)
    recalculations: list = field(default_factory=list)
    recalculation_requested: bool = True

    @property
    def status(self):
        statuses = [f.status for f in self.findings]
        ran = [r.severity for r in self.recalculations if r.status != NOT_RUN]
        statuses.extend(ran)
        if self.recalculation_requested and not ran:
            # Not being able to recalculate a test on one unit doesn't matter
            # if it was recalculated on another.
            statuses.append(NOT_RUN)
        return worst(statuses)

    @property
    def status_display(self):
        return STATUS_DISPLAY[self.status]

    def as_dict(self):
        return {
            'id': self.test.pk,
            'name': self.test.name,
            'macro_name': self.test.slug,
            'type': self.test.type,
            'status': self.status,
            'findings': [f.as_dict() for f in self.findings],
            'recalculations': [r.as_dict() for r in self.recalculations],
        }


def library_versions():
    """Versions of Python and the libraries calculation procedures most often use"""

    versions = {'Python': platform.python_version()}
    for name in ('numpy', 'scipy', 'pandas', 'matplotlib', 'pydicom', 'pylinac'):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
    return versions


def tests_with_procedures(queryset=None):
    """
    Tests whose calculation procedure is run when QC is performed: every
    composite, string composite and file upload test, plus any other test
    with a procedure that sets its default value.
    """
    queryset = models.Test.objects.all() if queryset is None else queryset
    has_procedure = Q(calculation_procedure__isnull=False) & ~Q(calculation_procedure='')
    return queryset.filter(Q(type__in=models.CALCULATED_TYPES) | has_procedure).order_by('name')


def procedure_kind(test):
    """Short description of what a test's procedure is for"""
    if test.type in models.CALCULATED_TYPES:
        return test.get_type_display()
    return _('%(test_type)s (default value)') % {'test_type': test.get_type_display()}


###############################################################################
# Scan
###############################################################################

# What NumPy 2 took out of its namespace, with what to use instead. Everything
# here exists in NumPy 1.26 and not in NumPy 2.x. Most of it is NumPy's own list
# (numpy/_expired_attrs_2_0.py, whose advice is reused); the rest was found by
# comparing the two versions directly. Keys are relative to `numpy`.
NUMPY2_REMOVED = {
    # numpy/_expired_attrs_2_0.py
    'geterrobj': 'Use the `np.errstate` context manager instead.',
    'seterrobj': 'Use the `np.errstate` context manager instead.',
    'cast': 'Use `np.asarray(arr, dtype=dtype)` instead.',
    'source': 'Use `inspect.getsource` instead.',
    'lookfor': "Search NumPy's documentation directly.",
    'who': 'Use `locals()` instead.',
    'fastCopyAndTranspose': 'Use `arr.T.copy()` instead.',
    'set_numeric_ops': 'Define `__array_ufunc__` on an ndarray subclass instead.',
    'NINF': 'Use `-np.inf` instead.',
    'PINF': 'Use `np.inf` instead.',
    'NZERO': 'Use `-0.0` instead.',
    'PZERO': 'Use `0.0` instead.',
    'add_newdoc': 'It is still available as `np.lib.add_newdoc`.',
    'add_docstring': 'It is still available as `np.lib.add_docstring`.',
    'add_newdoc_ufunc': 'It was internal and has no replacement.',
    'safe_eval': 'Use `ast.literal_eval` instead.',
    'float_': 'Use `np.float64` instead.',
    'complex_': 'Use `np.complex128` instead.',
    'longfloat': 'Use `np.longdouble` instead.',
    'singlecomplex': 'Use `np.complex64` instead.',
    'cfloat': 'Use `np.complex128` instead.',
    'longcomplex': 'Use `np.clongdouble` instead.',
    'clongfloat': 'Use `np.clongdouble` instead.',
    'string_': 'Use `np.bytes_` instead.',
    'unicode_': 'Use `np.str_` instead.',
    'Inf': 'Use `np.inf` instead.',
    'Infinity': 'Use `np.inf` instead.',
    'NaN': 'Use `np.nan` instead.',
    'infty': 'Use `np.inf` instead.',
    'issctype': 'Use `issubclass(rep, np.generic)` instead.',
    'maximum_sctype': 'Choose a specific dtype instead.',
    'obj2sctype': 'Use `np.dtype(obj).type` instead.',
    'sctype2char': 'Use `np.dtype(obj).char` instead.',
    'sctypes': 'Name the dtypes you need explicitly instead.',
    'issubsctype': 'Use `np.issubdtype` instead.',
    'set_string_function': 'Use `np.set_printoptions` with a formatter instead.',
    'asfarray': 'Use `np.asarray` with a floating point dtype instead.',
    'issubclass_': 'Use the built-in `issubclass` instead.',
    'tracemalloc_domain': 'It is now available as `np.lib.tracemalloc_domain`.',
    'mat': 'Use `np.asmatrix` instead.',
    'recfromcsv': 'Use `np.genfromtxt` with a comma delimiter instead.',
    'recfromtxt': 'Use `np.genfromtxt` instead.',
    'deprecate': 'Use `warnings.warn` with a `DeprecationWarning` instead.',
    'deprecate_with_doc': 'Use `warnings.warn` with a `DeprecationWarning` instead.',
    'find_common_type': 'Use `np.promote_types` or `np.result_type` instead.',
    'round_': 'Use `np.round` instead.',
    'get_array_wrap': 'It has no replacement.',
    'DataSource': 'It is still available as `np.lib.npyio.DataSource`.',
    'nbytes': 'Use `np.dtype(<dtype>).itemsize` instead.',
    'byte_bounds': 'It is now available as `np.lib.array_utils.byte_bounds`.',
    'compare_chararrays': 'It is still available as `np.char.compare_chararrays`.',
    'format_parser': 'It is still available as `np.rec.format_parser`.',
    'alltrue': 'Use `np.all` instead.',
    'sometrue': 'Use `np.any` instead.',
    # deprecated around NumPy 1.24 - 2.0 and removed since
    'product': 'Use `np.prod` instead.',
    'cumproduct': 'Use `np.cumprod` instead.',
    'trapz': (
        'Use `scipy.integrate.trapezoid`, which works with every NumPy version, '
        'or `np.trapezoid`, which only exists from NumPy 2.0 on.'
    ),
    'in1d': 'Use `np.isin` instead.',
    'row_stack': 'Use `np.vstack` instead.',
    'msort': 'Use `np.sort(a, axis=0)` instead.',
    'int0': 'Use `np.intp` instead.',
    'uint0': 'Use `np.uintp` instead.',
    'bool8': 'Use `np.bool_` instead.',
    'object0': 'Use `np.object_` instead.',
    'str0': 'Use `np.str_` instead.',
    'bytes0': 'Use `np.bytes_` instead.',
    'void0': 'Use `np.void` instead.',
    'chararray': 'It is still available as `np.char.chararray`.',
    'compat': 'It only supported Python 2 and has no replacement.',
    'math': 'Use the standard `math` module instead.',
    # modules that are now private; their public functions are all in `numpy`
    'lib.arraysetops': 'Use the same function from the main `np` namespace instead.',
    'lib.function_base': 'Use the same function from the main `np` namespace instead.',
    'lib.histograms': 'Use the same function from the main `np` namespace instead.',
    'lib.index_tricks': 'Use the same function from the main `np` namespace instead.',
    'lib.nanfunctions': 'Use the same function from the main `np` namespace instead.',
    'lib.polynomial': 'Use the same function from the main `np` namespace instead.',
    'lib.shape_base': 'Use the same function from the main `np` namespace instead.',
    'lib.twodim_base': 'Use the same function from the main `np` namespace instead.',
    'lib.type_check': 'Use the same function from the main `np` namespace instead.',
    'lib.ufunclike': 'Use the same function from the main `np` namespace instead.',
    'lib.utils': 'Use the same function from the main `np` namespace instead.',
    'lib.emath': 'Use `np.emath` instead.',
    'lib.math': 'Use the standard `math` module instead.',
    'lib.pad': 'Use `np.pad` instead.',
    'linalg.linalg': 'Use `np.linalg` directly instead.',
    'fft.helper': 'Use `np.fft` directly instead.',
    # array methods
    'ndarray.ptp': 'Use `np.ptp(arr)` instead.',
    'ndarray.itemset': 'Assign with `arr[index] = value` instead.',
    'ndarray.newbyteorder': 'Use `arr.view(arr.dtype.newbyteorder(order))` instead.',
}

# Still present in NumPy 2, but only as deprecated aliases.
NUMPY2_DEPRECATED = {
    'core': (
        '`numpy.core` was renamed `numpy._core` in NumPy 2.0 and is only kept as a deprecated '
        'alias. Use the public NumPy API instead.'
    ),
}

# Array methods NumPy 2 removed: (what to use instead, receivers to ignore).
# A scan can't know an object's type, so these are only reported as possible.
NUMPY2_REMOVED_METHODS = {
    'ptp': 'Use `np.ptp(arr)` instead.',
    'itemset': 'Assign with `arr[index] = value` instead.',
    # dtype.newbyteorder() still exists, so `x.dtype.newbyteorder()` is fine
    'newbyteorder': 'Use `arr.view(arr.dtype.newbyteorder(order))` instead.',
}


def scan_procedure(source):
    """Scan a calculation procedure's source and return a list of Findings"""

    if not source or not source.strip():
        return []

    # Normalise line endings first so that reported line numbers match what
    # people see in the admin.
    source = source.replace('\r\n', '\n').replace('\r', '\n')

    try:
        compile(source, '<calculation procedure>', 'exec')
    except SyntaxError as e:
        return [Finding(ERROR, _('This procedure is not valid Python: %(error)s') % {'error': e.msg}, e.lineno)]
    except ValueError as e:
        # e.g. null bytes in the source
        return [Finding(ERROR, _('This procedure is not valid Python: %(error)s') % {'error': e})]

    return _NumpyScan(ast.parse(source)).findings


class _NumpyScan:
    """
    Find the NumPy features a procedure uses that NumPy 2 removed or changed.

    NumPy is available to procedures as `numpy` without importing it, and may
    also be imported under any name (`import numpy as np`, `from numpy
    import linalg`, ...), so references are resolved through those names.
    """

    def __init__(self, tree):
        self.tree = tree
        self.findings = []
        self._seen = set()

        # the calculation context provides `numpy` without an import
        self.aliases = {'numpy': 'numpy'}
        self.star_import = False
        self.rebound = set()
        self._collect_aliases()

        self._scan_imports()
        self._scan_references()
        self._scan_calls()

        self.findings.sort(key=lambda f: (f.line or 0, f.message))

    def _add(self, status, message, node):
        line = getattr(node, 'lineno', None)
        if (line, message) not in self._seen:
            self._seen.add((line, message))
            self.findings.append(Finding(status, message, line))

    def _collect_aliases(self):
        rebound = self.rebound
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    if _is_numpy(name.name):
                        # `import numpy.linalg` binds `numpy`, `import numpy.linalg as la` binds `la`
                        if name.asname:
                            self.aliases[name.asname] = name.name
                        else:
                            self.aliases['numpy'] = 'numpy'
                    else:
                        rebound.add(name.asname or name.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                for name in node.names:
                    if name.name == '*':
                        self.star_import = self.star_import or (node.module == 'numpy' and not node.level)
                    elif node.module and not node.level and _is_numpy(node.module):
                        self.aliases[name.asname or name.name] = '%s.%s' % (node.module, name.name)
                    else:
                        rebound.add(name.asname or name.name)
            elif isinstance(node, ast.Name) and not isinstance(node.ctx, ast.Load):
                rebound.add(node.id)
            elif isinstance(node, ast.arg):
                rebound.add(node.arg)
            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                rebound.add(node.name)

        # a name assigned something other than NumPy isn't NumPy any more
        for name in rebound:
            self.aliases.pop(name, None)

    def _scan_imports(self):
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    if _is_numpy(name.name):
                        self._check(name.name, name.name, node)
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level and _is_numpy(node.module):
                self._check(node.module, node.module, node)
                for name in node.names:
                    if name.name != '*':
                        path = '%s.%s' % (node.module, name.name)
                        self._check(path, path, node)

    def _scan_references(self):
        inner = set()
        chains = []
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Attribute):
                chains.append(node)
                if isinstance(node.value, ast.Attribute):
                    inner.add(id(node.value))
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and self.star_import:
                if node.id in NUMPY2_REMOVED and node.id not in self.rebound:
                    self._check('numpy.%s' % node.id, 'numpy.%s' % node.id, node)

        for node in chains:
            # only the whole of `np.a.b.c`, not also `np.a.b` and `np.a`
            if id(node) in inner or not isinstance(node.ctx, ast.Load):
                continue
            resolved = self._resolve(node)
            if resolved:
                self._check(*resolved, node)

    def _scan_calls(self):
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.Call):
                continue

            resolved = self._resolve(node.func)
            path = resolved[0] if resolved else None
            keywords = {kw.arg: kw.value for kw in node.keywords if kw.arg}

            if path == 'numpy.array' and _is_false(keywords.get('copy')):
                msg = _(
                    'In NumPy 2, `np.array(..., copy=False)` raises an error whenever a copy '
                    "can't be avoided. Use `np.asarray(...)` instead."
                )
                self._add(WARNING, msg, node)
            elif path == 'numpy.linalg.lstsq' and len(node.args) < 3 and 'rcond' not in keywords:
                msg = _(
                    'NumPy 2 changed the default `rcond` of `np.linalg.lstsq`, which can change the '
                    'fit for poorly conditioned data. Pass `rcond=None` to accept the new default '
                    'explicitly, or `rcond=-1` to keep the old one.'
                )
                self._add(WARNING, msg, node)
            elif path is None and isinstance(node.func, ast.Attribute) and node.func.attr in NUMPY2_REMOVED_METHODS:
                receiver = node.func.value
                is_dtype = isinstance(receiver, ast.Attribute) and receiver.attr == 'dtype'
                if node.func.attr == 'newbyteorder' and is_dtype:
                    continue
                msg = _(
                    'If `%(receiver)s` is a NumPy array: arrays have no `.%(method)s()` method in NumPy 2. %(hint)s'
                ) % {
                    'receiver': ast.unparse(receiver),
                    'method': node.func.attr,
                    'hint': NUMPY2_REMOVED_METHODS[node.func.attr],
                }
                self._add(WARNING, msg, node)

    def _resolve(self, node):
        """Return (numpy path, name as written) if `node` is e.g. `np.linalg.lstsq`"""
        attrs = []
        while isinstance(node, ast.Attribute):
            attrs.append(node.attr)
            node = node.value
        if not (isinstance(node, ast.Name) and node.id in self.aliases):
            return None
        attrs.reverse()
        path = '.'.join([self.aliases[node.id]] + attrs)
        written = '.'.join([node.id] + attrs)
        return path, written

    def _check(self, path, written, node):
        """Report a reference to NumPy's `path` (e.g. 'numpy.linalg.lstsq') if it's a problem"""

        parts = path.split('.')[1:]
        written_parts = written.split('.')
        # how many leading parts of `written` stand for `numpy` itself
        offset = len(written_parts) - len(parts)

        def as_written(n):
            return '.'.join(written_parts[: max(offset + n, 1)])

        for n in range(1, len(parts) + 1):
            key = '.'.join(parts[:n])
            if offset < 1 and offset + n <= 1 and (key in NUMPY2_REMOVED or key in NUMPY2_DEPRECATED):
                # The problem is the aliased module itself (`import numpy.core as nc`),
                # which was already reported where it was imported.
                return
            if key in NUMPY2_REMOVED:
                msg = _('`%(name)s` does not exist in NumPy 2. %(hint)s') % {
                    'name': as_written(n),
                    'hint': NUMPY2_REMOVED[key],
                }
                # it still works if NumPy 1 is installed; it fails if NumPy 2 is
                self._add(ERROR if NUMPY_MAJOR >= 2 else WARNING, msg, node)
                return
            if key in NUMPY2_DEPRECATED:
                self._add(WARNING, NUMPY2_DEPRECATED[key], node)
                return

        # Anything else is looked up in the NumPy that's installed, which
        # catches names it has removed that the table above doesn't know about,
        # and anything it merely warns about. Only attributes of NumPy's own
        # modules and classes are read; nothing is called.
        obj = numpy
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            for n, part in enumerate(parts, start=1):
                try:
                    obj = getattr(obj, part)
                except AttributeError as e:
                    msg = _('`%(name)s` does not exist in the installed NumPy (%(version)s).') % {
                        'name': as_written(n),
                        'version': NUMPY_VERSION,
                    }
                    detail = str(e).splitlines()[0] if str(e) else ''
                    if detail and 'has no attribute' not in detail:
                        # NumPy's own explanation, e.g. "`np.NaN` was removed in the NumPy 2.0 release..."
                        msg = '%s %s' % (msg, detail)
                    self._add(ERROR, msg, node)
                    return
                except Exception:
                    # a lazily imported submodule failed to import: not something to guess about
                    return

        for w in caught:
            if issubclass(w.category, DeprecationWarning | FutureWarning):
                msg = _('`%(name)s`: %(warning)s') % {
                    'name': written,
                    'warning': str(w.message).splitlines()[0],
                }
                self._add(WARNING, msg, node)


def _is_numpy(module):
    return module == 'numpy' or module.startswith('numpy.')


def _is_false(node):
    return isinstance(node, ast.Constant) and node.value is False


###############################################################################
# Recalculation
###############################################################################


class _CheckUtils(CompositeUtils):
    """The UTILS object for a recalculation: files are converted but never saved"""

    def write_file(self, fname, obj):
        # Convert the object just as the real write_file does, so an object
        # that can no longer be converted still fails, but store nothing.
        fname = os.path.basename(fname)
        if imsave(obj, fname) is None:
            to_bytes(obj, fname)


def _use_check_utils(calculation_context, exclude_test_list_instance_id):
    utils = calculation_context.get('UTILS')
    if utils is None:
        return
    check_utils = _CheckUtils(
        utils.user,
        utils.unit,
        utils.test_list,
        utils.meta,
        utils.context,
        utils.comments,
        utils.skips,
    )
    check_utils.exclude_test_list_instance_id = exclude_test_list_instance_id
    calculation_context['UTILS'] = check_utils


class _CheckCompositePerformer(CompositePerformer):
    def __init__(self, user, data, exclude_test_list_instance_id=None):
        super().__init__(user, data)
        self.exclude_test_list_instance_id = exclude_test_list_instance_id

    def set_calculation_context(self):
        super().set_calculation_context()
        _use_check_utils(self.calculation_context, self.exclude_test_list_instance_id)


class _CheckUploadHandler(UploadHandler):
    def __init__(self, user, data, exclude_test_list_instance_id=None):
        super().__init__(user, data, None)
        self.exclude_test_list_instance_id = exclude_test_list_instance_id

    def set_calculation_context(self):
        super().set_calculation_context()
        _use_check_utils(self.calculation_context, self.exclude_test_list_instance_id)

    def run_calc(self):
        try:
            return super().run_calc()
        finally:
            # UploadHandler leaves the file it opened for the procedure open.
            # One upload is harmless; hundreds in a row are not.
            context = getattr(self, 'calculation_context', {})
            if context.get('FILE') is not None:
                context['FILE'].close()
            if context.get('BIN_FILE') is not None:
                context['BIN_FILE'].close()
            cleanup_matplotlib()


@dataclass
class Job:
    """
    One piece of recalculation work, small enough to run in a single web
    request: every composite and default value procedure of one saved test
    list instance ('list'), one upload test of one saved instance ('upload'),
    or one sample file ('sample').
    """

    kind: str
    test_ids: list
    test_list_instance_id: int = None
    attachment_id: int = None

    KINDS = ('list', 'upload', 'sample')

    def as_dict(self):
        return {
            'kind': self.kind,
            'test_ids': self.test_ids,
            'test_list_instance_id': self.test_list_instance_id,
            'attachment_id': self.attachment_id,
        }

    @classmethod
    def from_dict(cls, data):
        """Rebuild a Job from as_dict() output (e.g. posted back by the admin page)"""

        def optional_int(value):
            return None if value is None else int(value)

        kind = data.get('kind')
        if kind not in cls.KINDS:
            raise ValueError('Invalid job kind: %r' % kind)
        test_ids = [int(t) for t in data.get('test_ids') or []]
        if not test_ids:
            raise ValueError('A job needs at least one test')
        job = cls(
            kind, test_ids, optional_int(data.get('test_list_instance_id')), optional_int(data.get('attachment_id'))
        )
        if kind == 'sample' and job.attachment_id is None:
            raise ValueError('A sample job needs an attachment')
        if kind != 'sample' and job.test_list_instance_id is None:
            raise ValueError('A %s job needs a test list instance' % kind)
        return job


def plan_recalculations(tests, units=None):
    """
    Work out what to recalculate for `tests`: the most recent saved,
    completed, non-skipped result of each test on each unit it is currently
    assigned to (optionally only `units`), plus any sample files attached to
    upload tests.
    """

    tests = {t.pk: t for t in tests}
    if not tests:
        return []

    latest = (
        models.TestInstance.objects.filter(
            unit_test_info=OuterRef('pk'),
            skipped=False,
            test_list_instance__in_progress=False,
        )
        .order_by('-work_completed', '-pk')
        .values('test_list_instance_id')[:1]
    )

    utis = models.UnitTestInfo.objects.filter(test_id__in=tests, active=True)
    if units is not None:
        utis = utis.filter(unit__in=units)
    rows = utis.annotate(tli_id=Subquery(latest)).filter(tli_id__isnull=False).values_list('test_id', 'tli_id')

    by_instance = defaultdict(set)
    upload_jobs = []
    for test_id, tli_id in rows:
        if tests[test_id].type == models.UPLOAD:
            upload_jobs.append(Job('upload', [test_id], tli_id))
        else:
            by_instance[tli_id].add(test_id)

    jobs = [Job('list', sorted(ids), tli_id) for tli_id, ids in sorted(by_instance.items())]
    jobs.extend(sorted(upload_jobs, key=lambda j: (j.test_ids, j.test_list_instance_id)))

    uploads = [pk for pk, t in tests.items() if t.type == models.UPLOAD]
    samples = sample_files(uploads).order_by('test_id', 'pk').values_list('test_id', 'pk')
    jobs.extend(Job('sample', [test_id], attachment_id=pk) for test_id, pk in samples)

    return jobs


def sample_files(tests):
    """Files attached to (upload) tests to be run through their procedures as samples"""
    return Attachment.objects.filter(test__in=tests, label__istartswith=SAMPLE_FILE_LABEL)


def run_job(job, user=None, rtol=DEFAULT_RTOL, atol=DEFAULT_ATOL):
    """
    Run one Job and return a list of (test id, Recalculation). If the check
    itself fails, every test in the job is reported as broken with the reason,
    rather than the exception escaping and ending a long run early.
    """
    runners = {'list': _run_list_job, 'upload': _run_upload_job, 'sample': _run_sample_job}
    try:
        with transaction.atomic():
            try:
                return runners[job.kind](job, user, rtol, atol)
            finally:
                # A check must leave the database exactly as it found it,
                # whatever the procedures it ran did.
                transaction.set_rollback(True)
    except Exception:
        detail = traceback.format_exc()
        msg = _('The check could not be run: %(error)s') % {'error': detail.strip().splitlines()[-1]}
        return [(test_id, Recalculation(ERROR, _describe_job(job), msg, detail=detail)) for test_id in job.test_ids]


def check_tests(
    tests,
    recalculate=True,
    units=None,
    user=None,
    rtol=DEFAULT_RTOL,
    atol=DEFAULT_ATOL,
    progress=None,
):
    """
    Scan, and optionally recalculate, `tests` and return a TestCheck for each
    one in the same order. `progress(done, total, job)` is called before each
    recalculation job if given.
    """
    tests = list(tests)
    checks = {t.pk: TestCheck(t, scan_procedure(t.calculation_procedure), [], recalculate) for t in tests}
    if recalculate:
        jobs = plan_recalculations(tests, units=units)
        for n, job in enumerate(jobs):
            if progress:
                progress(n, len(jobs), job)
            for test_id, recalculation in run_job(job, user=user, rtol=rtol, atol=atol):
                checks[test_id].recalculations.append(recalculation)
    return list(checks.values())


def _load_instance(tli_id):
    tli = models.TestListInstance.objects.select_related(
        'test_list',
        'unit_test_collection__unit',
        'created_by',
    ).get(pk=tli_id)
    instances = tli.testinstance_set.select_related('unit_test_info__test')
    return tli, {ti.unit_test_info.test_id: ti for ti in instances}


def _run_list_job(job, user, rtol, atol):
    tli, instances = _load_instance(job.test_list_instance_id)
    source = _describe_instance(tli)
    data = _calculation_data(tli, instances)
    user = user or tli.created_by

    tests = list(models.Test.objects.filter(pk__in=job.test_ids).order_by('name'))
    in_list = set(tli.test_list.all_tests().values_list('pk', flat=True))
    composites = [t for t in tests if t.pk in in_list and t.type in models.COMPOSITE_TYPES]
    defaults = [t for t in tests if t.pk in in_list and t.type not in models.CALCULATED_TYPES]

    def finish(test, recalc, calculation=None):
        recalc.source, recalc.test_list_instance_id = source, tli.pk
        if calculation:
            recalc.warnings = calculation['warnings'].get(test.slug, [])
        return test.pk, recalc

    # e.g. a test removed from the list since this result was saved
    results = [
        finish(test, Recalculation(NOT_RUN, '', _('This test is no longer part of the test list.')))
        for test in tests
        if test.pk not in in_list
    ]
    if composites:
        calculation = _calculate_composites(user, data, tli.pk, defaults=False)
        for test in composites:
            recalc = _composite_recalculation(test, instances.get(test.pk), calculation, data, rtol, atol)
            results.append(finish(test, recalc, calculation))

    if defaults:
        calculation = _calculate_composites(user, data, tli.pk, defaults=True)
        for test in defaults:
            results.append(finish(test, _default_recalculation(test, calculation, data), calculation))

    return results


def _run_upload_job(job, user, rtol, atol):
    tli, instances = _load_instance(job.test_list_instance_id)
    source = _describe_instance(tli)
    test = models.Test.objects.get(pk=job.test_ids[0])
    ti = instances.get(test.pk)

    def result(status, message='', **kwargs):
        return [(test.pk, Recalculation(status, source, message, test_list_instance_id=tli.pk, **kwargs))]

    try:
        attachment = Attachment.objects.get(pk=int(ti.string_value))
    except (AttributeError, TypeError, ValueError, Attachment.DoesNotExist):
        return result(NOT_RUN, _('The file uploaded for this result no longer exists.'))
    if not attachment.file_exists:
        return result(
            NOT_RUN,
            _('The file uploaded for this result (%(name)s) is missing from storage.')
            % {'name': _file_name(attachment)},
        )

    data = dict(_calculation_data(tli, instances), test_id=test.pk, attachment_id=attachment.pk)
    outcome, warned = _process_upload(test, user or tli.created_by, data, tli.pk)
    result = functools.partial(result, warnings=warned)
    if outcome.get('errors'):
        error = _error('\n'.join(outcome['errors']))
        return result(ERROR, error.message, detail=error.detail)

    try:
        recalculated = _as_json(outcome.get('result'))
    except (TypeError, ValueError) as e:
        return result(
            ERROR, _("The result can't be saved because it can't be converted to JSON: %(error)s") % {'error': e}
        )

    saved = ti.json_value
    shown = {'saved': _display(saved), 'recalculated': _display(recalculated)}
    if saved is None:
        return result(OK, _('Ran without errors (no saved result to compare with).'), **shown)
    if _same(saved, recalculated, rtol, atol):
        return result(OK, **shown)
    return result(CHANGED, _('The result differs from the one saved.'), **shown)


def _run_sample_job(job, user, rtol, atol):
    attachment = Attachment.objects.select_related('test').get(pk=job.attachment_id)
    test = attachment.test
    source = _('Sample file %(name)s') % {'name': _file_name(attachment)}

    def result(status, message='', **kwargs):
        return [(test.pk, Recalculation(status, source, message, **kwargs))]

    if not attachment.file_exists:
        return result(NOT_RUN, _('The sample file is missing from storage.'))

    context = _sample_context(test, user)
    if context is None:
        return result(NOT_RUN, _('This test is not assigned to any unit, so there is no unit to run it for.'))
    data, exclude_tli_id, context_user = context

    data = dict(data, test_id=test.pk, attachment_id=attachment.pk)
    outcome, warned = _process_upload(test, user or context_user, data, exclude_tli_id)
    result = functools.partial(result, warnings=warned)
    if outcome.get('errors'):
        error = _error('\n'.join(outcome['errors']))
        return result(ERROR, error.message, detail=error.detail)

    try:
        recalculated = _as_json(outcome.get('result'))
    except (TypeError, ValueError) as e:
        return result(
            ERROR, _("The result can't be saved because it can't be converted to JSON: %(error)s") % {'error': e}
        )
    return result(OK, _('Ran without errors.'), recalculated=_display(recalculated))


def _sample_context(test, user):
    """
    The data to run a sample file with, as (data, test list instance to leave
    out of UTILS lookups, user). The latest saved result of the test is used if
    there is one, since it has realistic META, REFS and TOLS; otherwise a
    freshly opened Perform QC page on a unit the test is assigned to.
    """
    latest = (
        models.TestInstance.objects.filter(
            unit_test_info__test=test,
            unit_test_info__active=True,
            test_list_instance__in_progress=False,
        )
        .order_by('-work_completed', '-pk')
        .values_list('test_list_instance_id', flat=True)
        .first()
    )
    if latest is not None:
        tli, instances = _load_instance(latest)
        return _calculation_data(tli, instances), tli.pk, tli.created_by

    uti = (
        models.UnitTestInfo.objects.filter(test=test, active=True)
        .select_related('unit')
        .order_by('unit__number')
        .first()
    )
    membership = models.TestListMembership.objects.filter(test=test).select_related('test_list').order_by('pk').first()
    if uti is None or membership is None:
        return None

    unit, test_list = uti.unit, membership.test_list
    utc = models.UnitTestCollection.objects.filter(
        unit=unit,
        content_type=ContentType.objects.get_for_model(models.TestList),
        object_id=test_list.pk,
    ).first()

    now = timezone.now()
    tests = list(test_list.all_tests())
    data = {
        'tests': {t.slug: _as_posted(t.constant_value) if t.type == models.CONSTANT else None for t in tests},
        'meta': _meta(utc, test_list, unit, 0, now, now, user.username if user else ''),
        'test_list_id': test_list.pk,
        'unit_id': unit.pk,
        'comments': {t.slug: '' for t in tests},
        'skips': {t.slug: False for t in tests},
    }
    return data, None, user


def _calculation_data(tli, instances):
    """
    The data the Perform QC page posts to calculate a test list's composites
    and uploads when `tli` is opened for editing, rebuilt from what was saved
    (see calculate_composites_ and get_meta_data in qa/static/qa/js/qa.js).
    """
    tests = list(tli.test_list.all_tests())
    values, comments, skips = {}, {}, {}
    for test in tests:
        ti = instances.get(test.pk)
        values[test.slug] = _posted_value(test, ti)
        comments[test.slug] = (ti.comment if ti else '') or ''
        skips[test.slug] = bool(ti and ti.skipped)

    unit = tli.unit_test_collection.unit
    return {
        'tests': values,
        'meta': _meta(
            tli.unit_test_collection,
            tli.test_list,
            unit,
            tli.day,
            tli.work_started,
            tli.work_completed,
            tli.created_by.username,
        ),
        'test_list_id': tli.test_list_id,
        'unit_id': unit.pk,
        'comments': comments,
        'skips': skips,
    }


def _meta(utc, test_list, unit, day, work_started, work_completed, username):
    return {
        # the page reads these from hidden inputs, so they arrive as strings...
        'unit_test_collection_id': str(utc.pk) if utc else '',
        'test_list_id': str(test_list.pk),
        'test_list_name': test_list.name,
        # ...and parses these to integers
        'unit_number': unit.number,
        'cycle_day': day + 1,
        'work_completed': _as_input(work_completed, 'DATETIME_INPUT_FORMATS'),
        'work_started': _as_input(work_started, 'DATETIME_INPUT_FORMATS'),
        'username': username,
    }


def _posted_value(test, ti):
    """The value the Perform QC page would post for a saved test instance"""

    if ti is None or ti.skipped or test.type in models.COMPOSITE_TYPES:
        # composites are always posted empty; that's what is being calculated
        return None
    if test.type == models.UPLOAD:
        # the result of analysing the upload, not the file
        return ti.json_value
    if test.type in models.STRING_TYPES:
        return ti.string_value
    if test.type == models.DATE:
        return _as_input(ti.date_value, 'DATE_INPUT_FORMATS')
    if test.type == models.DATETIME:
        return _as_input(ti.datetime_value, 'DATETIME_INPUT_FORMATS')
    return _as_posted(ti.value)


def _as_posted(value):
    """
    A number as it reaches a procedure from the browser. JSON.stringify writes
    whole numbers without a decimal point, so a procedure receives 2, not 2.0,
    and that difference shows whenever a procedure puts the number in a string.
    """
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        if value.is_integer() and abs(value) < 1e21:  # JavaScript switches to exponents at 1e21
            return int(value)
    return value


def _as_input(value, format_name):
    """Format a date or datetime as the Perform QC page's inputs do, in a format the views parse back"""
    if value is None:
        return None
    if isinstance(value, datetime.datetime) and timezone.is_aware(value):
        value = timezone.localtime(value)
    return value.strftime(get_format(format_name)[0])


def _calculate_composites(user, data, tli_id, defaults):
    """Run CompositePerformer, returning its result, or the traceback if it crashed outright"""
    data = copy.deepcopy(data)
    if defaults:
        data['defaults'] = True
    performer = _CheckCompositePerformer(user, data, tli_id)
    try:
        with _procedure_warnings() as warned:
            outcome = performer.calculate()
    except Exception:
        # e.g. a procedure that can't be tokenized stops the whole test list
        return {'crash': traceback.format_exc(limit=3), 'performer': performer, 'warnings': {}}
    return {'outcome': outcome, 'performer': performer, 'warnings': warned}


def _process_upload(test, user, data, exclude_tli_id):
    """Run an upload test's procedure, returning UploadHandler's result and the procedure's warnings"""
    with _procedure_warnings() as warned:
        outcome = _CheckUploadHandler(user, data, exclude_tli_id).process()
    return outcome, warned.get(test.slug, [])


@contextlib.contextmanager
def _procedure_warnings(limit=10):
    """
    Collect the deprecation warnings procedures trigger while they run, as
    {macro name: [description, ...]}.

    A warning counts if it points at the procedure's own code, or at the line
    in views/perform.py that runs the procedure: libraries sometimes point one
    frame too far (NumPy 1.25/1.26's deprecation of `np.product` does), so the
    procedure's line is found on the live stack rather than taken from the
    warning. Warnings pointing inside a library are that library's business
    and are left out.
    """
    found = defaultdict(list)

    def record(message, category, filename, lineno, file=None, line=None):
        filename = str(filename)
        at_procedure = filename.startswith(PROCEDURE_FILE_PREFIX)
        if not issubclass(category, UPGRADE_WARNINGS):
            return
        if not (at_procedure or os.path.normcase(filename) == PERFORM_FILE):
            return

        frame = sys._getframe(1)
        while frame is not None and not frame.f_code.co_filename.startswith(PROCEDURE_FILE_PREFIX):
            frame = frame.f_back
        if frame is None:
            return

        slug = frame.f_code.co_filename[len(PROCEDURE_FILE_PREFIX) :].removesuffix('.py')
        text = _('Line %(line)s: %(category)s: %(message)s') % {
            'line': lineno if at_procedure else frame.f_lineno,
            'category': category.__name__,
            'message': str(message).splitlines()[0],
        }
        if text not in found[slug] and len(found[slug]) < limit:
            found[slug].append(text)

    # catch_warnings restores both the filters and showwarning afterwards
    with _WARNINGS_LOCK, warnings.catch_warnings():
        warnings.simplefilter('always')
        warnings.showwarning = record
        yield found


def _composite_recalculation(test, ti, calculation, data, rtol, atol):
    failure = _calculation_failure(calculation)
    if failure:
        return failure

    result = calculation['outcome']['results'].get(test.slug)
    if result is None or ti is None:
        return Recalculation(NOT_RUN, '', _('This test is no longer part of the test list.'))
    if result['error']:
        return _error(result['error'])
    if result['value'] is None:
        return _missing_inputs(test, calculation, data)

    value = result['value']
    if test.type == models.STRING_COMPOSITE:
        saved = ti.string_value
        same = _same_string_result(saved, value, rtol, atol)
    else:
        saved = ti.value
        same = _same_number(saved, value, rtol, atol)

    shown = {'saved': _display(saved), 'recalculated': _display(value)}
    if same:
        return Recalculation(OK, '', **shown)

    message = _('The result differs from the one saved.')
    difference = _relative_difference(saved, value)
    if difference is not None:
        message = _('The result differs from the one saved (relative difference %(difference).2g).') % {
            'difference': difference,
        }
    return Recalculation(CHANGED, '', message, **shown)


def _default_recalculation(test, calculation, data):
    failure = _calculation_failure(calculation)
    if failure:
        return failure

    result = calculation['outcome']['results'].get(test.slug)
    if result is None:
        return Recalculation(NOT_RUN, '', _('This test is no longer part of the test list.'))
    if result['error']:
        return _error(result['error'])
    if result['value'] is None:
        return _missing_inputs(test, calculation, data)
    # A default is only a starting point for the person performing the test,
    # so there is nothing saved to compare it with.
    return Recalculation(
        OK, '', _('Calculated a default value without errors.'), recalculated=_display(result['value'])
    )


def _calculation_failure(calculation):
    if 'crash' in calculation:
        crash = calculation['crash']
        msg = _('Calculating this test list failed before any test could be checked: %(error)s') % {
            'error': crash.strip().splitlines()[-1],
        }
        return Recalculation(ERROR, '', msg, detail=crash)
    if not calculation['outcome']['success']:
        return Recalculation(ERROR, '', '\n'.join(str(e) for e in calculation['outcome']['errors']))
    return None


# "<macro name>", line 3, in ...' - the procedure's own frame, which is where
# CompositePerformer and UploadHandler start the tracebacks they report
_PROCEDURE_FRAME = re.compile(r'line (\d+), in ')


def _error(message):
    """
    A Recalculation for an error reported by CompositePerformer or
    UploadHandler, summarised as e.g. "Line 3: TypeError: ..." with the full
    traceback kept as its detail.
    """
    message = str(message).strip()
    lines = message.splitlines()
    match = _PROCEDURE_FRAME.search(lines[0]) if lines else None
    if not match:
        if len(lines) > 1:
            # a traceback from outside the procedure: its last line is the error
            return Recalculation(ERROR, '', lines[-1].strip(), detail=message)
        # not a traceback at all, e.g. "Cyclic test dependency"
        return Recalculation(ERROR, '', message)

    # the exception is whatever follows the last indented traceback line
    rest = lines[1:]
    last_frame = max((n for n, line in enumerate(rest) if line.startswith(' ')), default=-1)
    exception = ' '.join(line.strip() for line in rest[last_frame + 1 :]) or lines[0]
    summary = _('Line %(line)s: %(error)s') % {'line': match.group(1), 'error': exception}
    return Recalculation(ERROR, '', summary, detail=message)


def _missing_inputs(test, calculation, data):
    """A procedure that wasn't run because some of its inputs are empty or failed"""

    performer = calculation['performer']
    results = calculation['outcome']['results']
    missing = []
    for slug in sorted(performer.all_dependencies.get(test.slug, ())):
        if slug in results:
            if results[slug]['value'] is None or results[slug]['error']:
                missing.append(slug)
        elif data['tests'].get(slug) in (None, ''):
            missing.append(slug)

    if missing:
        msg = _('Not calculated, because these inputs were empty or failed: %(inputs)s') % {
            'inputs': ', '.join(missing),
        }
    else:
        msg = _('Not calculated, because some of its inputs were empty or failed.')
    return Recalculation(NOT_RUN, '', msg)


def _same_number(saved, new, rtol, atol):
    if saved is None:
        return False
    try:
        return _same(float(saved), float(new), rtol, atol)
    except (TypeError, ValueError):
        return False


def _same_string_result(saved, new, rtol, atol):
    """
    Compare a string composite's saved text with a recalculated result. The
    page saves strings as they are and anything else as JSON; results saved
    through the API were converted with str().
    """
    if isinstance(new, str):
        return new == saved
    if saved is None:
        return False
    try:
        new_json = _as_json(new)
    except (TypeError, ValueError):
        return False
    try:
        return _same(json.loads(saved), new_json, rtol, atol)
    except ValueError:
        return str(new) == saved


def _same(saved, new, rtol, atol):
    """Compare saved and recalculated results, allowing for floating point noise in numbers"""
    number = int | float
    if isinstance(saved, number) and isinstance(new, number):
        if math.isnan(saved) or math.isnan(new):
            return math.isnan(saved) and math.isnan(new)
        return math.isclose(saved, new, rel_tol=rtol, abs_tol=atol)
    if isinstance(saved, dict) and isinstance(new, dict):
        return saved.keys() == new.keys() and all(_same(saved[k], new[k], rtol, atol) for k in saved)
    if isinstance(saved, list) and isinstance(new, list):
        return len(saved) == len(new) and all(_same(s, n, rtol, atol) for s, n in zip(saved, new, strict=True))
    return saved == new


def _relative_difference(saved, new):
    try:
        saved, new = float(saved), float(new)
    except (TypeError, ValueError):
        return None
    if saved == 0 or not (math.isfinite(saved) and math.isfinite(new)):
        return None
    return abs(new - saved) / abs(saved)


def _as_json(value):
    """A result as the browser (or API) receives it: through QATrack+'s JSON encoder"""
    return json.loads(json.dumps(value, cls=QATrackJSONEncoder))


def _display(value):
    if value is None:
        return ''
    if isinstance(value, str):
        text = value
    elif isinstance(value, float):
        # float() so NumPy scalars show as numbers, not e.g. np.float64(1.5)
        text = repr(float(value))
    else:
        try:
            text = json.dumps(value, cls=QATrackJSONEncoder)
        except (TypeError, ValueError):
            text = repr(value)
    return text if len(text) <= DISPLAY_LIMIT else text[:DISPLAY_LIMIT] + '...'


def _file_name(attachment):
    return os.path.basename(attachment.attachment.name)


def _describe_instance(tli):
    return _('%(unit)s, %(test_list)s, performed %(date)s') % {
        'unit': tli.unit_test_collection.unit.name,
        'test_list': tli.test_list.name,
        'date': format_datetime(tli.work_completed),
    }


def _describe_job(job):
    if job.kind == 'sample':
        return _('Sample file (attachment %(id)s)') % {'id': job.attachment_id}
    return _('Test list instance %(id)s') % {'id': job.test_list_instance_id}
