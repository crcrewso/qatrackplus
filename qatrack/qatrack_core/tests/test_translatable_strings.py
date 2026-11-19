"""Catch user-facing strings that were never marked for translation.

QATrack+ ships in English, French, French Canadian and Spanish, and has
roughly two thousand marked strings in Python and fifteen hundred in
templates. A string that misses its `_()` does not fail anywhere - it simply
stays English for every other locale, and nobody finds out until a French site
reads it.

This does not try to fix the ones already here. It records them, and fails on
the next one, so the number can only go down.
"""

import ast
import pathlib
import textwrap

QATRACK = pathlib.Path(__file__).resolve().parents[2]
REPO_ROOT = QATRACK.parent

TRANSLATORS = {
    '_', '_l', 'gettext', 'gettext_lazy', 'ugettext', 'ugettext_lazy',
    'pgettext', 'pgettext_lazy', 'ngettext', 'ngettext_lazy', 'npgettext',
}

# Keyword arguments whose value is rendered to a user.
USER_FACING_KWARGS = {
    'verbose_name', 'verbose_name_plural', 'help_text', 'label', 'empty_label',
}

# Calls whose string argument is rendered to a user, and *which* argument that
# is. Iterating every positional argument instead would report the ones that
# are not messages: `ValidationError(message, code)` would flag the code, and
# `messages.success(request, "Saved", "notice")` would flag the extra_tags.
#
#   ValidationError(message, code=None, params=None)
#   messages.<level>(request, message, extra_tags='', fail_silently=False)
#   messages.add_message(request, level, message, extra_tags='', ...)
MESSAGE_ARGUMENT = {
    'ValidationError': 0,
    'success': 1,
    'error': 1,
    'info': 1,
    'warning': 1,
    'debug': 1,
    'add_message': 2,
}
USER_FACING_CALLS = set(MESSAGE_ARGUMENT)

# `messages.success(request, message="Saved")` passes the message by keyword.
MESSAGE_KWARGS = {'message'}

# `messages.warning(request, "...")` is user facing. `logger.warning("...")` is
# not: a log line is read by an administrator in the server's log, and
# translating it would make it unsearchable and locale-dependent. The names above
# are matched on the method alone, so without this the scanner demands that every
# logging call in the project be translated.
LOGGING_RECEIVERS = {'logger', 'log', 'logging', 'LOGGER', '_logger'}

# Strings that are deliberately not translated. Add to this only with a reason.
#
# 'ID' is the verbose_name Django generates for an automatic primary key.
# There are 57 of them, and every locale this project ships already renders it
# unchanged - `msgid "ID"` has `msgstr "ID"` in fr, fr_CA and es. Including
# them would bury three dozen real findings under identity translations.
IGNORED_VALUES = {'ID'}


def _is_translated(node):
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Name):
        return func.id in TRANSLATORS
    if isinstance(func, ast.Attribute):
        return func.attr in TRANSLATORS
    return False


def _receiver(func):
    """What a method is called on: 'logger' in `logger.warning(...)`.

    Handles `self.logger.warning(...)` too, by taking the last attribute name,
    and `logging.getLogger(__name__).warning(...)`, where the receiver is a
    call and so has no name to match - without which that line reads as a
    user-facing message and fails the build.
    """
    value = getattr(func, 'value', None)
    if isinstance(value, ast.Name):
        return value.id
    if isinstance(value, ast.Attribute):
        return value.attr
    if isinstance(value, ast.Call):
        factory = value.func
        name = getattr(factory, 'attr', None) or getattr(factory, 'id', None)
        if name in {'getLogger', 'get_logger'}:
            return 'logger'
    return ''


def _template(node):
    """The literal a user actually reads, out of an interpolated expression.

    `"Error with %s" % name` and `"Error with {}".format(name)` both present a
    literal template, and that template is the string needing translation.
    Returns the node to examine, which may be the one passed in.
    """
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
        return _template(node.left)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == 'format'
    ):
        return _template(node.func.value)
    return node


def _literal_string(node):
    if isinstance(node, ast.JoinedStr):
        # an f-string: its literal parts are user-facing, and an f-string
        # cannot be translated at all, so finding one here is the point.
        #
        # Interpolations are rendered as {} rather than dropped. Joining only
        # the literal parts would report f'Service event {id} deleted' as
        # 'Service event  deleted', which reads as a stray double space in the
        # source and sends whoever fixes it looking for one.
        text = ''.join(
            part.value if isinstance(part, ast.Constant) and isinstance(part.value, str) else '{}'
            for part in node.values
        ).strip()
        if text and text not in IGNORED_VALUES:
            return text
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        text = node.value.strip()
        if text and text not in IGNORED_VALUES:
            return text
    return None


