from datetime import datetime, date, timedelta

from django.utils import timezone
from mock import Mock, call, ANY, patch
from django import forms
from django.contrib.admin.widgets import AdminDateWidget
from django.utils.translation import gettext as _
from daterange_filter.filter import DateRangeFilterBaseForm, DateRangeForm, DateTimeRangeForm, \
    DateRangeFilterAdminSplitDateTime, DateRangeFilter, DateTimeRangeFilter, clean_input_prefix
from tests import BaseTest


class CleanInputPrefixTest(BaseTest):

    @patch('daterange_filter.filter.FILTER_PREFIX', 'MY_CUSTOM_PREFIX___')
    def test_removes_prefix(self):
        input_ = {'MY_CUSTOM_PREFIX___some_field__gte': None}
        self.assertEquals(clean_input_prefix(input_), {'some_field__gte': None})

    def test_doesnt_raise_error_if_dict_key_doesnt_start_with_prefix(self):
        input_ = {'some_field__gte': None}
        self.assertEquals(clean_input_prefix(input_), {'some_field__gte': None})


class DateRangeFilterBaseFormTest(BaseTest):
    def setUp(self):
        self.request = Mock()

    def test_form_returns_all_media(self):
        del self.request.daterange_filter_media_included
        form = DateRangeFilterBaseForm(self.request)

        self.assertEqual(str(form.media), str(forms.Media(
            js=['admin/js/calendar.js', 'admin/js/admin/DateTimeShortcuts.js'],
            css={'all': ['admin/css/widgets.css']}
        )))

    def test_form_returns_empty_media_if_another_form_has_already_been_instantiated(self):
        del self.request.daterange_filter_media_included

        form_1 = DateRangeFilterBaseForm(self.request)
        form_2 = DateRangeFilterBaseForm(self.request)

        self.assertNotEqual(str(form_1.media), '')
        self.assertEqual(str(form_2.media), '')


class DateRangeFormTest(BaseTest):
    def test_create_fields(self):
        form = DateRangeForm(Mock(), field_name='spam')

        self.assertIsInstance(form.fields['drf__spam__gte'], forms.DateField)
        self.assertIsInstance(form.fields['drf__spam__lte'], forms.DateField)

    def test_field_attributes(self):
        form = DateRangeForm(Mock(), field_name='ham')

        self.assertEqual(form.fields['drf__ham__gte'].label, '')
        self.assertEqual(form.fields['drf__ham__gte'].localize, True)
        self.assertEqual(form.fields['drf__ham__gte'].required, False)
        self.assertIsInstance(form.fields['drf__ham__gte'].widget, AdminDateWidget)
        self.assertDictContainsSubset({'placeholder': _('From date')},
                                      form.fields['drf__ham__gte'].widget.attrs)

        self.assertEqual(form.fields['drf__ham__lte'].label, '')
        self.assertEqual(form.fields['drf__ham__lte'].localize, True)
        self.assertEqual(form.fields['drf__ham__lte'].required, False)
        self.assertIsInstance(form.fields['drf__ham__lte'].widget, AdminDateWidget)
        self.assertDictContainsSubset({'placeholder': _('To date')},
                                      form.fields['drf__ham__lte'].widget.attrs)

    def test_returns_all_media(self):
        request = Mock()
        del request.daterange_filter_media_included
        form_1 = DateRangeForm(request, field_name='spam')
        form_2 = DateRangeForm(request, field_name='ham')

        self.assertEqual(str(form_1.media), str(forms.Media(
            js=['admin/js/calendar.js', 'admin/js/admin/DateTimeShortcuts.js'],
            css={'all': ['admin/css/widgets.css']}
        )))
        self.assertEquals(str(form_2.media), '')


