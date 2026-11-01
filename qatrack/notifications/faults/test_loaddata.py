"""Loading faults from a fixture must not depend on their units being loaded first.

`on_fault_created` listens on `m2m_changed`, which carries no `raw` flag, so
the `loaded_from_fixture()` guard the other receivers use is unavailable to it.
Its recipient lookup did `fault.unit`, which raised `Unit.DoesNotExist` when a
fixture carried the faults before the units, and because `loaddata` runs in
one transaction that rolled back everything already inserted - measured on the
clinical database conversion, forty minutes in, twice (aviary B124).
"""

import os
import tempfile
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from qatrack.faults import models
from qatrack.faults.tests import utils as fault_utils
from qatrack.notifications.faults.handlers import get_notification_recipients
from qatrack.units.models import Unit


class TestRecipientsForAFaultWithNoUnit(TestCase):

    def test_no_unit_means_no_recipients(self):
        fault = models.Fault(unit_id=10**6)
        assert get_notification_recipients(fault) == set()


class TestFaultsLoadBeforeUnits(TestCase):

    def test_loaddata_with_faults_first(self):
        fault = fault_utils.create_fault()
        unit_pk, fault_pk = fault.unit.pk, fault.pk

        tmp = tempfile.mkdtemp()
        faults_first = os.path.join(tmp, "a-faults.json")
        the_rest = os.path.join(tmp, "b-units-and-users.json")
        with open(faults_first, "w") as f:
            call_command("dumpdata", "faults", stdout=f)
        with open(the_rest, "w") as f:
            call_command("dumpdata", "auth.user", "units", stdout=f)

        Unit.objects.filter(pk=unit_pk).delete()  # cascades to the fault
        assert not models.Fault.objects.filter(pk=fault_pk).exists()

        # The handler fires while the fault's unit is still absent; it used to raise.
        call_command("loaddata", faults_first, the_rest, stdout=StringIO())

        assert models.Fault.objects.get(pk=fault_pk).unit.pk == unit_pk
