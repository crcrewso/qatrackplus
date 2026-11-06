"""The migration-policy evidence: classification, rendering, discovery, and the report.

The classifier is tested on synthetic operations against a throwaway model state,
one per clause, so a green run means each clause can actually fail. Rendering is
tested on SQLite with the schema editor outside a transaction, which is what the
command does. The command is run against the 4.0.2 bundle in `qa`, whose
measured answer is on record: 132 metadata alterations that render as no-ops and
one RunPython that cannot be rendered.
"""

import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.db import migrations, models
from django.db.migrations.state import ModelState, ProjectState

from qatrack.qatrack_core import migration_safety as ms

APP = 'qatrack_core'


def thing_state(**extra_fields):
    fields = [
        ('id', models.AutoField(primary_key=True)),
        ('name', models.CharField(max_length=20, verbose_name='Name')),
        ('note', models.TextField(null=True)),
    ] + list(extra_fields.items())
    state = ProjectState()
    state.add_model(ModelState(APP, 'Thing', fields))
    return state


def noop(apps, schema_editor):
    pass


def writes(apps, schema_editor):
    pass


# --------------------------------------------------------------------------
# Classification, one negative control per clause
# --------------------------------------------------------------------------


def test_additive_operations_pass_clauses_one_and_two():
    state = thing_state()
    for op in (
        migrations.AddField('Thing', 'flag', models.BooleanField(default=False)),
        migrations.AddField('Thing', 'extra', models.CharField(max_length=5, null=True)),
        migrations.AddIndex('Thing', models.Index(fields=['name'], name='thing_name_idx')),
        migrations.CreateModel('Other', [('id', models.AutoField(primary_key=True))]),
    ):
        f = ms.classify(op, APP, state)
        assert f.category == ms.ADDITIVE, (op.describe(), f.category)
        assert not f.disqualifies_effect and not f.disqualifies_structure


def test_metadata_operations_are_metadata_before_rendering():
    f = ms.classify(migrations.AlterModelOptions('Thing', {'verbose_name': 'thing'}), APP, thing_state())
    assert f.category == ms.METADATA


def test_add_field_not_null_without_default_fails_clause_one():
    f = ms.classify(migrations.AddField('Thing', 'code', models.CharField(max_length=3)), APP, thing_state())
    assert f.category == ms.WIDENS_NOT_NULL
    assert f.disqualifies_effect and f.disqualifies_structure


def test_remove_rename_and_retype_fail_clause_two():
    state = thing_state()
    cases = {
        migrations.RemoveField('Thing', 'note'): ms.REMOVES,
        migrations.DeleteModel('Thing'): ms.REMOVES,
        migrations.RenameField('Thing', 'name', 'title'): ms.RENAMES,
        migrations.RenameModel('Thing', 'Object'): ms.RENAMES,
        migrations.AlterField('Thing', 'name', models.IntegerField()): ms.RETYPES,
        migrations.AlterField('Thing', 'name', models.CharField(max_length=5)): ms.RETYPES,
        migrations.AlterField('Thing', 'note', models.TextField()): ms.WIDENS_NOT_NULL,
    }
    for op, expected in cases.items():
        f = ms.classify(op, APP, state)
        assert f.category == expected, (op.describe(), f.category, f.notes)
        assert f.disqualifies_structure, op.describe()


def test_alter_field_that_may_be_metadata_is_undecided_until_rendered():
    f = ms.classify(
        migrations.AlterField('Thing', 'name', models.CharField(max_length=20, verbose_name='Title')),
        APP,
        thing_state(),
    )
    assert f.category == ms.ALTER
    assert not f.disqualifies_effect, 'nothing rendered yet, so nothing to hold against it'
    f.rendered['default'] = []
    assert not f.disqualifies_effect
    f.rendered['default'] = ['ALTER TABLE ...']
    assert f.disqualifies_effect, 'DDL on an engine is a column change, not metadata'


def test_run_python_needs_reading_and_reports_its_reverse():
    forward_only = ms.classify(migrations.RunPython(writes), APP, thing_state())
    assert forward_only.category == ms.PYTHON
    assert forward_only.needs_reading and not forward_only.writes_data
    assert not forward_only.reversible
    assert 'code: writes' in forward_only.notes and 'no reverse_code: forward-only' in forward_only.notes

    with_noop = ms.classify(migrations.RunPython(writes, migrations.RunPython.noop), APP, thing_state())
    assert with_noop.reversible and 'reverse is noop' in with_noop.notes


