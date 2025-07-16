# -*- coding: utf-8 -*-


'''
Has the filter that allows to filter by a date range.

'''
import copy
import datetime
import django
from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError, ImproperlyConfigured
from django.db import models
from django.utils.translation import gettext as _
from django.templatetags.static import static
from django.conf import settings
from django.forms.utils import from_current_timezone

use_suit = 'DATE_RANGE_FILTER_USE_WIDGET_SUIT'

if hasattr(settings, use_suit):
    DATE_RANGE_FILTER_USE_WIDGET_SUIT = getattr(settings, use_suit)
else:
    DATE_RANGE_FILTER_USE_WIDGET_SUIT = False

if DATE_RANGE_FILTER_USE_WIDGET_SUIT:
    try:
        from suit.widgets import (
            SuitDateWidget as AdminDateWidget,
            SuitTimeWidget as AdminTimeWidget,
            SuitSplitDateTimeWidget as AdminSplitDateTime
        )
    except ImportError:
        from django.contrib.admin.widgets import (
            AdminDateWidget,
            AdminTimeWidget,
            AdminSplitDateTime
        )
else:
    from django.contrib.admin.widgets import (
        AdminDateWidget,
        AdminTimeWidget,
        AdminSplitDateTime
    )

try:
    from django.utils.html import format_html
except ImportError:
    from django.utils.html import conditional_escape, mark_safe

    def format_html(format_string, *args, **kwargs):
        args_safe = map(conditional_escape, args)
        kwargs_safe = dict((k, conditional_escape(v)) for (k, v) in kwargs.items())
        return mark_safe(format_string.format(*args_safe, **kwargs_safe))


# Django doesn't deal well with filter params that look like queryset lookups.
FILTER_PREFIX = 'drf__'


def clean_input_prefix(input_):
    return dict((key.split(FILTER_PREFIX)[1] if key.startswith(FILTER_PREFIX) else key, val)
                for (key, val) in input_.items())


class DateRangeFilterAdminSplitDateTime(AdminSplitDateTime):
    def __init__(self, *args, date_attrs=None, time_attrs=None, **kwargs):
        if date_attrs is None:
            date_attrs = {}
        if time_attrs is None:
            time_attrs = {}
        widgets = [
            AdminDateWidget(attrs=date_attrs),
            AdminTimeWidget(attrs=time_attrs),
        ]
        # NOTE: We're deliberately skipping `AdminSplitDateTime.__init__`
        # here, because it'll override our `widgets`.
        forms.MultiWidget.__init__(self, widgets, **kwargs)

    def format_output(self, rendered_widgets):
        return format_html('<p>{0} {1}<br />{2} {3}</p>',
                           '', rendered_widgets[0],
                           '', rendered_widgets[1])


class DateRangeFilterBaseForm(forms.Form):
    def __init__(self, request, *args, **kwargs):
        super(DateRangeFilterBaseForm, self).__init__(*args, **kwargs)
        self.request = request

    @property
    def media(self):
        try:
            if getattr(self.request, 'daterange_filter_media_included'):
                return forms.Media()
        except AttributeError:
            setattr(self.request, 'daterange_filter_media_included', True)

            js = ["calendar.js", "admin/DateTimeShortcuts.js"]
            css = ['widgets.css']

            return forms.Media(
                js=[static("admin/js/%s" % path) for path in js],
                css={'all': [static("admin/css/%s" % path) for path in css]}
            )


class DateRangeForm(DateRangeFilterBaseForm):

    def __init__(self, *args, **kwargs):
        field_name = kwargs.pop('field_name')
        super(DateRangeForm, self).__init__(*args, **kwargs)

        self.fields['%s%s__gte' % (FILTER_PREFIX, field_name)] = forms.DateField(
            label='',
            widget=AdminDateWidget(
                attrs={'placeholder': _('From date')}
            ),
            localize=True,
            required=False
        )

        self.fields['%s%s__lte' % (FILTER_PREFIX, field_name)] = forms.DateField(
            label='',
            widget=AdminDateWidget(
                attrs={'placeholder': _('To date')}
            ),
            localize=True,
            required=False,
        )

    # Django 1.4 can't handle media inheritance well. We have to do it manually.
    if django.VERSION < (1, 5):
        @property
        def media(self):
            return super(DateRangeForm, self).media


