"""pyplot cross-talk inside one request, with no threads: the evidence for `qatrack.W017`.

nsmela's test, from q#904. A characterisation test: it pins today's wrong behaviour.
When pyplot is cleared between procedures, the expected value becomes `[1, 1]`.
"""

import matplotlib.pyplot as plt
import pytest
from django.test import TestCase

from qatrack.qa import models
from qatrack.qa.tests import utils
from qatrack.qa.views.perform import CompositePerformer

# The write_file example docs/admin/qa/tests.rst used to show.
PYPLOT_PROCEDURE = (
    "import matplotlib.pyplot as plt\n"
    "plt.plot(range(10), range(10))\n"
    "figure = plt.gcf()\n"
    "result = len(figure.axes[0].lines)\n"
)


@pytest.fixture(autouse=True)
def clean_pyplot():
    plt.close('all')
    yield
    plt.close('all')


class TestPyplotCrossTalkInOneRequest(TestCase):

    def setUp(self):
        self.user = utils.create_user()
        self.unit = utils.create_unit()
        self.test_list = utils.create_test_list()

    def add_composite(self, name, procedure):
        test = utils.create_test(name=name, test_type=models.COMPOSITE)
        test.calculation_procedure = procedure
        test.save()
        utils.create_test_list_membership(self.test_list, test)
        utils.create_unit_test_info(test=test, unit=self.unit)

    def test_two_pyplot_procedures_in_one_request_share_a_figure(self):
        self.add_composite('plot_a', PYPLOT_PROCEDURE)
        self.add_composite('plot_b', PYPLOT_PROCEDURE)

        # One call is one request. No threads are involved.
        results = CompositePerformer(self.user, {
            'tests': {'plot_a': '', 'plot_b': ''},
            'meta': {},
            'test_list_id': self.test_list.id,
            'unit_id': self.unit.id,
        }).calculate()['results']

        assert all(r['error'] is None for r in results.values()), results
        lines = sorted(r['value'] for r in results.values())
        # Each procedure drew one line. The second one's figure holds two,
        # because pyplot is only cleared after the last composite test.
        assert lines == [1, 2]
