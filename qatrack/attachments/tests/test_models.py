import os
from unittest import mock

import pytest
from django.conf import settings

from qatrack.attachments.models import Attachment
from qatrack.qa import models as qam


@pytest.mark.django_db
def test_owner_testlist():
    tl = qam.TestList(name="test")
    a = Attachment(testlist=tl)
    assert a.owner is tl


@pytest.mark.django_db
def test_owner_testinstances():
    ti = qam.TestInstance()
    a = Attachment(testinstance=ti)
    assert a.owner is ti


def test_owner_none():
    assert Attachment().owner is None


def test_has_owner_yes():
    assert Attachment(testinstance=qam.TestInstance(pk=1)).has_owner


def test_has_owner_no():
    assert not Attachment().has_owner


def test_type():
    assert Attachment(testlist=qam.TestList()).type == "testlist"


def test_is_in_tmp():
    mocka = mock.Mock()
    mocka.path = os.path.join(settings.TMP_UPLOAD_ROOT, "foo.bar")
    a = Attachment(attachment=mocka)
    assert a.is_in_tmp


def test_is_not_in_tmp():
    mocka = mock.Mock()
    mocka.path = "/foo/bar"
    a = Attachment(attachment=mocka)
    assert not a.is_in_tmp


def test_can_finalize_unowned():
    assert not Attachment().can_finalize


def test_can_finalize_unsaved_fk():
    assert not Attachment(testlist=qam.TestList()).can_finalize


def test_can_finalize_ok():
    mocka = mock.Mock()
    mocka.path = os.path.join(settings.TMP_UPLOAD_ROOT, "foo.bar")
    a = Attachment(testlist=qam.TestList(pk=1), attachment=mocka)
    assert a.can_finalize


@mock.patch("shutil.copy")
@mock.patch("os.remove")
@mock.patch("os.makedirs")
def test_move_from_tmp(makedirs, remove, copy):
    mocka = mock.Mock()
    name = "foo.bar"
    mocka.path = os.path.join(settings.TMP_UPLOAD_ROOT, name)
    mocka.name = name
    a = Attachment(testlist=qam.TestList(pk=1), attachment=mocka)
    a.move_tmp_file(save=False)

    expected_rename_from_to = (
        os.path.join(settings.TMP_UPLOAD_ROOT, "foo.bar"),
        os.path.join(settings.UPLOAD_ROOT, "testlist", "1", name),
    )

    dir_path = os.path.join(settings.UPLOAD_ROOT, "testlist", "1")
    if not os.path.exists(os.path.dirname(dir_path)):
        expected_make_dirs = (dir_path,)
    else:
        expected_make_dirs = None

    assert copy.call_args[0] == expected_rename_from_to
    assert remove.call_args[0] == (expected_rename_from_to[0],)
    if expected_make_dirs:
        assert makedirs.call_args[0] == expected_make_dirs
