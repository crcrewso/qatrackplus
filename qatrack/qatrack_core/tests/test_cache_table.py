"""The cache table has to exist after `migrate`, with nothing else run.

Until `qatrack_core.0002_cache_table`, `CACHES` pointed at a table that only
`manage.py createcachetable` created, so a migrated database could still raise
`no such table: qatrack_cache_table` on an ordinary save - every cached count is
invalidated from a `post_save` receiver, and those run on every write.
"""

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import connection
from django.test import TestCase

from qatrack.service_log import models as sl_models


class TestCacheTableExists(TestCase):
    """The test database is built by running the migrations, so this asserts the
    migration did it - nothing in the test suite calls `createcachetable`."""

    def test_the_cache_table_was_created_by_a_migration(self):
        location = settings.CACHES["default"].get("LOCATION")
        if not settings.CACHES["default"]["BACKEND"].endswith("db.DatabaseCache"):
            self.skipTest("this installation is not using a database cache")
        assert location in connection.introspection.table_names(), (
            "%s is missing: `migrate` alone has to leave a usable cache" % location
        )

    def test_the_cache_round_trips(self):
        cache.set("qatrack-cache-probe", 1)
        assert cache.get("qatrack-cache-probe") == 1

    def test_an_ordinary_save_does_not_need_createcachetable(self):
        """Creating a user invalidates six cached counts through
        `qa.signals.update_unreviewed_cache`. Before the migration this raised."""
        User.objects.create_user("cache-table-probe", "a@b.com", "password")
        assert User.objects.filter(username="cache-table-probe").exists()


class TestRawSavesSkipTheCache(TestCase):
    """`loaddata` saves with `raw=True` and the receivers still fire. They now
    return early: a fixture load should not be invalidating per-request badges,
    and on a database whose cache table is absent it aborted the load outright."""

    def sentinel(self, *keys):
        """Put a recognisable non-count in real cache keys, and take it out again.

        These are the keys the application reads, and the value is a **string** where
        the application expects a count. `get_sl_notification_total` sums three of
        them from a context processor, so a leaked sentinel raises `int + str` on
        every page for the rest of the run - which is what happened during a
        full-suite run on the demo server on 2026-10-13, three tests failing with a
        traceback that pointed nowhere near their own subject.

        A `TestCase` rolls back the database, and the cache here *is* the database,
        so the write usually disappears on its own. "Usually" is the problem: the
        same test on a locmem or Redis cache leaks, and nothing in the file said the
        cleanup was being relied on. So it is explicit.
        """
        for key in keys:
            cache.set(key, "kept")
            self.addCleanup(cache.delete, key)

    def test_receivers_return_early_for_raw_saves(self):
        """All seven guards, each asserted on its own key.

        This covered four of the seven and asserted three keys. It called
        `update_colours` without ever asserting `CACHE_SERVICE_STATUS_COLOURS`, so
        removing *that* guard would still have passed - and the two active-collection
        receivers and `update_rts_cache` were not called at all.
        @coderabbitai pointed that out on c#13.

        Each receiver below is driven with `raw=True` and checked against a key only it
        touches, so a guard removed from any one of the seven fails here.
        """
        from qatrack.faults.signals import update_faults_cache
        from qatrack.qa import models as qa_models
        from qatrack.qa.signals import (
            update_active_unit_test_collections_for_unit_post_save,
            update_active_unit_test_collections_for_unit_utc,
            update_unreviewed_cache,
        )
        from qatrack.qa.tests import utils as qa_utils
        from qatrack.service_log.signals import (
            update_colours,
            update_rts_cache,
            update_se_cache,
        )

        utc = qa_utils.create_unit_test_collection()
        unit = utc.unit
        per_unit_key = settings.CACHE_ACTIVE_UTCS_FOR_UNIT_.format(unit.id)

        self.sentinel(
            settings.CACHE_UNREVIEWED_COUNT,            # update_unreviewed_cache
            settings.CACHE_UNREVIEWED_FAULT_COUNT,      # update_faults_cache
            settings.CACHE_SE_NEEDING_REVIEW_COUNT,     # update_se_cache
            settings.CACHE_DEFAULT_SE_STATUS,           # update_se_cache, status sender
            settings.CACHE_SERVICE_STATUS_COLOURS,      # update_colours
            settings.CACHE_RTS_QA_COUNT,                # update_rts_cache
            settings.CACHE_RTS_INCOMPLETE_QA_COUNT,     # update_rts_cache
            per_unit_key,                               # the two active-collection ones
        )

        update_unreviewed_cache(sender=User, raw=True)
        update_faults_cache(sender=User, raw=True)
        # the status sender, so the CACHE_DEFAULT_SE_STATUS branch is reached too
        update_se_cache(sender=sl_models.ServiceEventStatus, raw=True)
        update_colours(sender=sl_models.ServiceEventStatus, raw=True)
        update_rts_cache(sender=User, raw=True)
        update_active_unit_test_collections_for_unit_utc(
            sender=qa_models.UnitTestCollection, instance=utc, raw=True)
        update_active_unit_test_collections_for_unit_post_save(
            sender=type(unit), instance=unit, raw=True)

        for key, who in (
            (settings.CACHE_UNREVIEWED_COUNT, "update_unreviewed_cache"),
            (settings.CACHE_UNREVIEWED_FAULT_COUNT, "update_faults_cache"),
            (settings.CACHE_SE_NEEDING_REVIEW_COUNT, "update_se_cache"),
            (settings.CACHE_DEFAULT_SE_STATUS, "update_se_cache (status sender)"),
            (settings.CACHE_SERVICE_STATUS_COLOURS, "update_colours"),
            (settings.CACHE_RTS_QA_COUNT, "update_rts_cache"),
            (settings.CACHE_RTS_INCOMPLETE_QA_COUNT, "update_rts_cache"),
            (per_unit_key, "update_active_unit_test_collections_for_unit_*"),
        ):
            assert cache.get(key) == "kept", "%s did not return early for a raw save" % who

    def test_a_real_save_still_invalidates(self):
        """The guard is specific to raw, not a blanket early return."""
        self.addCleanup(cache.delete, settings.CACHE_UNREVIEWED_COUNT)
        cache.set(settings.CACHE_UNREVIEWED_COUNT, "stale")
        update = __import__("qatrack.qa.signals", fromlist=["update_unreviewed_cache"])
        update.update_unreviewed_cache(sender=User)
        assert cache.get(settings.CACHE_UNREVIEWED_COUNT) is None