class CustomSplitDateTimeField(forms.SplitDateTimeField):
    """
    Permit an empty time sub-field (and interpret as zero, ie.  midnight).

    The default `SplitDateTimeField` will complain if you leave the
    time sub-field blank (unless the date sub-field is *also* blank).
    """

    def __init__(self, *args, default_time=None, **kwargs):
        self.default_time = default_time or datetime.time(0, 0, 0)
        super().__init__(*args, **kwargs)

    def compress(self, data_list):
        if data_list:
            # Raise a validation error if date is empty.
            #
            # This is only possible if the *time* sub-field is populated
            # but the date sub-field isn't.
            if data_list[0] in self.empty_values:
                raise ValidationError(self.error_messages['invalid_date'], code='invalid_date')
            if data_list[1] in self.empty_values:
                # It's perfectly okay for the time sub-field to be left
                # empty, as long as the date sub-field is populated!
                # Just interpret it as the given `default_time`.
                result = datetime.datetime.combine(data_list[0], self.default_time)
            else:
                result = datetime.datetime.combine(*data_list)
            return from_current_timezone(result)
        return None


class DateTimeRangeForm(DateRangeFilterBaseForm):

    def __init__(self, *args, default_start_time=None, default_end_time=None,
            from_widget_kwargs=None, to_widget_kwargs=None, **kwargs):
        field_name = kwargs.pop('field_name')
        super(DateTimeRangeForm, self).__init__(*args, **kwargs)

        if from_widget_kwargs is None:
            from_widget_kwargs = dict(
                date_attrs={'placeholder': _('From date')},
                time_attrs={'placeholder': _('From time')})
        if to_widget_kwargs is None:
            to_widget_kwargs = dict(
                date_attrs={'placeholder': _('To date')},
                time_attrs={'placeholder': _('To time')})

        self.fields['%s%s__gte' % (FILTER_PREFIX, field_name)] = CustomSplitDateTimeField(
            label='',
            widget=DateRangeFilterAdminSplitDateTime(**from_widget_kwargs),
            localize=True,
            required=False,
            default_time=default_start_time,
        )

        self.fields['%s%s__lte' % (FILTER_PREFIX, field_name)] = CustomSplitDateTimeField(
            label='',
            widget=DateRangeFilterAdminSplitDateTime(**to_widget_kwargs),
            localize=True,
            required=False,
            default_time=default_end_time,
        )

    # Django 1.4 can't handle media inheritance well. We have to do it manually.
    if django.VERSION < (1, 5):
        @property
        def media(self):
            return super(DateTimeRangeForm, self).media


class DateRangeFilter(admin.filters.FieldListFilter):
    template = 'daterange_filter/filter.html'

    def __init__(self, field, request, params, model, model_admin, field_path):
        self.lookup_kwarg_since = '%s%s__gte' % (FILTER_PREFIX, field_path)
        self.lookup_kwarg_upto = '%s%s__lte' % (FILTER_PREFIX, field_path)

        super(DateRangeFilter, self).__init__(
            field, request, params, model, model_admin, field_path)
        self.form = self.get_form(request)

        # Query parameters are returned as lists in Django 5 and need to
        # be unpacked to be used with this filter.
        # Only one value is expected for each parameter as the user can
        # only enter one date for each field.
        for param, param_item_list in self.used_parameters.items():
            if isinstance(param_item_list, list) and len(param_item_list) == 1:
                self.used_parameters[param] = param_item_list[0]

    def choices(self, cl):
        """
        Pop the original parameters, and return the date filter & other filter
        parameters.
        """
        hidden_params = copy.deepcopy(cl.params)
        hidden_params.pop(self.lookup_kwarg_since, None)
        hidden_params.pop(self.lookup_kwarg_upto, None)
        return ({
            'get_query': hidden_params,
        }, )

    def expected_parameters(self):
        return [self.lookup_kwarg_since, self.lookup_kwarg_upto]

    def get_form(self, request):
        return DateRangeForm(request, data=self.used_parameters,
                             field_name=self.field_path)

    def queryset(self, request, queryset):
        if self.form.is_valid():
            # get no null params
            filter_params = clean_input_prefix(dict(filter(lambda x: bool(x[1]), self.form.cleaned_data.items())))

            # filter by upto included
            lookup_upto = self.lookup_kwarg_upto.lstrip(FILTER_PREFIX)
            if filter_params.get(lookup_upto) is not None:
                lookup_kwarg_upto_value = filter_params.pop(lookup_upto)
                filter_params['%s__lt' % self.field_path] = lookup_kwarg_upto_value + datetime.timedelta(days=1)

            return queryset.filter(**filter_params)
        else:
            return queryset

    def get_facet_counts(self, pk_attname, filtered_qs):
        """
        Implements the abstract method from `FacetsMixin` in Django 5.0.
        We don't need a proper implementation of this method given
        facets are not shown or supported by ths filter. As such returning
        an `ImproperlyConfigured` exception is sufficient.

        """
        raise ImproperlyConfigured(
            "DateRangeFilter has not been configured to support facet counts. "
            "Please override the `get_facet_counts` method to implement this functionality."
        )        


