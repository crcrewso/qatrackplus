"""Evidence for the migration policy: what each migration does, on each engine.

A patch release may carry a migration only if every operation is metadata,
additive, or restores something the models already declare; nothing removes,
renames or retypes a field or model; no ``RunPython`` or ``RunSQL`` writes or
deletes user data; everything is reversible without loss; and it has been
rendered on every supported engine. Those five clauses are the policy (Cody,
2026-10-07; the developer guide's *Migrations in a patch release*). This module
produces the evidence for each clause. **It does not decide.** The evidence is
the developer's to produce and publish in the pull request; the judgement is the
maintainers' to make. A green report here is not an approval, and the report
says so in its own header.

Three sources of operations are examined:

* migrations a branch **added** since a base ref, found with ``git diff``;
* migrations named explicitly, ``app_label.name_or_prefix``;
* model changes that are still **unwritten**, from Django's autodetector, so a
  developer sees the verdict before ``makemigrations`` runs.

Each operation is classified from its type and from the project state before
it (``classify``), and rendered to SQL on every configured database alias with
the same schema-editor collection ``sqlmigrate`` uses (``render``); an empty
rendering is a no-op on that engine, which is the strongest evidence that an
operation is metadata. ``RunPython`` cannot be rendered and is reported for a
human to read.
"""

from __future__ import annotations

import dataclasses
import pathlib
import re
import subprocess
from collections.abc import Iterable

from django.apps import apps
from django.conf import settings
from django.db import connections
from django.db.migrations import operations as ops
from django.db.migrations.autodetector import MigrationAutodetector
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.operations.base import Operation
from django.db.migrations.questioner import NonInteractiveMigrationQuestioner
from django.db.migrations.state import ProjectState
from django.db.utils import DatabaseError

REPO_ROOT = pathlib.Path(settings.PROJECT_ROOT).parent

# Clause numbers, as the policy numbers them.
EFFECT, STRUCTURE, DATA, REVERSIBLE, ENGINES = 1, 2, 3, 4, 5

# What an operation does, for clause 1 and 2. `alter` is undecided until it is
# rendered: an AlterField that changes only verbose_name is metadata, one that
# changes max_length is DDL, and the operation object alone cannot tell them apart.
METADATA = 'metadata'
ADDITIVE = 'additive'
ALTER = 'alter'
REMOVES = 'removes'
RENAMES = 'renames'
RETYPES = 'retypes'
WIDENS_NOT_NULL = 'not-null without default'
PYTHON = 'python'
SQL = 'sql'

_DML = re.compile(r'\b(INSERT|UPDATE|DELETE|TRUNCATE|MERGE|REPLACE)\b', re.I)
_DDL_DROP = re.compile(r'\b(DROP|ALTER\s+TABLE\s+\S+\s+DROP)\b', re.I)


@dataclasses.dataclass
class Finding:
    """One operation, classified."""

    describe: str
    category: str
    reversible: bool
    notes: list[str] = dataclasses.field(default_factory=list)
    # alias -> list of SQL statements, or None when the operation is Python
    rendered: dict[str, list[str] | None] = dataclasses.field(default_factory=dict)
    errors: dict[str, str] = dataclasses.field(default_factory=dict)

    @property
    def disqualifies_effect(self) -> bool:
        """Clause 1: fails when the operation is neither metadata, additive nor a rendered no-op."""
        if self.category in (METADATA, ADDITIVE):
            return False
        if self.category == ALTER:
            # Undecided by type; decided by what the engines rendered.
            rendered = [sql for sql in self.rendered.values() if sql is not None]
            return bool(rendered) and any(rendered)
        return self.category in (REMOVES, RENAMES, RETYPES, WIDENS_NOT_NULL, SQL)

    @property
    def disqualifies_structure(self) -> bool:
        """Clause 2: removes, renames or retypes a field or model."""
        return self.category in (REMOVES, RENAMES, RETYPES, WIDENS_NOT_NULL)

    @property
    def needs_reading(self) -> bool:
        """Clause 3: code or SQL a human has to read, because the tool cannot tell what it writes."""
        return self.category in (PYTHON, SQL)

    @property
    def writes_data(self) -> bool:
        return self.category == SQL and any(n.startswith('DML') for n in self.notes)


