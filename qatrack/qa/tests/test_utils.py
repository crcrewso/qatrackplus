import io
import json
from unittest import mock

import pytest
from django.conf import settings
from django.test.utils import override_settings

from qatrack.qa import models, testpack
from qatrack.qa import utils as qautils
from qatrack.qa.tests import utils

delta_time = 0


def time():
    global delta_time
    delta_time += 10
    return delta_time


def test_unique():
    items = ["foo", "foo", "bar"]
    assert items[1:] == qautils.unique(items)


def test_almost_equal_none():
    assert not qautils.almost_equal(None, None)


def test_almost_equal_equal():
    assert qautils.almost_equal(1, 1)


def test_almost_equal_small():
    assert qautils.almost_equal(1, 1 + 1E-10)


def test_almost_equal_zero():
    assert qautils.almost_equal(0, 0)


def test_tokenize():
    proc = "result = a + 2"
    assert proc.split() == qautils.tokenize_composite_calc(proc)


def test_set_encoder_set():
    assert isinstance(json.dumps(set([1, 2]), cls=qautils.SetEncoder), str)


def test_float_format():
    numbers = (
        (0.999, 3, "0.999"),
        (-0.999, 3, "-0.999"),
        (0.999, 1, "1"),
        (0.999, 2, "1.0"),
        (0.0, 4, "0"),
        (-0.0, 4, "0"),
        (1234.567, 1, "1e+3"),
        (1234.567, 2, "1.2e+3"),
        (1234.567, 5, "1234.6"),
    )

    for number, prec, expected in numbers:
        assert qautils.to_precision(number, prec) == expected


@pytest.fixture
def import_export_setup():
    """Fixture to set up test data for import/export tests."""
    user = utils.create_user()
    tl1 = utils.create_test_list("tl1 é")
    tl2 = utils.create_test_list("tl2")
    tl3 = utils.create_test_list("tl3")
    tlc = utils.create_cycle([tl1, tl2])
    t1 = utils.create_test("t1")
    t2 = utils.create_test("t2")
    t3 = utils.create_test("t3")
    t4 = utils.create_test("t4")
    utils.create_test_list_membership(tl1, t1)
    utils.create_test_list_membership(tl2, t2)
    utils.create_test_list_membership(tl3, t3)
    utils.create_test_list_membership(tl3, t1)

    tlqs = models.TestList.objects.filter(pk=tl3.pk)
    tlcqs = models.TestListCycle.objects.filter(pk=tlc.pk)
    extra = models.Test.objects.filter(pk=t4.pk)

    return {
        'user': user,
        'tl1': tl1,
        'tl2': tl2,
        'tl3': tl3,
        'tlc': tlc,
        't1': t1,
        't2': t2,
        't3': t3,
        't4': t4,
        'tlqs': tlqs,
        'tlcqs': tlcqs,
        'extra': extra,
    }


@pytest.mark.django_db
def test_round_trip(import_export_setup):
    tlqs = import_export_setup['tlqs']
    tlcqs = import_export_setup['tlcqs']
    extra = import_export_setup['extra']
    
    pack = json.dumps(testpack.create_testpack(
        test_lists=tlqs,
        cycles=tlcqs,
        extra_tests=extra,
    ))
    models.TestListCycle.objects.all().delete()
    models.TestList.objects.all().delete()
    models.Test.objects.all().delete()
    models.Category.objects.all().delete()
    testpack.add_testpack(pack)

    assert models.Test.objects.count() == 4
    assert models.TestList.objects.count() == 3
    assert models.TestListMembership.objects.count() == 4
    assert models.TestListCycle.objects.count() == 1
    assert models.TestListCycleMembership.objects.count() == 2


@pytest.mark.django_db
def test_create_pack(import_export_setup):
    tlqs = import_export_setup['tlqs']
    tlcqs = import_export_setup['tlcqs']
    tl3 = import_export_setup['tl3']
    t3 = import_export_setup['t3']

    pack = testpack.create_testpack(tlqs, tlcqs)

    assert 'meta' in pack
    assert 'objects' in pack

    test_found = False
    list_found = False
    for tl_dat in pack['objects']['testlists']:
        tl = json.loads(tl_dat)
        if tl['object']['fields']['name'] == tl3.name:
            list_found = True

        for o in tl['dependencies']:
            try:
                if o['fields']['name'] == t3.name:
                    test_found = True
            except KeyError:
                pass

    assert list_found and test_found


