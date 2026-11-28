import json
import logging

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import HttpResponse, HttpResponseRedirect
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _l
from django.views.generic import FormView, TemplateView, View
from formtools.preview import FormPreview

from qatrack.qa import calculation_check, models
from qatrack.qa.forms.admin import CopyReferencesAndTolerancesForm
from qatrack.qa.testpack import add_testpack, create_testpack

logger = logging.getLogger('qatrack')




class CopyReferencesAndTolerances(FormPreview):

    form_template = 'admin/qa/unittestinfo/copy_refs_and_tols.html'
    preview_template = 'admin/qa/unittestinfo/copy_refs_and_tols_preview.html'

    def get_context(self, request, form):

        context = super().get_context(request, form)
        context['title'] = _("Copy References & Tolerances")
        if not request.POST:
            return context

        if not form.is_valid():
            return context

        cleaned_data = form.cleaned_data

        source_unit = cleaned_data.get("source_unit")
        dest_unit = cleaned_data.get("dest_unit")
        source_testlist_pk = cleaned_data.get("source_testlist")
        ctype = ContentType.objects.get(model=cleaned_data.get("content_type"))

        ModelClass = ctype.model_class()  # either TestList or TestListCycle

        source_testlist = ModelClass.objects.get(pk=source_testlist_pk)
        all_tests = source_testlist.all_tests()

        utis = models.UnitTestInfo.objects.filter(test__in=all_tests).select_related(
            "reference",
            "tolerance",
            "test",
        ).order_by("test")

        dest_utis = utis.filter(unit=dest_unit)
        source_utis = utis.filter(unit=source_unit)
        source_utis = {uti.test.pk: uti for uti in source_utis}
        dest_source_utis = [(dest_uti, source_utis[dest_uti.test.pk]) for dest_uti in dest_utis]
        context["dest_source_utis"] = dest_source_utis
        context["source_test_list"] = source_testlist
        context["source_unit"] = source_unit
        context["dest_unit"] = dest_unit

        return context

    def done(self, request, cleaned_data):

        if 'cancel' in request.POST:
            messages.warning(request, _("Copy references & tolerances cancelled"))
        else:
            form = CopyReferencesAndTolerancesForm(request.POST)
            form.full_clean()
            form.save()

            messages.success(request, _("References & tolerances successfully copied"))

        return HttpResponseRedirect(reverse('admin:qa_copy_refs_and_tols'))


def testlist_json(request, source_unit, content_type):
    ctype = ContentType.objects.get(model=content_type)

    if ctype.name == 'test list':
        utcs = models.UnitTestCollection.objects.filter(
            unit__pk=source_unit,
            content_type=ctype,
        ).values_list(
            'object_id', flat=True
        )
        testlists = list(models.TestList.objects.filter(pk__in=utcs).values_list('pk', 'name'))
        return HttpResponse(json.dumps(testlists), content_type='application/json')
    elif ctype.name == 'test list cycle':
        utcs = models.UnitTestCollection.objects.filter(
            unit__pk=source_unit,
            content_type=ctype,
        ).values_list(
            'object_id', flat=True
        )
        testlistcycles = list(models.TestListCycle.objects.filter(pk__in=utcs).values_list('pk', 'name'))
        return HttpResponse(json.dumps(testlistcycles), content_type='application/json')
    else:
        raise ValidationError(_('Invalid value'))


class ExportTestPackForm(forms.Form):

    name = forms.SlugField(label=_l("Test Pack Name"))
    description = forms.CharField(
        label=_("Description"),
        widget=forms.Textarea(attrs={
            'rows': 4,
            'cols': ""
        }),
        required=False,
    )
    testlists = forms.CharField(widget=forms.HiddenInput(), required=False)
    testlistcycles = forms.CharField(widget=forms.HiddenInput(), required=False)
    tests = forms.CharField(widget=forms.HiddenInput(), required=False)

    def clean_testlists(self):
        t = self.cleaned_data['testlists'].strip()
        if t == "all":
            return models.TestList.objects.all()
        elif t:
            return models.TestList.objects.filter(id__in=t.split(","))
        return models.TestList.objects.none()

    def clean_testlistcycles(self):
        t = self.cleaned_data['testlistcycles'].strip()
        if t == "all":
            return models.TestListCycle.objects.all()
        elif t:
            return models.TestListCycle.objects.filter(id__in=t.split(","))
        return models.TestListCycle.objects.none()

    def clean_tests(self):
        t = self.cleaned_data['tests'].strip()
        if t == "all":
            return models.Test.objects.all()
        elif t:
            return models.Test.objects.filter(id__in=t.split(","))
        return models.Test.objects.none()

    def clean(self):
        if not any(self.data[t].strip() for t in ['tests', 'testlists', 'testlistcycles']):
            raise ValidationError(_("You must select at least one Test, TestList, or TestListCycle for Export"))
        return super().clean()


