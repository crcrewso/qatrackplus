"""pyplot cross-talk inside a single request, with no threads involved.

The test and the finding are nsmela's, from his review of q#904; this is his
file with its comments kept. It is the evidence behind `qatrack.W012`'s wording:
every deployment is exposed, because all of a test list's composite tests are
calculated in one `CompositePerformer.calculate()` call and `cleanup_matplotlib`
runs only after the last of them.

`test_two_pyplot_procedures_in_one_request_share_a_figure` is a
**characterisation** test: it records what QATrack+ does today, which is wrong,
rather than what it should do. Calling `plt.close('all')` between procedures
would fix the cause - and would change the saved plots of any site relying,
knowingly or not, on figures carrying over. nsmela's judgement, which we took:
that belongs in its own discussion rather than in a 4.0.2 patch. When it is
fixed, the expected value here becomes `[1, 1]`.
"""

import matplotlib.pyplot as plt
import pytest
from django.test import TestCase

from qatrack.qa import models
from qatrack.qa.tests import utils
from qatrack.qa.views.perform import CompositePerformer

# The write_file example the documentation showed before q#904.
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