@pytest.mark.django_db
def test_timeout(import_export_setup):
    tlqs = import_export_setup['tlqs']
    tlcqs = import_export_setup['tlcqs']

    with pytest.raises(RuntimeError):
        with mock.patch('time.time', mock.Mock(side_effect=time)):
            testpack.create_testpack(tlqs, tlcqs, timeout=1)


@pytest.mark.django_db
def test_save_pack(import_export_setup):
    tlqs = import_export_setup['tlqs']
    tlcqs = import_export_setup['tlcqs']
    
    pack = testpack.create_testpack(tlqs, tlcqs)
    fp = io.StringIO()
    testpack.save_testpack(pack, fp)
    fp.seek(0)
    # check the accented character in test list 1 name was written
    assert "\\u00e9" in fp.read()


@pytest.mark.django_db
def test_non_destructive_load(import_export_setup):
    tlqs = import_export_setup['tlqs']
    tlcqs = import_export_setup['tlcqs']
    extra = import_export_setup['extra']
    
    ntl = models.TestList.objects.count()
    nt = models.Test.objects.count()
    pack = testpack.create_testpack(tlqs, tlcqs, extra)
    fp = io.StringIO()
    testpack.save_testpack(pack, fp)
    fp.seek(0)
    testpack.load_testpack(fp)
    assert models.TestList.objects.count() == 2 * ntl
    assert models.Test.objects.count() == 2 * nt


@pytest.mark.django_db
def test_load(import_export_setup):
    tlqs = import_export_setup['tlqs']
    tlcqs = import_export_setup['tlcqs']
    tl1 = import_export_setup['tl1']
    t1 = import_export_setup['t1']
    tlc = import_export_setup['tlc']
    
    pack = testpack.create_testpack(tlqs, tlcqs)
    models.TestList.objects.all().delete()
    models.Test.objects.all().delete()
    models.TestListCycle.objects.all().delete()

    fp = io.StringIO()
    testpack.save_testpack(pack, fp)
    fp.seek(0)
    testpack.load_testpack(fp)

    assert models.TestList.objects.filter(name=tl1.name).exists()
    assert models.Test.objects.filter(name=t1.name).exists()
    assert models.TestListCycle.objects.filter(name=tlc.name).exists()
    assert tl1.name in models.TestListCycle.objects.values_list("test_lists__name", flat=True)


@pytest.mark.django_db
def test_selective_load(import_export_setup):
    t1 = import_export_setup['t1']
    tl1 = import_export_setup['tl1']
    tlcqs = import_export_setup['tlcqs']
    
    pack = testpack.create_testpack(models.TestList.objects.all(), tlcqs)
    models.TestList.objects.all().delete()
    models.Test.objects.all().delete()
    models.TestListCycle.objects.all().delete()

    fp = io.StringIO()
    testpack.save_testpack(pack, fp)
    fp.seek(0)
    testpack.load_testpack(
        fp,
        test_keys=[t1.natural_key()],
        test_list_keys=[tl1.natural_key()],
        cycle_keys=[],
    )

    assert models.TestList.objects.count() == 1
    assert models.Test.objects.count() == 1
    assert models.TestListCycle.objects.count() == 0


@pytest.mark.django_db
def test_existing_created_user_not_overwritten(import_export_setup):
    tlqs = import_export_setup['tlqs']
    tlcqs = import_export_setup['tlcqs']
    tl1 = import_export_setup['tl1']
    
    user2 = utils.create_user(uname="user2")
    pack = testpack.create_testpack(tlqs, tlcqs)

    fp = io.StringIO()
    testpack.save_testpack(pack, fp)
    fp.seek(0)
    testpack.load_testpack(fp, user2)

    assert models.TestList.objects.get(slug=tl1.slug).created_by != user2