class DateTimeRangeFilter(admin.filters.FieldListFilter):
    template = 'daterange_filter/filter.html'

    def __init__(self, field, request, params, model, model_admin, field_path):
        self.lookup_kwarg_since_0 = '%s%s__gte_0' % (FILTER_PREFIX, field_path)
        self.lookup_kwarg_since_1 = '%s%s__gte_1' % (FILTER_PREFIX, field_path)
        self.lookup_kwarg_upto_0 = '%s%s__lte_0' % (FILTER_PREFIX, field_path)
        self.lookup_kwarg_upto_1 = '%s%s__lte_1' % (FILTER_PREFIX, field_path)

        super(DateTimeRangeFilter, self).__init__(
            field, request, params, model, model_admin, field_path)
        self.form = self.get_form(request)

        # Query parameters are returned as lists in Django 5.0 and need to
        # be unpacked to be used with this filter.
        # Only one value is expected for each parameter as the user can
        # only enter one date and time for each pair of fields.
        for param, param_item_list in self.used_parameters.items():
            if isinstance(param_item_list, list) and len(param_item_list) == 1:
                self.used_parameters[param] = param_item_list[0]

    def choices(self, cl):
        """
        Pop the original parameters, and return the date filter & other filter
        parameters.
        """
        hidden_params = copy.deepcopy(cl.params)
        hidden_params.pop(self.lookup_kwarg_since_0, None)
        hidden_params.pop(self.lookup_kwarg_since_1, None)
        hidden_params.pop(self.lookup_kwarg_upto_0, None)
        hidden_params.pop(self.lookup_kwarg_upto_1, None)
        return ({
            'get_query': hidden_params,
        }, )

    def expected_parameters(self):
        return [self.lookup_kwarg_since_0, self.lookup_kwarg_since_1, self.lookup_kwarg_upto_0, self.lookup_kwarg_upto_1]

    def get_form(self, request):
        return DateTimeRangeForm(request, data=self.used_parameters, field_name=self.field_path)

    def queryset(self, request, queryset):
        if self.form.is_valid():
            # get no null params
            filter_params = clean_input_prefix(dict(filter(lambda x: bool(x[1]), self.form.cleaned_data.items())))
            return queryset.filter(**filter_params)
        else:
            return queryset

    def get_facet_counts(self, pk_attname, filtered_qs):
        """
        Implements the abstract method from `FacetsMixin` in Django 5.0.
        We don't need a proper implementation of this method given
        facets are not shown or supported by ths filter. As such returning
        an `ImproperlyConfigured` exception is sufficient.

        """
        raise ImproperlyConfigured(
            "DateTimeRangeFilter has not been configured to support facet counts. "
            "Please override the `get_facet_counts` method to implement this functionality."
        )


# register the filters
admin.filters.FieldListFilter.register(
    lambda f: isinstance(f, models.DateField), DateRangeFilter)
admin.filters.FieldListFilter.register(
    lambda f: isinstance(f, models.DateTimeField), DateTimeRangeFilter)