def test_run_sql_that_writes_data_fails_clause_three():
    f = ms.classify(
        migrations.RunSQL('DELETE FROM qatrack_core_thing WHERE note IS NULL', migrations.RunSQL.noop),
        APP,
        thing_state(),
    )
    assert f.category == ms.SQL and f.writes_data
    assert f.notes[0] == 'DML: DELETE'
    ddl = ms.classify(
        migrations.RunSQL('CREATE INDEX x ON qatrack_core_thing (name)', 'DROP INDEX x'), APP, thing_state()
    )
    assert ddl.needs_reading and not ddl.writes_data


def test_unique_together_added_is_additive_and_removed_is_a_removal():
    state = thing_state()
    added = ms.classify(migrations.AlterUniqueTogether('Thing', {('name', 'note')}), APP, state)
    assert added.category == ms.ADDITIVE and 'can fail to apply' in added.notes[0]
    with_unique = ProjectState()
    with_unique.add_model(
        ModelState(
            APP,
            'Thing',
            [('id', models.AutoField(primary_key=True)), ('name', models.CharField(max_length=20))],
            {'unique_together': {('id', 'name')}},
        )
    )
    removed = ms.classify(migrations.AlterUniqueTogether('Thing', set()), APP, with_unique)
    assert removed.category == ms.REMOVES


def test_report_verdicts():
    ok = ms.MigrationReport(APP, '0001', 'named', [ms.Finding('add', ms.ADDITIVE, True, [], {'default': ['CREATE']})])
    assert ok.verdict == 'OK'
    review = ms.MigrationReport(APP, '0002', 'named', [ms.Finding('py', ms.PYTHON, True, [], {'default': None})])
    assert review.verdict == 'REVIEW'
    fail = ms.MigrationReport(APP, '0003', 'named', [ms.Finding('rm', ms.REMOVES, True, [], {'default': ['DROP']})])
    assert fail.verdict == 'FAIL' and fail.clause_fails() == {ms.EFFECT: ['rm'], ms.STRUCTURE: ['rm']}
    unreached = ms.MigrationReport(
        APP, '0004', 'named', [ms.Finding('add', ms.ADDITIVE, True, [], {}, {'postgres': 'OperationalError: refused'})]
    )
    assert unreached.verdict == 'REVIEW' and unreached.engines_not_reached() == {
        'postgres': 'OperationalError: refused'
    }
    reversed_failed = ms.MigrationReport(
        APP,
        '0005',
        'named',
        [ms.Finding('add', ms.ADDITIVE, True, [], {'default': []})],
        {'default (copy)': 'failed: boom'},
    )
    assert reversed_failed.verdict == 'FAIL'


# --------------------------------------------------------------------------
# Rendering, on the engine the test database is
# --------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_render_distinguishes_a_no_op_from_ddl():
    # Render against a real table so the schema editor has something to alter:
    # the auth user table exists in every test database.
    from_state = ProjectState.from_apps(ms.apps)
    metadata_only = migrations.AlterField(
        'user', 'first_name', models.CharField(max_length=150, blank=True, verbose_name='given name')
    )
    sql = ms.render(metadata_only, 'auth', from_state, 'default')
    assert sql == [], sql
    additive = migrations.AddField('user', 'nickname', models.CharField(max_length=10, null=True))
    sql = ms.render(additive, 'auth', from_state, 'default')
    assert sql and any('nickname' in s for s in sql), sql
    assert ms.render(migrations.RunPython(noop), 'auth', from_state, 'default') is None


@pytest.mark.django_db(transaction=True)
def test_examine_promotes_a_rendered_no_op_alter_to_metadata():
    from_state = ProjectState.from_apps(ms.apps)
    op = migrations.AlterField(
        'user', 'first_name', models.CharField(max_length=150, blank=True, verbose_name='given name')
    )
    report = ms.examine('auth', 'x', [op], from_state, ['default'], 'named')
    assert report.findings[0].category == ms.METADATA
    assert report.verdict == 'OK'