@dataclasses.dataclass
class MigrationReport:
    app_label: str
    name: str
    source: str  # 'added', 'named' or 'unwritten'
    findings: list[Finding]
    reverse: dict[str, str] = dataclasses.field(default_factory=dict)  # alias -> outcome

    @property
    def label(self) -> str:
        return '%s.%s' % (self.app_label, self.name)

    def clause_fails(self) -> dict[int, list[str]]:
        fails: dict[int, list[str]] = {}
        for f in self.findings:
            if f.disqualifies_effect:
                fails.setdefault(EFFECT, []).append(f.describe)
            if f.disqualifies_structure:
                fails.setdefault(STRUCTURE, []).append(f.describe)
            if f.writes_data:
                fails.setdefault(DATA, []).append(f.describe)
            if not f.reversible:
                fails.setdefault(REVERSIBLE, []).append(f.describe)
        return fails

    def needs_reading(self) -> list[Finding]:
        return [f for f in self.findings if f.needs_reading and not f.writes_data]

    def engines_not_reached(self) -> dict[str, str]:
        errors: dict[str, str] = {}
        for f in self.findings:
            errors.update(f.errors)
        return errors

    @property
    def verdict(self) -> str:
        """FAIL when a clause is broken; REVIEW when a human or an engine is still owed; OK otherwise.

        'OK' means the evidence supports a patch release. It is not an approval.
        """
        if self.clause_fails():
            return 'FAIL'
        if self.needs_reading() or self.engines_not_reached():
            return 'REVIEW'
        if any(outcome.startswith('failed') for outcome in self.reverse.values()):
            return 'FAIL'
        return 'OK'


# --------------------------------------------------------------------------
# Classification
# --------------------------------------------------------------------------


def classify(operation: Operation, app_label: str, state: ProjectState) -> Finding:
    """Say what one operation does, from its type and the model state before it."""
    describe = operation.describe()
    reversible = bool(getattr(operation, 'reversible', True))
    notes: list[str] = []

    if isinstance(operation, ops.RunPython):
        code = getattr(operation.code, '__name__', repr(operation.code))
        reverse = operation.reverse_code
        if reverse is None:
            notes.append('no reverse_code: forward-only')
        elif reverse is ops.RunPython.noop:
            notes.append('reverse is noop')
        else:
            notes.append('reverse: %s' % getattr(reverse, '__name__', repr(reverse)))
        notes.insert(0, 'code: %s' % code)
        return Finding(describe, PYTHON, reversible, notes)

    if isinstance(operation, ops.RunSQL):
        text = _sql_text(operation.sql)
        if _DML.search(text):
            notes.append('DML: %s' % ', '.join(sorted({m.upper() for m in _DML.findall(text)})))
        elif _DDL_DROP.search(text):
            notes.append('DDL that drops')
        else:
            notes.append('DDL only, as far as a keyword scan can tell')
        if operation.reverse_sql is None:
            notes.append('no reverse_sql: forward-only')
        return Finding(describe, SQL, reversible, notes)

    if isinstance(operation, ops.SeparateDatabaseAndState):
        if not operation.database_operations:
            return Finding(describe, METADATA, reversible, ['state only; no database operation'])
        inner = [classify(o, app_label, state) for o in operation.database_operations]
        worst = max(inner, key=lambda f: _severity(f.category))
        return Finding(
            describe, worst.category, reversible, ['database operations: ' + '; '.join(f.describe for f in inner)]
        )

    if isinstance(operation, ops.AlterModelOptions | ops.AlterModelManagers):
        return Finding(describe, METADATA, reversible, notes)

    if isinstance(operation, ops.CreateModel | ops.AddIndex | ops.AlterOrderWithRespectTo):
        return Finding(describe, ADDITIVE, reversible, notes)

    if isinstance(operation, ops.AddConstraint):
        notes.append('a constraint can fail to apply if existing rows violate it')
        return Finding(describe, ADDITIVE, reversible, notes)

    if isinstance(operation, ops.AddField):
        field = operation.field
        if getattr(field, 'many_to_many', False) or field.null or field.has_default():
            return Finding(describe, ADDITIVE, reversible, notes)
        notes.append('NOT NULL with no default: existing rows cannot be filled')
        return Finding(describe, WIDENS_NOT_NULL, reversible, notes)

    if isinstance(operation, ops.RemoveField | ops.DeleteModel):
        return Finding(describe, REMOVES, reversible, notes)

    if isinstance(operation, ops.RemoveIndex | ops.RemoveConstraint):
        notes.append('removes a guarantee the models declared')
        return Finding(describe, REMOVES, reversible, notes)

    if isinstance(operation, ops.RenameField | ops.RenameModel | ops.AlterModelTable):
        return Finding(describe, RENAMES, reversible, notes)

    if isinstance(operation, ops.AlterUniqueTogether | ops.AlterIndexTogether):
        old = _model_option(state, app_label, operation.name, operation.option_name) or set()
        new = set(getattr(operation, operation.option_name) or set())
        if new - old:
            notes.append('adds %s; can fail to apply if existing rows violate it' % operation.option_name)
        if old - new:
            notes.append('removes %s: a guarantee the models declared' % operation.option_name)
            return Finding(describe, REMOVES, reversible, notes)
        return Finding(describe, ADDITIVE, reversible, notes)

    if isinstance(operation, ops.AlterField):
        old = _field(state, app_label, operation.model_name, operation.name)
        new = operation.field
        if old is not None:
            if old.get_internal_type() != new.get_internal_type():
                notes.append('type %s -> %s' % (old.get_internal_type(), new.get_internal_type()))
                return Finding(describe, RETYPES, reversible, notes)
            old_len, new_len = getattr(old, 'max_length', None), getattr(new, 'max_length', None)
            if old_len and new_len and new_len < old_len:
                notes.append('max_length %s -> %s narrows the column' % (old_len, new_len))
                return Finding(describe, RETYPES, reversible, notes)
            if old.null and not new.null and not new.has_default():
                notes.append('null=True -> null=False with no default')
                return Finding(describe, WIDENS_NOT_NULL, reversible, notes)
        notes.append('decided by what the engines render: no-op is metadata, DDL is a column change')
        return Finding(describe, ALTER, reversible, notes)

    notes.append('operation type not classified; read it')
    return Finding(describe, ALTER, reversible, notes)