@pytest.mark.django_db
def test_existing_objs_not_deleted(import_export_setup):
    tlqs = import_export_setup['tlqs']
    tlcqs = import_export_setup['tlcqs']
    t1 = import_export_setup['t1']
    tl1 = import_export_setup['tl1']
    tl2 = import_export_setup['tl2']
    tl3 = import_export_setup['tl3']
    t2 = import_export_setup['t2']
    t3 = import_export_setup['t3']
    tlc = import_export_setup['tlc']
    
    pack = testpack.create_testpack(tlqs, tlcqs)

    fp = io.StringIO()
    testpack.save_testpack(pack, fp)
    fp.seek(0)
    testpack.load_testpack(
        fp,
        test_keys=[t1.natural_key()],
        test_list_keys=[tl1.natural_key()],
        cycle_keys=[],
    )

    assert models.TestList.objects.filter(name__in=[tl2.name, tl3.name]).count() == 2
    assert models.Test.objects.filter(name__in=[t2.name, t3.name]).count() == 2
    assert models.TestListCycle.objects.filter(name__in=[tlc.name]).count() == 1


@pytest.mark.django_db
def test_extra_tests(import_export_setup):
    tlqs = import_export_setup['tlqs']
    tlcqs = import_export_setup['tlcqs']
    
    extra = utils.create_test("extra test")
    extra_qs = models.Test.objects.filter(pk=extra.pk)
    pack = testpack.create_testpack(tlqs, tlcqs, extra_tests=extra_qs)
    fp = io.StringIO()
    testpack.save_testpack(pack, fp)
    fp.seek(0)
    assert "extra test" in fp.read()


@pytest.mark.django_db
def test_extra_tests_loaded(import_export_setup):
    tlqs = import_export_setup['tlqs']
    tlcqs = import_export_setup['tlcqs']
    
    extra = utils.create_test("extra test")
    extra_qs = models.Test.objects.filter(pk=extra.pk)
    pack = testpack.create_testpack(tlqs, tlcqs, extra_tests=extra_qs)
    fp = io.StringIO()
    testpack.save_testpack(pack, fp)
    fp.seek(0)
    models.Test.objects.all().delete()
    testpack.load_testpack(fp, test_keys=[extra.natural_key()], test_list_keys=[], cycle_keys=[])
    assert models.Test.objects.filter(name=extra.name).exists()


@pytest.mark.django_db
def test_sublist(import_export_setup):
    tl1 = import_export_setup['tl1']
    tl2 = import_export_setup['tl2']
    
    tl5 = utils.create_test_list("tl5")
    t5 = utils.create_test("t5")
    utils.create_test_list_membership(tl5, t5, order=0)
    utils.create_sublist(tl5, tl1, order=2)
    utils.create_sublist(tl5, tl2, order=3)
    pack = json.dumps(testpack.create_testpack(test_lists=models.TestList.objects.filter(pk=tl5.pk)))
    models.TestList.objects.all().delete()
    models.Test.objects.all().delete()
    assert models.Sublist.objects.count() == 0
    testpack.add_testpack(pack, test_list_keys=[tl5.natural_key()])
    assert models.Sublist.objects.count() == 2
    assert models.TestListMembership.objects.count() == 3
    for sl in models.Sublist.objects.all():
        assert sl.child.testlistmembership_set.count() == 1
    assert models.TestList.objects.count() == 3
    assert models.TestList.objects.get(name="tl5")


@override_settings(CONSTANT_PRECISION=2)
def test_null_format():
    assert qautils.format_qc_value(1, None) == "1.0"


@override_settings(CONSTANT_PRECISION=2)
def test_empty_format():
    assert qautils.format_qc_value(1, "") == "1.0"


def test_old_style():
    assert qautils.format_qc_value(1, "%.3f") == "1.000"


def test_new_style():
    assert qautils.format_qc_value(1, "{:.3f}") == "1.000"


@override_settings(CONSTANT_PRECISION=2)
def test_invalid_format():
    assert qautils.format_qc_value(1, "{:foo}") == qautils.to_precision(1, settings.CONSTANT_PRECISION)


def test_non_numerical_val():
    assert qautils.format_qc_value(None, "%d") == "None"


@override_settings(DEFAULT_NUMBER_FORMAT="{:.3f}")
def test_default_format_new():
    assert qautils.format_qc_value(1, "") == qautils.format_qc_value(1, "{:.3f}")


@override_settings(DEFAULT_NUMBER_FORMAT="%.3f")
def test_default_format_old():
    assert qautils.format_qc_value(1, None) == qautils.format_qc_value(1, "{:.3f}")


@override_settings(DEFAULT_NUMBER_FORMAT="{:foo}")
def test_invalid_default_fallback():
    assert qautils.format_qc_value(1, None) == qautils.to_precision(1, settings.CONSTANT_PRECISION)