class ExportTestPack(PermissionRequiredMixin, FormView):
    """View for exporting a QATrack+ test pack"""

    permission_required = 'qa.change_testlist'
    form_class = ExportTestPackForm
    template_name = "admin/qa/testpack/export.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _("Export Test Pack")

        context['cycles'] = models.TestListCycle.objects.all()
        context['testlists'] = models.TestList.objects.only("pk", "name", "description")
        context['tests'] = models.Test.objects.select_related("category").only(
            "pk",
            "name",
            "display_name",
            "type",
            "description",
            "category__name",
        )

        return context

    def form_valid(self, form):
        tls = form.cleaned_data['testlists']
        cycles = form.cleaned_data['testlistcycles']
        extra_tests = form.cleaned_data['tests']
        desc = form.cleaned_data['description']
        user = self.request.user
        name = form.cleaned_data['name']
        try:
            tp = create_testpack(
                test_lists=tls,
                cycles=cycles,
                extra_tests=extra_tests,
                description=desc,
                user=user,
                name=name,
                timeout=settings.TESTPACK_TIMEOUT,
            )
        except RuntimeError as e:
            form.add_error(None, ValidationError(str(e), code="timeout"))
            return self.form_invalid(form)

        response = HttpResponse(json.dumps(tp), content_type='application/json')
        response['Content-Disposition'] = 'attachment; filename=%s' % (name + ".tpk")
        return response


class ImportTestPackForm(forms.Form):

    testpack_data = forms.CharField(widget=forms.HiddenInput())
    testlists = forms.CharField(widget=forms.HiddenInput(), required=False)
    testlistcycles = forms.CharField(widget=forms.HiddenInput(), required=False)
    tests = forms.CharField(widget=forms.HiddenInput(), required=False)


class ImportTestPack(PermissionRequiredMixin, FormView):
    """View for importing a QATrack+ test pack"""

    permission_required = 'qa.change_testlist'
    form_class = ImportTestPackForm
    template_name = "admin/qa/testpack/import.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _("Import Test Pack")
        context['test_types'] = json.dumps(dict(models.TEST_TYPE_CHOICES))
        return context

    def get_success_url(self):
        """Redirect user to previous page they were on if possible"""
        next_ = self.request.GET.get("next", None)
        if next_ is not None:
            return next_
        return reverse("admin:qa_import_testpack")

    def form_valid(self, form):
        tls = form.cleaned_data['testlists']
        try:
            tls = json.loads(tls) if tls != "all" else None
        except ValueError:
            tls = None

        cycles = form.cleaned_data['testlistcycles']
        try:
            cycles = json.loads(cycles) if cycles != "all" else None
        except ValueError:
            cycles = None

        extra_tests = form.cleaned_data['tests']
        try:
            extra_tests = json.loads(extra_tests) if extra_tests != "all" else None
        except ValueError:
            extra_tests = None

        testpack = form.cleaned_data['testpack_data']
        try:
            counts, totals = add_testpack(
                testpack,
                self.request.user,
                test_keys=extra_tests,
                test_list_keys=tls,
                cycle_keys=cycles,
            )
            count_msg = ", ".join("%d/%d %s's" % (counts[k], totals[k], k) for k in totals)
            msg = _("Test Pack import successfully: %(item_counts)s were imported.") % {'item_counts': count_msg}

            messages.success(self.request, msg)
        except:  # noqa: E722
            msg = _("Sorry, but an error occurred when trying to import your TestPack. Please file a bug report.")
            logger.exception(msg)
            messages.error(self.request, msg)

        return super().form_valid(form)


def recurrence_examples(request):

    dates = []
    return JsonResponse({'dates': dates})