def _severity(category: str) -> int:
    order = [METADATA, ADDITIVE, ALTER, PYTHON, SQL, REMOVES, RENAMES, RETYPES, WIDENS_NOT_NULL]
    return order.index(category) if category in order else len(order)


def _sql_text(sql) -> str:
    if isinstance(sql, list | tuple):
        return ' '.join(_sql_text(s[0] if isinstance(s, list | tuple) else s) for s in sql)
    return str(sql)


def _field(state: ProjectState, app_label: str, model_name: str, name: str):
    model = state.models.get((app_label, model_name.lower()))
    return model.fields.get(name) if model else None


def _model_option(state: ProjectState, app_label: str, model_name: str, option: str):
    model = state.models.get((app_label, model_name.lower()))
    if model is None:
        return None
    value = model.options.get(option)
    return set(value) if value else set()


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


def render(operation: Operation, app_label: str, from_state: ProjectState, alias: str) -> list[str] | None:
    """The SQL one operation would run on one engine, or None for an operation that is Python.

    Exactly what ``sqlmigrate`` collects, one operation at a time: a schema editor in
    ``collect_sql`` mode records statements instead of executing them. An empty list
    is a no-op on that engine. Requires a connection, because the schema editor is
    the engine's own, and must not run inside a transaction on SQLite.
    """
    if not operation.reduces_to_sql:
        return None
    connection = connections[alias]
    to_state = from_state.clone()
    operation.state_forwards(app_label, to_state)
    with connection.schema_editor(collect_sql=True, atomic=False) as editor:
        operation.database_forwards(app_label, editor, from_state, to_state)
    return [sql for sql in editor.collected_sql if sql and not sql.startswith('--')]


def examine(
    app_label: str,
    name: str,
    operations: Iterable[Operation],
    from_state: ProjectState,
    aliases: Iterable[str],
    source: str,
) -> MigrationReport:
    """Classify and render every operation of one migration, walking the state forward."""
    state = from_state.clone()
    findings: list[Finding] = []
    for operation in operations:
        finding = classify(operation, app_label, state)
        for alias in aliases:
            try:
                finding.rendered[alias] = render(operation, app_label, state, alias)
            except DatabaseError as exc:
                finding.errors[alias] = _one_line(exc)
            except Exception as exc:  # the schema editor can raise its own types; the engine still was not reached
                finding.errors[alias] = _one_line(exc)
        if finding.category == ALTER and finding.rendered and all(sql == [] for sql in finding.rendered.values()):
            finding.category = METADATA
            finding.notes = ['no-op on every engine reached']
        operation.state_forwards(app_label, state)
        findings.append(finding)
    return MigrationReport(app_label, name, source, findings)