class DateTimeRangeFormTest(BaseTest):

    class DummyForm(DateTimeRangeForm):
        pass

    def test_create_fields(self):
        form = self.DummyForm(Mock(), field_name='spam')

        self.assertIsInstance(form.fields['drf__spam__gte'], forms.DateTimeField)
        self.assertIsInstance(form.fields['drf__spam__lte'], forms.DateTimeField)

    def test_field_attributes(self):
        form = self.DummyForm(Mock(), field_name='ham')

        self.assertEqual(form.fields['drf__ham__gte'].label, '')
        self.assertEqual(form.fields['drf__ham__gte'].localize, True)
        self.assertEqual(form.fields['drf__ham__gte'].required, False)
        self.assertIsInstance(form.fields['drf__ham__gte'].widget, DateRangeFilterAdminSplitDateTime)
        self.assertDictContainsSubset({'placeholder': _('From date')},
                                      form.fields['drf__ham__gte'].widget.attrs)

        self.assertEqual(form.fields['drf__ham__lte'].label, '')
        self.assertEqual(form.fields['drf__ham__lte'].localize, True)
        self.assertEqual(form.fields['drf__ham__lte'].required, False)
        self.assertIsInstance(form.fields['drf__ham__lte'].widget, DateRangeFilterAdminSplitDateTime)
        self.assertDictContainsSubset({'placeholder': _('To date')},
                                      form.fields['drf__ham__lte'].widget.attrs)

    def test_returns_all_media(self):
        request = Mock()
        del request.daterange_filter_media_included
        form_1 = DateTimeRangeForm(request, field_name='spam')
        form_2 = DateTimeRangeForm(request, field_name='ham')

        self.assertEqual(str(form_1.media), str(forms.Media(
            js=['admin/js/calendar.js', 'admin/js/admin/DateTimeShortcuts.js'],
            css={'all': ['admin/css/widgets.css']}
        )))
        self.assertEquals(str(form_2.media), '')


class DateRangeFilterTest(BaseTest):
    def setUp(self):
        self.request = Mock()
        self.filter_ = DateRangeFilter('spam', self.request, [], Mock(), Mock(), 'egg')

    def test_use_correctly_template(self):
        self.assertEqual(self.filter_.template, 'daterange_filter/filter.html')

    def test_form_uses_request(self):
        self.assertEqual(self.filter_.form.request, self.request)

    def test_choices_is_empty(self):
        self.assertEqual(self.filter_.choices(Mock()), [])

    def test_expected_params(self):
        self.assertItemsEqual(self.filter_.expected_parameters(), ['drf__egg__lte', 'drf__egg__gte'])

    @patch('daterange_filter.filter.DateRangeForm')
    def test_get_form(self, DateRangeForm):
        self.filter_.get_form(self.request)

        self.assertEqual([call(self.request, data=ANY, field_name='egg')],
                          DateRangeForm.call_args_list)

    def test_queryset_ignore_null_fields(self):
        queryset = Mock()
        params = {'drf__ham__gte': None, 'drf__ham__lte': None}
        filter_ = DateRangeFilter('spam', self.request, params, Mock(), Mock(), 'ham')

        return_value = filter_.queryset(self.request, queryset)

        self.assertEqual(return_value, queryset.filter.return_value)
        self.assertItemsEqual([call()], queryset.filter.call_args_list)

    def test_queryset_filters_by_date_from(self):
        queryset = Mock()
        params = {'drf__ham__gte': date(2014, 1, 3), 'drf__ham__lte': None}
        filter_ = DateRangeFilter('spam', self.request, params, Mock(), Mock(), 'ham')

        return_value = filter_.queryset(self.request, queryset)

        self.assertEqual(return_value, queryset.filter.return_value)
        self.assertItemsEqual([call(ham__gte=date(2014, 1, 3))], queryset.filter.call_args_list)

    def test_queryset_filters_by_date_to(self):
        queryset = Mock()
        data_end = date(2014, 1, 3)
        params = {'drf__ham__gte': None, 'drf__ham__lte': data_end}
        filter_ = DateRangeFilter('spam', self.request, params, Mock(), Mock(), 'ham')

        return_value = filter_.queryset(self.request, queryset)

        self.assertEqual(return_value, queryset.filter.return_value)
        self.assertEqual((data_end + timedelta(days=1)).strftime('%s'),
                          queryset.filter.call_args_list[0][1]['ham__lt'].strftime('%s'))

    def test_return_raw_queryset_if_form_is_invalid(self):
        queryset = Mock()
        params = {'drf__ham__gte': 'Yay!', 'drf__ham__lte': None}
        filter_ = DateRangeFilter('spam', self.request, params, Mock(), Mock(), 'ham')

        return_value = filter_.queryset(self.request, queryset)

        self.assertEqual(return_value, queryset)


