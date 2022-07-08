from django.db.models import Q
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import get_template
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from qatrack.qatrack_core.dates import format_as_date
from qatrack.reports import (  # noqa: F401
    faults, models, qc, reports, service_log,
)
from qatrack.reports.forms import (
    ReportForm,
    ReportNoteFormSet,
    ReportScheduleForm,
    serialize_form_data,
    serialize_savedreport,
    serialize_savedreport_notes,
)


def process_form_post(post_data, user, instance):
    """Handle validing form and filter form for views"""

    form = ReportForm(post_data, instance=instance)
    form.is_valid()
    notes_formset = ReportNoteFormSet(post_data, instance=instance)
    notes_formset.is_valid()
    base_opts = {'report_id': post_data.get("report_id")}
    base_opts.update(form.cleaned_data)
    filter_form = None
    all_valid = False
    report = None
    if not (form.is_valid() and notes_formset.is_valid()) and "report_type" not in form.errors:
        # something wrong with base form, but we know what report_type we're trying to produce
        # so validate that form too
        notes = notes_formset.cleaned_data if notes_formset.is_valid() else []
        ReportClass = reports.report_class(form.cleaned_data['report_type'])
        report = ReportClass(base_opts=base_opts, report_opts=post_data, notes=notes, user=user)
        filter_form = report.get_filter_form()
        filter_form.is_valid()
    elif form.is_valid():
        ReportClass = reports.report_class(form.cleaned_data['report_type'])
        notes = notes_formset.cleaned_data if notes_formset.is_valid() else []
        report = ReportClass(base_opts=base_opts, report_opts=post_data, notes=notes, user=user)
        filter_form = report.get_filter_form()
        if filter_form.is_valid() and notes_formset.is_valid():
            all_valid = report.filter_form_valid(filter_form)

    return all_valid, report, form, filter_form, notes_formset


def select_report(request):
    """Handle initial loading of page, as well as the downloading of the report
    in the requested format"""

    if not request.user.has_perm("reports.can_run_reports"):
        return HttpResponseForbidden()

    if request.method == "GET":
        filter_form = None  # filter form is loaded dynamically by client
        form = ReportForm()
        notes_formset = ReportNoteFormSet()
    else:

        # need to filter out any report note meta data so the formset
        # can be treated like a new report rather than a saved report
        def dont_include(k):
            return ((k.startswith("reportnote_set-") and k.endswith("-report")) or
                    (k.startswith("reportnote_set-") and k.endswith("-id")))

        delete = [k for k in request.POST if dont_include(k)]

        data = request.POST.copy()
        for k in delete:
            del data[k]
        data['reportnote_set-INITIAL_FORMS'] = '0'

        all_valid, report, form, filter_form, notes_formset = process_form_post(data, request.user, None)
        if all_valid:
            return report.render_to_response(form.cleaned_data['report_format'])

    context = {
        "report_form": form,
        "notes_formset": notes_formset,
        "filter_form": filter_form,
    }
    return render(request, "reports/reports.html", context)


def get_filter(request):
    """When a user selects a new report type, get the proper filter form and
    render it as an html fragment to display for user"""

    try:
        report = reports.report_class(request.GET.get("report_type"))
    except ValueError:
        raise Http404("Unknown report type")

    template = get_template("_form_horizontal.html")
    content = template.render({'form': report.filter_class().form})
    formats = [f for f in models.SavedReport.FORMATS if f[0] in report.formats]
    return JsonResponse({'errors': [], 'filter': content, 'formats': formats})


@require_POST
def report_preview(request):
    """Validate the ReportForm, filter form and then return an html
    preview of the pdf report"""

    if not request.user.has_perm("reports.can_run_reports"):
        return HttpResponseForbidden()

    resp = {
        'errors': False,
        'base_errors': {},
        'report_errors': {},
        'notes_formset_errors': [],
        'preview': '',
    }

    all_valid, report, form, filter_form, notes_formset = process_form_post(request.POST, request.user, None)
    if all_valid:
        resp['preview'] = report.to_html()
        return JsonResponse(resp)

    resp['errors'] = True
    resp['base_errors'] = form.errors
    resp['report_errors'] = filter_form.errors if filter_form else {}
    resp['notes_formset_errors'] = notes_formset.errors

    return JsonResponse(resp)