def _message_literals(node):
    """Every untranslated user-facing literal a message argument can hold.

    Django accepts a dict or a list of messages as well as a single one, so
    `ValidationError({"name": "Enter a name"})` has to be looked into rather
    than skipped for not being a string. Dictionary *keys* are field names, not
    text, so only the values are examined.
    """
    node = _template(node)

    if isinstance(node, ast.Dict):
        return [text for value in node.values for text in _message_literals(value)]
    if isinstance(node, ast.List | ast.Tuple):
        return [text for element in node.elts for text in _message_literals(element)]

    if _is_translated(node):
        return []
    text = _literal_string(node)
    return [text] if text else []


def find_untranslated():
    """Every user-facing literal that is not wrapped in a translation call.

    Keyed by (path, kind, text) rather than by line, so that moving code around
    does not look like a new finding.
    """
    found = set()

    for path in sorted(QATRACK.rglob('*.py')):
        relative = path.relative_to(REPO_ROOT)
        # as_posix(), not str(): the baseline is a checked-in file read on
        # every platform, and str() would write it with backslashes on
        # Windows. Every entry would then miss, the remaining debt would read
        # as new findings, and the suite would be red on Windows only.
        key = relative.as_posix()
        parts = relative.parts
        # Migrations carry a frozen copy of old field definitions; tests are
        # not user facing.
        if 'migrations' in parts or 'tests' in parts:
            continue

        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except (SyntaxError, UnicodeDecodeError):
            continue

        found |= untranslated_in_tree(tree, key)

    return found


def untranslated_in_tree(tree, key=''):
    """The findings in one parsed module.

    Split out from `find_untranslated` so the detection can be tested against
    a snippet rather than only against the repository, which is the difference
    between knowing the rules work and knowing today's tree happens to pass.
    """
    found = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        for keyword in node.keywords:
            if keyword.arg in USER_FACING_KWARGS and not _is_translated(keyword.value):
                text = _literal_string(keyword.value)
                if text:
                    found.add((key, keyword.arg, text))

        name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, 'id', '')
        if name in USER_FACING_CALLS and _receiver(node.func) not in LOGGING_RECEIVERS:
            index = MESSAGE_ARGUMENT[name]
            arguments = []
            if len(node.args) > index:
                arguments.append(node.args[index])
            arguments.extend(k.value for k in node.keywords if k.arg in MESSAGE_KWARGS)
            for argument in arguments:
                for text in _message_literals(argument):
                    found.add((key, name, text))

    return found


BASELINE_PATH = pathlib.Path(__file__).with_name('untranslated_baseline.json')


def _load_baseline():
    import json
    return {tuple(row) for row in json.loads(BASELINE_PATH.read_text(encoding='utf-8'))}


def test_no_new_untranslated_user_facing_strings():
    """A ratchet, not a cleanup.

    The strings already recorded in untranslated_baseline.json are a debt to
    pay down when someone is in the area. What this stops is the debt growing:
    a new verbose_name, help_text, label, ValidationError or flash message that
    nobody can translate.

    To fix a finding, wrap it:

        from django.utils.translation import gettext_lazy as _l
        help_text=_l("Current status of this issue")

    and delete its line from the baseline. The baseline should only ever
    shrink.
    """
    baseline = _load_baseline()
    current = find_untranslated()

    new = sorted(current - baseline)
    assert not new, (
        "%d user-facing string(s) are not marked for translation:\n\n%s\n\n"
        "Wrap them with gettext_lazy (imported as _l in this codebase). If a "
        "string genuinely should not be translated - a code, a unit symbol - "
        "add it to IGNORED_VALUES with a note saying why."
        % (len(new), '\n'.join('  %s\n    %s=%r' % (p, k, t) for p, k, t in new))
    )


def test_baseline_has_no_stale_entries():
    """A fixed string must be removed from the baseline, or it protects nothing.

    Without this, the file accumulates entries for code that no longer exists
    and stops describing anything real.
    """
    baseline = _load_baseline()
    current = find_untranslated()

    stale = sorted(baseline - current)
    assert not stale, (
        "%d baseline entr(ies) no longer match anything - the string was "
        "translated, moved or deleted. Remove them from %s:\n\n%s"
        % (len(stale), BASELINE_PATH.name,
           '\n'.join('  %s\n    %s=%r' % (p, k, t) for p, k, t in stale))
    )


def test_baseline_paths_are_posix():
    """The baseline is one file, read on every platform.

    ``find_untranslated`` keys on ``Path.as_posix()``, so an entry written
    with backslashes can never match - which is invisible on Linux and turns
    the whole remaining debt into "new findings" on Windows. Regenerating the
    baseline on a Windows checkout is the way that happens.
    """
    backslashed = sorted(path for path, _, _ in _load_baseline() if '\\' in path)
    assert not backslashed, (
        "%d baseline path(s) use backslashes. Rewrite them with forward "
        "slashes in %s:\n\n%s"
        % (len(backslashed), BASELINE_PATH.name, '\n'.join('  %s' % p for p in backslashed))
    )