# --------------------------------------------------------------------------
# The command against the repository's own history
# --------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_the_4_0_2_bundle_reports_what_was_measured():
    """jackdaw measured qa 0061 on 2026-10: every AlterField a no-op, one RunPython."""
    out = StringIO()
    with pytest.raises(SystemExit) as excinfo:
        call_command(
            'check_migrations_safe',
            '--migration',
            'qa.0061',
            '--no-unwritten',
            '--no-reverse',
            '--format',
            'json',
            stdout=out,
        )
    assert excinfo.value.code == 2, 'a RunPython to read is REVIEW, exit 2'
    report = json.loads(out.getvalue())['migrations'][0]
    assert report['migration'] == 'qa.0061_v4_0_2_final'
    assert report['verdict'] == 'REVIEW'
    assert report['clause_fails'] == {}
    categories = [op['category'] for op in report['operations']]
    assert categories.count(ms.METADATA) == 132, categories.count(ms.METADATA)
    assert categories.count(ms.PYTHON) == 1
    assert report['needs_reading'] == ['Raw Python operation']
    assert all(op['rendered'] == {'default': 0} for op in report['operations'] if op['category'] == ms.METADATA)


@pytest.mark.django_db(transaction=True)
def test_markdown_output_is_a_table_with_the_policy_header():
    out = StringIO()
    with pytest.raises(SystemExit):
        call_command(
            'check_migrations_safe',
            '--migration',
            'qa.0061',
            '--no-unwritten',
            '--no-reverse',
            '--format',
            'markdown',
            stdout=out,
        )
    text = out.getvalue()
    assert 'not a verdict' in text
    assert '| Migration | Operations | 1 metadata/additive/restores |' in text
    assert '| qa.0061_v4_0_2_final |' in text
    assert '<details>' in text


@pytest.mark.django_db(transaction=True)
def test_nothing_added_against_head_and_nothing_unwritten_exits_zero():
    out = StringIO()
    call_command('check_migrations_safe', '--base', 'HEAD', '--no-reverse', stdout=out)
    assert 'No added migrations and no unwritten model changes.' in out.getvalue()


@pytest.mark.django_db
def test_unknown_migration_and_alias_are_refused():
    from django.core.management.base import CommandError

    with pytest.raises(CommandError):
        call_command('check_migrations_safe', '--migration', 'qa.9999', '--no-unwritten', '--no-reverse')
    with pytest.raises(CommandError):
        call_command(
            'check_migrations_safe', '--migration', 'qa.0061', '--database', 'nosuch', '--no-unwritten', '--no-reverse'
        )


# --------------------------------------------------------------------------
# Reverse and re-apply: the sequence, without a database
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_reverse_and_reapply_runs_apply_reverse_apply(monkeypatch):
    calls = []

    def fake_call_command(name, *args, **kwargs):
        calls.append((name, args, kwargs.get('database')))

    outcome = ms.reverse_and_reapply('qa', '0061_v4_0_2_final', 'default', fake_call_command)
    assert outcome.startswith('reversed to 0060')
    assert [c[1] for c in calls] == [
        ('qa', '0061_v4_0_2_final'),
        ('qa', '0060_v4_0_final'),
        ('qa', '0061_v4_0_2_final'),
    ]
    assert {c[2] for c in calls} == {'default'}


@pytest.mark.django_db
def test_reverse_and_reapply_reports_a_failure_instead_of_raising():
    def boom(*args, **kwargs):
        raise RuntimeError('cannot reverse')

    assert ms.reverse_and_reapply('qa', '0061_v4_0_2_final', 'default', boom).startswith('failed: RuntimeError')
    assert ms.reverse_and_reapply('qa', 'nosuch', 'default', boom).startswith('skipped')


def test_sqlite_file_detection(monkeypatch):
    monkeypatch.setitem(
        ms.connections.databases, '_probe_mem', {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}
    )
    assert ms.sqlite_file_of('_probe_mem') is None
    monkeypatch.setitem(
        ms.connections.databases, '_probe_pg', {'ENGINE': 'django.db.backends.postgresql', 'NAME': 'qatrack'}
    )
    assert ms.sqlite_file_of('_probe_pg') is None