@require_POST
def save_report(request):

    if not request.user.has_perm("reports.can_create_reports"):
        return HttpResponseForbidden()

    resp = {'errors': False, 'base_errors': {}, 'report_errors': {}, 'report_id': None}

    report_id = request.POST.get("report_id")
    if report_id:
        instance = get_object_or_404(models.SavedReport, id=report_id)
        if instance.created_by != request.user:
            return HttpResponseForbidden()
    else:
        instance = None

    all_valid, report, form, filter_form, notes_formset = process_form_post(request.POST, request.user, instance)
    if all_valid:
        saved_report = form.save(commit=False)
        saved_report.filters = serialize_form_data(filter_form.cleaned_data)
        saved_report.created_by = request.user
        saved_report.modified_by = request.user
        saved_report.save()
        form.save_m2m()
        notes_formset = ReportNoteFormSet(request.POST, instance=saved_report)
        if notes_formset.is_valid():
            notes_formset.save()
            resp['report_id'] = saved_report.pk
            resp['notes'] = serialize_savedreport_notes(saved_report)
            resp['success_message'] = _("Your report was saved")
            return JsonResponse(resp)

    resp['errors'] = True
    resp['base_errors'] = form.errors
    resp['report_errors'] = filter_form.errors if filter_form else {}
    resp['notes_formset_errors'] = notes_formset.errors
    return JsonResponse(resp)


def visible_user_reports(user):

    return models.SavedReport.objects.filter(Q(created_by=user) | Q(visible_to__in=user.groups.all())
                                             ).select_related("created_by").order_by("title", "created").distinct()


def saved_reports_datatable(request):

    reports = visible_user_reports(request.user)

    vals = []
    template = get_template("reports/_saved_reports_table_link.html")
    sch_template = get_template("reports/_saved_reports_table_schedule.html")
    for r in reports:
        user = '<abbr title="Created on %s">%s</abbr>' % (format_as_date(r.created), r.created_by.username)
        context = {'report': r, 'editable': r.created_by == request.user}
        try:
            schedule = r.schedule
            recipients = ' '.join(schedule.recipients())
        except models.ReportSchedule.DoesNotExist:
            recipients = ""
        vals.append([template.render(context), user, sch_template.render(context), recipients])
    return JsonResponse({'data': vals})


def load_report(request):

    if not request.user.has_perm("reports.can_run_reports"):
        return HttpResponseForbidden()

    report_id = request.GET.get("report_id")
    resp = {'errors': []}
    try:

        rep = visible_user_reports(request.user).get(pk=report_id)
        resp['id'] = report_id
        resp['fields'] = serialize_savedreport(rep)
        resp['notes'] = serialize_savedreport_notes(rep)
        resp['editable'] = rep.created_by_id == request.user.id
    except models.SavedReport.DoesNotExist:
        resp['errors'].append(_('Report does not exist'))

    return JsonResponse(resp)


@require_POST
def delete_report(request):

    if not request.user.has_perm("reports.can_create_reports"):
        return HttpResponseForbidden()

    report_id = request.POST.get("report_id")
    resp = {'errors': False, 'deleted': False, 'save_errors': []}
    try:

        rep = models.SavedReport.objects.filter(created_by=request.user).distinct().get(pk=report_id)
        rep.delete()
        resp['deleted'] = True
        resp['success_message'] = _("Your report was deleted")

    except models.SavedReport.DoesNotExist:
        resp['errors'] = True
        resp['save_errors'].append(_('Report does not exist'))

    return JsonResponse(resp)


def report_schedule_form(request, report_id):

    report = models.SavedReport.objects.get(pk=report_id)
    try:
        schedule = report.schedule
    except models.ReportSchedule.DoesNotExist:
        schedule = None

    form = ReportScheduleForm(initial={'report': report}, instance=schedule)
    template = get_template("_form_horizontal.html")
    resp = {'form': template.render({'form': form})}
    return JsonResponse(resp)


@require_POST
def schedule_report(request):
    """Set a schedule, or update a schedule for a report"""

    if not request.user.has_perm("reports.can_run_reports"):
        return HttpResponseForbidden()

    report = models.SavedReport.objects.get(pk=request.POST.get("schedule-report"))
    if request.user != report.created_by:
        return HttpResponseForbidden()

    try:
        schedule = report.schedule
    except models.ReportSchedule.DoesNotExist:
        schedule = None

    form = ReportScheduleForm(request.POST, instance=schedule)
    resp = {'error': True, 'message': ""}
    if form.is_valid():
        resp['error'] = False
        resp['message'] = _("Schedule updated successfully!")
        new_schedule = form.save(commit=False)
        if schedule is None:
            new_schedule.created_by = request.user
        new_schedule.modified_by = request.user
        new_schedule.save()
        form.save_m2m()

    template = get_template("_form_horizontal.html")
    resp['form'] = template.render({'form': form})
    return JsonResponse(resp)


@require_POST
def delete_schedule(request):

    try:
        report = models.SavedReport.objects.get(pk=request.POST.get("schedule-report"))

        if request.user != report.schedule.created_by:
            return HttpResponseForbidden()

        report.schedule.delete()

    except (ValueError, models.ReportSchedule.DoesNotExist):
        pass

    resp = {'error': False, 'message': _("Schedule cleared")}
    form = ReportScheduleForm()
    template = get_template("_form_horizontal.html")
    resp['form'] = template.render({'form': form})
    return JsonResponse(resp)