def test_logging_calls_are_not_user_facing():
    """`logger.warning(...)` must not be demanded for translation.

    The names in ``USER_FACING_CALLS`` - warning, error, info, debug - exist for
    ``django.contrib.messages``, and were matched on the method name alone. That
    also matches every logging call in the project, so the scanner asked for log
    lines to be translated. A log line is read by an administrator in the
    server's log; translating it makes it locale-dependent and unsearchable.

    Asserted against parsed source rather than the tree, so it states the rule
    instead of depending on which calls happen to exist today.
    """
    source = textwrap.dedent(
        '''
        from django.contrib import messages
        logger = logging.getLogger(__name__)

        def f(request):
            logger.warning("a log line")
            logger.error("another %s", x)
            logging.info("a third")
            self.logger.debug("a fourth")
            messages.warning(request, "a message to a person")
        '''
    )
    tree = ast.parse(source)
    flagged = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, 'id', '')
        if name in USER_FACING_CALLS and _receiver(node.func) not in LOGGING_RECEIVERS:
            for argument in node.args:
                text = _literal_string(argument)
                if text:
                    flagged.add(text)

    assert flagged == {"a message to a person"}, flagged


def scan(code):
    """What the scanner finds in a snippet, as a set of (kind, text)."""
    return {(kind, text) for _key, kind, text in untranslated_in_tree(ast.parse(textwrap.dedent(code)))}


class TestDetection:
    """The rules themselves, against snippets.

    The two tests above only say that today's tree passes, which it would also
    do if the rules caught nothing. These say what the rules actually catch.
    """

    def test_a_plain_literal(self):
        assert scan('ValidationError("Enter a name")') == {('ValidationError', 'Enter a name')}

    def test_a_translated_literal_is_left_alone(self):
        assert scan('ValidationError(_("Enter a name"))') == set()

    # interpolated messages: the template is the thing needing translation

    def test_percent_interpolation(self):
        assert scan('ValidationError("Error with %s test" % slug)') == {
            ('ValidationError', 'Error with %s test')
        }

    def test_str_format(self):
        assert scan('ValidationError("Error with {} test".format(slug))') == {
            ('ValidationError', 'Error with {} test')
        }

    def test_an_f_string(self):
        """An f-string cannot be translated at all, so finding one is the point."""
        assert scan('messages.success(request, f"Deleted event {pk} now")') == {
            ('success', 'Deleted event {} now')
        }

    def test_a_translated_template_is_left_alone(self):
        """`_("a %s") % x` is the correct idiom and must not be reported."""
        assert scan('ValidationError(_("Error with %s test") % slug)') == set()
        assert scan('ValidationError(_("Error with {} test").format(slug))') == set()

    # only the argument that carries the message

    def test_validation_error_code_is_not_a_message(self):
        assert scan('ValidationError(_("Bad"), "invalid_choice")') == set()

    def test_extra_tags_is_not_a_message(self):
        assert scan('messages.success(request, _("Saved"), "notice")') == set()

    def test_the_request_is_not_a_message(self):
        assert scan('messages.success(request, "Saved")') == {('success', 'Saved')}

    def test_add_message_takes_the_third_argument(self):
        assert scan('messages.add_message(request, messages.INFO, "Saved")') == {
            ('add_message', 'Saved')
        }

    def test_a_message_passed_by_keyword(self):
        assert scan('messages.success(request, message="Saved")') == {('success', 'Saved')}

    # Django accepts containers of messages

    def test_a_dict_of_messages(self):
        """The keys are field names, not text, so only the values are examined."""
        assert scan('ValidationError({"name": "Enter a name"})') == {
            ('ValidationError', 'Enter a name')
        }

    def test_a_list_of_messages(self):
        assert scan('ValidationError(["Enter a name", _("Already taken")])') == {
            ('ValidationError', 'Enter a name')
        }

    # logging is not user facing

    def test_a_named_logger(self):
        assert scan('logger.warning("Retry failed")') == set()

    def test_a_logger_on_self(self):
        assert scan('self.logger.warning("Retry failed")') == set()

    def test_a_logger_created_inline(self):
        """`logging.getLogger(__name__).warning(...)` has no receiver *name*."""
        assert scan('logging.getLogger(__name__).warning("Retry failed")') == set()

    # keyword arguments rendered to a user

    def test_help_text(self):
        assert scan('models.CharField(help_text="Current status")') == {
            ('help_text', 'Current status')
        }

    def test_translated_help_text_is_left_alone(self):
        assert scan('models.CharField(help_text=_l("Current status"))') == set()
