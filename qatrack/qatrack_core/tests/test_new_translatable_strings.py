"""The CI step that reports which strings a change adds.

Covered because its predecessor was wrong in a way no test would have caught:
it grepped `^+msgid "` out of the PO diff, which cannot see a long message,
since gettext writes those as `msgid ""` plus quoted continuation lines. Every
real validation message was missing from the count and nothing said so.
"""

import importlib.util
import pathlib

import pytest

polib = pytest.importorskip('polib', reason="only installed with the translations extra")

SCRIPT = pathlib.Path(__file__).resolve().parents[3] / '.github' / 'scripts' / 'new_translatable_strings.py'

HEADER = 'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n'

LONG = (
    'A long validation message that gettext wrapped across several lines '
    'because it is well past the width limit and so has an empty msgid header line'
)


def load():
    spec = importlib.util.spec_from_file_location('new_translatable_strings', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def catalogues(tmp_path):
    """A before/after pair of catalogues for two locales."""

    def build(after_body, before_body='msgid "Existing"\nmsgstr "Existante"\n'):
        before = tmp_path / 'before'
        before.mkdir(exist_ok=True)
        locales = tmp_path / 'locale'
        for locale in ('es', 'fr'):
            (before / ('%s.po' % locale)).write_text(HEADER + before_body, encoding='utf-8')
            directory = locales / locale / 'LC_MESSAGES'
            directory.mkdir(parents=True, exist_ok=True)
            (directory / 'django.po').write_text(HEADER + after_body, encoding='utf-8')
        return locales, before

    return build


def test_a_short_string_is_found(catalogues):
    locales, before = catalogues('msgid "Existing"\nmsgstr "Existante"\n\nmsgid "New one"\nmsgstr ""\n')
    assert load().new_msgids(locales, before) == ['New one']


def test_a_multiline_string_is_found(catalogues):
    """The whole reason this script exists."""
    body = (
        'msgid "Existing"\nmsgstr "Existante"\n\n'
        'msgid ""\n'
        '"A long validation message that gettext wrapped across several lines because "\n'
        '"it is well past the width limit and so has an empty msgid header line"\n'
        'msgstr ""\n'
    )
    locales, before = catalogues(body)
    assert load().new_msgids(locales, before) == [LONG]


def test_a_string_in_every_locale_is_counted_once(catalogues):
    """`makemessages --all` adds it to each catalogue, and it is one string."""
    locales, before = catalogues('msgid "Existing"\nmsgstr "Existante"\n\nmsgid "New one"\nmsgstr ""\n')
    assert load().new_msgids(locales, before).count('New one') == 1


def test_nothing_new_is_nothing(catalogues):
    locales, before = catalogues('msgid "Existing"\nmsgstr "Existante"\n')
    assert load().new_msgids(locales, before) == []


def test_the_header_is_not_a_string(catalogues):
    """The header is an entry whose msgid is empty; reporting it would be noise."""
    locales, before = catalogues('msgid "Existing"\nmsgstr "Existante"\n')
    assert '' not in load().new_msgids(locales, before)


def test_a_missing_previous_catalogue_reports_everything(catalogues):
    """A newly added locale has no committed catalogue to compare against."""
    locales, before = catalogues('msgid "Only one"\nmsgstr ""\n')
    for stale in before.glob('*.po'):
        stale.unlink()
    assert load().new_msgids(locales, before) == ['Only one']