class DateTimeRangeFilterTest(BaseTest):
    def setUp(self):
        self.request = Mock()
        self.filter_ = DateTimeRangeFilter('spam', self.request, {'drf__egg__lte_0': None, 'drf__egg__lte_1': None}, Mock(),
                                           Mock(), 'egg')

    def test_use_correctly_template(self):
        self.assertEqual(self.filter_.template, 'daterange_filter/filter.html')

    def test_form_uses_request(self):
        self.assertEqual(self.filter_.form.request, self.request)

    def test_choices_is_empty(self):
        self.assertEqual(self.filter_.choices(Mock()), [])

    def test_expected_params(self):
        self.assertItemsEqual(self.filter_.expected_parameters(), ['drf__egg__lte_0', 'drf__egg__lte_1', 'drf__egg__gte_0', 'drf__egg__gte_1'])

    @patch('daterange_filter.filter.DateTimeRangeForm')
    def test_get_form(self, DateTimeRangeForm):
        self.filter_.get_form(self.request)

        self.assertEqual([call(self.request, data={'drf__egg__lte_0': None, 'drf__egg__lte_1': None}, field_name='egg')],
                          DateTimeRangeForm.call_args_list)

    def test_queryset_ignore_null_fields(self):
        queryset = Mock()
        params = {'drf__ham__gte_0': None, 'drf__ham__gte_1': None, 'drf__ham__lte_0': None, 'drf__ham__lte_1': None}
        filter_ = DateTimeRangeFilter('spam', self.request, params, Mock(), Mock(), 'ham')

        return_value = filter_.queryset(self.request, queryset)

        self.assertEqual(return_value, queryset.filter.return_value)
        self.assertItemsEqual([call()], queryset.filter.call_args_list)

    def test_queryset_filters_by_date_from(self):
        queryset = Mock()
        params = {'drf__ham__gte_0': '2014-01-02', 'drf__ham__gte_1': '03:04:05',
                  'drf__ham__lte_0': None, 'drf__ham__lte_1': None}
        filter_ = DateTimeRangeFilter('spam', self.request, params, Mock(), Mock(), 'ham')

        return_value = filter_.queryset(self.request, queryset)
        timezoned_expected_result = timezone.make_aware(datetime(2014, 1, 2, 3, 4, 5), timezone.get_current_timezone())

        self.assertEqual(return_value, queryset.filter.return_value)
        self.assertItemsEqual([call(ham__gte=timezoned_expected_result)], queryset.filter.call_args_list)

    def test_queryset_filters_by_date_to(self):
        queryset = Mock()
        data_end = timezone.make_aware(datetime(2014, 1, 2, 3, 4, 5), timezone.get_current_timezone())
        params = {'drf__ham__lte_0': data_end.strftime('%Y-%m-%d'), 'drf__ham__lte_1': data_end.strftime('%H:%M:%S'),
                  'drf__ham__gte_0': None, 'drf__ham__gte_1': None}
        filter_ = DateTimeRangeFilter('spam', self.request, params, Mock(), Mock(), 'ham')

        return_value = filter_.queryset(self.request, queryset)

        self.assertEqual(return_value, queryset.filter.return_value)
        self.assertEqual(data_end, queryset.filter.call_args_list[0][1]['ham__lte'])

    def test_return_raw_queryset_if_form_is_invalid(self):
        queryset = Mock()
        params = {'drf__ham__gte_0': 'Yay!', 'drf__ham__gte_1': None, 'drf__ham__lte_0': None, 'drf__ham__lte_1': None}
        filter_ = DateTimeRangeFilter('spam', self.request, params, Mock(), Mock(), 'ham')

        return_value = filter_.queryset(self.request, queryset)

        self.assertEqual(return_value, queryset)