class CopyReferencesTolerancesView(PermissionRequiredMixin, FormView):
    template_name = 'qa/copy_refs_tols.html'
    permission_required = 'qa.change_unittestinfo'
    form_class = CopyReferencesAndTolerancesForm
    success_url = reverse_lazy('admin:qa_unittestinfo_changelist')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _("Copy References & Tolerances")
        form = kwargs.get('form', self.get_form())
        context['form'] = form

        if form.is_valid() and self.request.POST.get('stage') == '1':
            cleaned_data = form.cleaned_data
            source_unit = cleaned_data.get("source_unit")
            dest_unit = cleaned_data.get("dest_unit")
            source_testlist_pk = cleaned_data.get("source_testlist")
            ctype = ContentType.objects.get(model=cleaned_data.get("content_type"))

            ModelClass = ctype.model_class()  # either TestList or TestListCycle
            source_testlist = ModelClass.objects.get(pk=source_testlist_pk)
            all_tests = source_testlist.all_tests()

            utis = models.UnitTestInfo.objects.filter(test__in=all_tests).select_related(
                "reference",
                "tolerance",
                "test",
            ).order_by("test")

            dest_utis = utis.filter(unit=dest_unit)
            source_utis = utis.filter(unit=source_unit)
            source_utis = {uti.test.pk: uti for uti in source_utis}
            dest_source_utis = [(dest_uti, source_utis[dest_uti.test.pk]) for dest_uti in dest_utis]
            context["dest_source_utis"] = dest_source_utis
            context["source_test_list"] = source_testlist
            context["source_unit"] = source_unit
            context["dest_unit"] = dest_unit

        return context

    def form_valid(self, form):
        stage = self.request.POST.get('stage')
        if stage == '1':
            return self.render_to_response(self.get_context_data(form=form))
        elif stage == '2' and self.request.POST.get('confirm') == 'Confirm':
            try:
                form.save()
                messages.success(self.request, _("References and tolerances copied successfully"))
                return super().form_valid(form)
            except Exception as e:
                logger.error("Error copying references and tolerances: %s", str(e))
                form.add_error(None, _("An error occurred while copying references and tolerances"))
                return self.form_invalid(form)
        return self.render_to_response(self.get_context_data(form=form))


class CheckCalculations(PermissionRequiredMixin, TemplateView):
    """
    Admin page for checking that tests' calculation procedures still run, and
    still give the results that were saved (see qatrack.qa.calculation_check).

    Procedures are scanned when the page loads. Recalculating is done by the
    page's JavaScript one job at a time through CheckCalculationsRun, so that no
    single request runs for long however many tests a site has.

    Planned: turn the results into a work list an admin can work through -
    each problematic test opening in its own window to be edited, and the
    list keeping track of what has been dealt with. For now every test links
    to its admin page and opens in a new tab, and "Only show tests with
    problems" narrows the table to what needs attention.
    """

    permission_required = 'qa.change_test'
    template_name = 'admin/qa/test/check_calculations.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        tests = list(calculation_check.tests_with_procedures())
        rows = []
        for test in tests:
            findings = calculation_check.scan_procedure(test.calculation_procedure)
            check = calculation_check.TestCheck(test, findings, recalculation_requested=False)
            rows.append({'check': check, 'kind': calculation_check.procedure_kind(test)})

        jobs = calculation_check.plan_recalculations(tests)
        context.update({
            'title': _('Check Calculation Procedures'),
            'rows': rows,
            'versions': calculation_check.library_versions(),
            'recalculation_count': sum(len(job.test_ids) for job in jobs),
            'sample_file_label': calculation_check.SAMPLE_FILE_LABEL,
            'page_data': {
                'runUrl': reverse('admin:qa_check_calculations_run'),
                'jobs': [job.as_dict() for job in jobs],
                'severity': list(calculation_check.SEVERITY),
                'statusDisplay': {k: str(v) for k, v in calculation_check.STATUS_DISPLAY.items()},
                'strings': {
                    'progress': _('Recalculating: %(done)s of %(total)s done...'),
                    'finished': _('Finished: %(done)s of %(total)s recalculated.'),
                    'serverError': _('The server could not run this check: %(error)s'),
                    'noResults': _('There are no saved results to recalculate it from.'),
                    'saved': _('Saved'),
                    'recalculated': _('Recalculated'),
                    'details': _('Details'),
                },
            },
        })
        return context


class CheckCalculationsRun(PermissionRequiredMixin, View):
    """Run one recalculation job (calculation_check.Job) for the Check Calculation Procedures page"""

    permission_required = 'qa.change_test'

    def post(self, request, *args, **kwargs):
        try:
            job = calculation_check.Job.from_dict(json.loads(request.body))
        except (AttributeError, TypeError, ValueError):
            return JsonResponse({'error': _('Invalid recalculation job')}, status=400)

        results = []
        for test_id, recalculation in calculation_check.run_job(job, user=request.user):
            result = recalculation.as_dict()
            result.update({
                'test_id': test_id,
                'severity': recalculation.severity,
                'status_display': str(calculation_check.STATUS_DISPLAY[recalculation.severity]),
            })
            results.append(result)
        return JsonResponse({'results': results})
