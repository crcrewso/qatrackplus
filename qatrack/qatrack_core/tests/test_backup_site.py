"""`backup_site` must not claim a database backup it did not take.

The command used to print "Successfully backed up SQL Server database to ..." when the
backup had failed - crane measured it on SQL Server 2022: exit 0, empty folder, no row
in `msdb.dbo.backupset`, and `Error: 3041 BACKUP failed` in the server log at the same
second. It now says, per engine, that it has not taken one.

These tests pin the *wording*, because wording is the entire behaviour of this command
now. A message that over-claims is the defect; there is nothing else to get wrong.

They override `DATABASES['default']['ENGINE']`, which makes Django emit
"Overriding setting DATABASES can lead to unexpected behavior" once per engine. That is
deliberate and harmless here: nothing in these tests touches the database, only the
branch that reads the engine string. The alternative - a test per real backend - would
cover four engines this suite cannot run.
"""

from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase, override_settings

ENGINES = {
    'sqlserver': 'mssql',
    'postgres': 'django.db.backends.postgresql',
    'mysql': 'django.db.backends.mysql',
    'sqlite': 'django.db.backends.sqlite3',
    'unknown': 'some.third.party.backend',
}


def run_for(engine, tmpdir):
    """Run the command with DATABASES['default']['ENGINE'] forced to `engine`."""
    from django.conf import settings

    databases = {k: dict(v) for k, v in settings.DATABASES.items()}
    databases['default']['ENGINE'] = engine
    out = StringIO()
    with override_settings(DATABASES=databases, BACKUP_DIR=str(tmpdir)):
        # The media half does real file work; it is not what these tests are about.
        with mock.patch('qatrack.qatrack_core.management.commands.backup_site'
                        '.Command.backup_media', create=True, return_value=None):
            try:
                call_command('backup_site', stdout=out, stderr=out)
            except Exception:
                # A failure in the media half must not hide the message under test.
                pass
    return out.getvalue()


class TestItNeverClaimsADatabaseBackup(TestCase):

    def setUp(self):
        import tempfile

        self.tmp = tempfile.mkdtemp()

    def test_every_engine_is_told_no_database_backup_was_taken(self):
        for label, engine in ENGINES.items():
            with self.subTest(engine=label):
                output = run_for(engine, self.tmp)
                assert "Database backup is not performed by this command" in output, (
                    label, output)

    def test_no_engine_is_told_a_database_backup_succeeded(self):
        """The two phrasings that were false, and nothing new in their shape.

        The command *does* legitimately report success for uploads, so a blanket ban on
        "Successfully backed up" fails against a true statement - the first version of
        this test did exactly that. The rule is narrower: every success line must be
        about uploads, and none may mention the database.
        """
        for label, engine in ENGINES.items():
            with self.subTest(engine=label):
                output = run_for(engine, self.tmp)
                # the two measured false claims
                assert "Successfully backed up SQL Server database" not in output, label
                assert "Copied SQLite database" not in output, label
                # and nothing of that shape, whatever the wording
                for line in output.splitlines():
                    if "Successfully backed up" in line:
                        assert "uploads" in line, (label, line)
                    if "database" in line.lower():
                        assert "not performed" in line or "pg_dump" in line \
                            or "backup tooling" in line or "BACKUP DATABASE" in line \
                            or "mysqldump" in line or "sqlite3" in line, (label, line)

    def test_each_engine_is_pointed_at_its_own_tooling(self):
        expected = {
            'mssql': "BACKUP DATABASE",
            'django.db.backends.postgresql': "pg_dump",
            'django.db.backends.mysql': "mysqldump",
            'django.db.backends.sqlite3': "sqlite3 .backup",
            'some.third.party.backend': "the backup tooling for that engine",
        }
        for engine, needle in expected.items():
            with self.subTest(engine=engine):
                assert needle in run_for(engine, self.tmp), (engine, needle)


class TestTheDockerNoteIsConditional(TestCase):
    """The bundled service covers the database only if it is actually running.

    `backup` is a default service in `deploy/docker/compose.yaml` with no profile, so a
    stock deployment does run it - but a site may have removed it, scaled it to zero, or
    be on an older compose file, and the command cannot see any of that. Promising
    coverage it cannot verify would repeat this branch's own defect one level up.
    Raised by @coderabbitai on c#10 as Major.
    """

    def setUp(self):
        import tempfile

        self.tmp = tempfile.mkdtemp()

    def test_postgres_gets_the_note_hedged_and_actionable(self):
        output = run_for('django.db.backends.postgresql', self.tmp)
        assert "bundled `backup` service" in output, output
        assert "if it is running" in output, output
        assert "cannot tell whether it is" in output, output
        assert "pg_dump" in output

    def test_the_note_is_not_offered_to_engines_it_cannot_help(self):
        """pg_dump cannot read SQL Server or SQLite, so the service is no alternative."""
        for engine in ('mssql', 'django.db.backends.sqlite3',
                       'django.db.backends.mysql', 'some.third.party.backend'):
            with self.subTest(engine=engine):
                output = run_for(engine, self.tmp)
                assert "bundled" not in output, (engine, output)