def _one_line(exc: BaseException) -> str:
    text = ' '.join(str(exc).split())
    return '%s: %s' % (type(exc).__name__, text[:160])


# --------------------------------------------------------------------------
# Discovery
# --------------------------------------------------------------------------


def loader_for(alias: str) -> MigrationLoader:
    """A loader that has read the applied migrations of one database; falls back to disk only."""
    try:
        return MigrationLoader(connections[alias])
    except DatabaseError:
        return MigrationLoader(None, ignore_no_migrations=True)


def resolve_base(base: str | None) -> str | None:
    """The git ref the branch is compared against: the first that exists of the usual names."""
    candidates = [base] if base else ['upstream/develop', 'origin/develop', 'develop']
    for ref in candidates:
        if _git('rev-parse', '--verify', '--quiet', ref) is not None:
            return ref
    return None


def added_migrations(base_ref: str) -> list[tuple[str, str]]:
    """``(app_label, migration_name)`` for every migration file added since the merge base with ``base_ref``."""
    merge_base = _git('merge-base', base_ref, 'HEAD')
    if merge_base is None:
        raise LookupError(
            'no merge base between %s and HEAD (a shallow clone may need `git fetch --deepen`)' % base_ref
        )
    paths = _git('diff', '--name-only', '--diff-filter=A', merge_base.strip(), 'HEAD', '--', '*/migrations/*.py')
    found: list[tuple[str, str]] = []
    for path in (paths or '').splitlines():
        label = _app_label_for(path)
        if label and not path.endswith('__init__.py'):
            found.append((label, pathlib.Path(path).stem))
    return found


def _app_label_for(path: str) -> str | None:
    full = (REPO_ROOT / path).resolve()
    for config in apps.get_app_configs():
        migrations_dir = pathlib.Path(config.path).resolve() / 'migrations'
        if migrations_dir in full.parents:
            return config.label
    return None


def unwritten_changes(loader: MigrationLoader) -> list[tuple[str, str, list[Operation]]]:
    """Model changes ``makemigrations`` would still write, as ``(app_label, name, operations)``."""
    autodetector = MigrationAutodetector(
        loader.project_state(),
        ProjectState.from_apps(apps),
        NonInteractiveMigrationQuestioner(dry_run=True, verbosity=0),
    )
    changes = autodetector.changes(graph=loader.graph)
    result = []
    for app_label, migrations in sorted(changes.items()):
        for migration in migrations:
            result.append((app_label, migration.name, list(migration.operations)))
    return result


def _git(*args: str) -> str | None:
    done = subprocess.run(['git', *args], cwd=REPO_ROOT, capture_output=True, text=True)
    return done.stdout if done.returncode == 0 else None


# --------------------------------------------------------------------------
# Reverse and re-apply
# --------------------------------------------------------------------------


def sqlite_file_of(alias: str) -> pathlib.Path | None:
    """The file behind a SQLite alias, or None for in-memory and for other engines."""
    db = connections.databases.get(alias, {})
    if 'sqlite3' not in db.get('ENGINE', ''):
        return None
    name = str(db.get('NAME', ''))
    if not name or name == ':memory:' or 'mode=memory' in name or name.startswith('file:memorydb'):
        return None
    path = pathlib.Path(name)
    return path if path.exists() else None


def reverse_and_reapply(app_label: str, name: str, alias: str, run) -> str:
    """Apply, reverse to the previous node, and re-apply one migration on ``alias``.

    ``run`` is ``call_command``-shaped; it is injected so the sequence can be tested
    without a database. Returns a one-line outcome. The caller decides which alias
    is safe to do this to.
    """
    loader = loader_for(alias)
    node = (app_label, name)
    if node not in loader.graph.nodes:
        return 'skipped: %s is not in the migration graph' % '.'.join(node)
    parents = [p for p in loader.graph.node_map[node].parents if p[0] == app_label]
    previous = sorted(parents)[-1][1] if parents else 'zero'
    try:
        run('migrate', app_label, name, database=alias, verbosity=0)
        run('migrate', app_label, previous, database=alias, verbosity=0)
        run('migrate', app_label, name, database=alias, verbosity=0)
    except Exception as exc:
        return 'failed: %s' % _one_line(exc)
    return 'reversed to %s and re-applied' % previous
