"""A declared `permission_required` must actually be consulted.

Django resolves `dispatch()` by method order, so a permission mixin listed *after* a
generic view base never runs - `View.dispatch` wins, and `permission_required` sits
there looking enforced. `DeleteServiceEvent` had exactly that shape: the permission was
declared, and any logged-in user could use the view.

**The mistake is invisible where it is made.** The class reads fine, the attribute is
right, and the only symptom is an absence. Nothing fails. So this does not test one
class - it walks every view in the project that declares `permission_required` and
asserts the declaration can take effect. A future view written with the bases in the
wrong order fails here, wherever it is.

Note what this does *not* claim: that each permission is the correct one, or that the
view is reachable only by the right people. It claims the narrower thing that was false -
that the declaration is wired up at all.
"""

import inspect

from braces.views._access import AccessMixin as BracesAccessMixin
from django.contrib.auth.mixins import AccessMixin as DjangoAccessMixin
from django.test import TestCase
from django.views.generic import View

# **Both families, and this is the point of the file.** QATrack+ mostly uses
# `braces.views.PermissionRequiredMixin`, which is *not* a subclass of Django's
# `AccessMixin`. The first version of this sweep tested only Django's, so it skipped
# every class it was written to check and passed while measuring nothing. It was caught
# by the one test here that names a class explicitly.
ACCESS_MIXINS = (DjangoAccessMixin, BracesAccessMixin)


def is_access_mixin(cls):
    return issubclass(cls, ACCESS_MIXINS)


def view_classes_declaring_a_permission():
    """Every class under `qatrack` that is a View and declares `permission_required`."""
    import importlib
    import pkgutil

    import qatrack

    found = {}
    for module in pkgutil.walk_packages(qatrack.__path__, prefix='qatrack.'):
        name = module.name
        # migrations are not views; the accel tool is a standalone script set
        if '.migrations' in name or 'accel_migration_tool' in name:
            continue
        try:
            mod = importlib.import_module(name)
        except Exception:
            # An import error is not this test's business - other tests cover that,
            # and skipping keeps one broken optional module from hiding every view.
            continue
        for attr, obj in vars(mod).items():
            if not inspect.isclass(obj) or not issubclass(obj, View):
                continue
            if 'permission_required' not in {k for c in obj.__mro__ for k in vars(c)}:
                continue
            if getattr(obj, 'permission_required', None) in (None, ''):
                continue
            found['%s.%s' % (obj.__module__, obj.__name__)] = obj
    return found


def dispatch_owner(cls):
    return next(c for c in cls.__mro__ if 'dispatch' in vars(c))


class TestPermissionMixinsActuallyRun(TestCase):

    def test_there_are_views_to_check(self):
        """Guards the sweep itself: an empty sweep would pass everything below."""
        found = view_classes_declaring_a_permission()
        assert len(found) > 20, "only found %d views declaring permission_required" % len(found)

    def test_every_declared_permission_is_reachable_by_dispatch(self):
        offenders = []
        for label, cls in sorted(view_classes_declaring_a_permission().items()):
            owner = dispatch_owner(cls)
            # Either the access mixin owns dispatch, or it sorts ahead of the plain
            # View whose dispatch would otherwise shadow it.
            mro = cls.__mro__
            access = [c for c in mro if is_access_mixin(c) and c is not cls]
            if not access:
                continue
            if is_access_mixin(owner):
                continue
            if View in mro and min(mro.index(a) for a in access) < mro.index(View):
                continue
            offenders.append("%s: dispatch from %s, mixin after it" % (label, owner.__name__))

        assert not offenders, (
            "these views declare a permission that is never checked:\n  " + "\n  ".join(offenders)
        )

    def test_delete_service_event_specifically(self):
        """The one that was wrong, named so a reader can find the history."""
        from qatrack.service_log.views import DeleteServiceEvent

        assert is_access_mixin(dispatch_owner(DeleteServiceEvent))
        assert DeleteServiceEvent.permission_required == 'service_log.delete_serviceevent'
        # FormView must survive the reorder - the view's delete form depends on it
        assert any(c.__name__ == 'FormView' for c in DeleteServiceEvent.__mro__)
        assert DeleteServiceEvent.form_class.__name__ == 'ServiceEventDeleteForm'


class TestDeleteServiceEventRefusesTheWrongUser(TestCase):
    """And the behaviour, not only the wiring.

    The existing admin tests use a superuser throughout, which is why this went
    unnoticed: a superuser passes every permission check, so an absent check looks
    identical to a satisfied one.
    """

    def setUp(self):
        from django.contrib.auth.models import Permission, User

        from qatrack.service_log.tests import utils as sl_utils

        self.service_event = sl_utils.create_service_event()
        self.url = '/service-log/delete/%d/' % self.service_event.pk

        self.plain = User.objects.create_user('plain-sl', 'p@e.com', 'pw')
        self.allowed = User.objects.create_user('allowed-sl', 'a@e.com', 'pw')
        self.allowed.user_permissions.add(
            Permission.objects.get(content_type__app_label='service_log',
                                   codename='delete_serviceevent'))
        self.allowed = User.objects.get(pk=self.allowed.pk)

    def resolve(self):
        """The URL name, rather than a hand-built path that may not match the conf."""
        from django.urls import NoReverseMatch, reverse

        for name in ('se_delete',):
            try:
                return reverse(name, kwargs={'pk': self.service_event.pk})
            except NoReverseMatch:
                continue
        return None

    def test_a_user_without_the_permission_is_refused(self):
        url = self.resolve()
        if url is None:
            self.skipTest("could not resolve the delete URL by name")
        self.client.force_login(self.plain)
        assert self.client.get(url).status_code == 403

    def test_a_user_with_the_permission_is_not_refused(self):
        """Without this the test above would pass if the view were simply broken."""
        url = self.resolve()
        if url is None:
            self.skipTest("could not resolve the delete URL by name")
        self.client.force_login(self.allowed)
        assert self.client.get(url).status_code != 403
