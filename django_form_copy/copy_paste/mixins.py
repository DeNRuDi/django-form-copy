from django.db.models.fields.files import ImageFieldFile, ImageField
from django.db.models import ForeignKey, ManyToManyField
from django.core.files.storage import FileSystemStorage
from django.core.files.base import ContentFile
from django.forms import model_to_dict
from django.contrib import messages
from django.conf import settings
from django.apps import apps

from dateutil.parser import parse, ParserError
from datetime import datetime, date

import clipboard
import ast


class UtilsMixin:

    def _creating_actual_info_from_cb_process(self, model_info: dict) -> dict:
        models = apps.get_models()
        models_dict = {model.__name__: model for model in models}
        for field, values in model_info.items():
            if isinstance(values, dict):
                self._foreign_field_update_info_process(models_dict, values, model_info, field)
            elif isinstance(values, list):
                self._many_2_many_field_update_info_process(models_dict, values, model_info, field)
            elif isinstance(values, str):
                self._default_field_update_info_process(values, model_info, field)
            elif isinstance(values, tuple):
                self._image_field_update_info_process(values, model_info, field)
        return model_info

    def _foreign_field_update_info_process(self, models_dict: dict, values: dict, model_info: dict, field: str) -> None:
        model = models_dict.get(values['model'])
        if model:
            values = self._pre_format_model_dict(values, to_datetime=True)
            nested_values = self._get_or_create_nested_model(models_dict, values)
            nested_values = self._del_values_from_dict(nested_values, ['id', 'model'])
            obj, _ = model.objects.get_or_create(**nested_values)
            model_info.update({field: obj.id})

    def _many_2_many_field_update_info_process(self, models_dict: dict, values: list, model_info: dict, field: str) -> None:
        m2m_ids = []
        for m2m_item in values:
            model = models_dict.get(m2m_item['model'])
            if model:
                m2m_item = self._pre_format_model_dict(m2m_item, to_datetime=True)
                nested_m2m_item = self._get_or_create_nested_model(models_dict, m2m_item)
                nested_m2m_item = self._del_values_from_dict(nested_m2m_item, ['id', 'model'])
                obj, _ = model.objects.get_or_create(**nested_m2m_item)
                m2m_ids.append(obj.id)
        model_info.update({field: m2m_ids})

    def _default_field_update_info_process(self, values: str, model_info: dict, field: str) -> None:
        result = self._is_datetime(values)
        model_info.update({field: result}) if result else None

    @staticmethod
    def _image_field_update_info_process(values: tuple, model_info: dict, field: str) -> None:
        name, image_bytes, model_name = values
        image = ImageField(storage=FileSystemStorage(location=settings.BASE_DIR))
        image.attname = model_name

        content_file = ContentFile(image_bytes, name=name)
        image_file_field = ImageFieldFile(instance=content_file, field=image, name=name)
        model_info.update({field: image_file_field}) if image_file_field else None

    def _get_or_create_nested_model(self, models_dict: dict, m2m_item: dict) -> dict:
        nested_m2m_item = m2m_item.copy()
        for key, value in m2m_item.items():
            if isinstance(value, dict):
                model = models_dict.get(value['model'])
                if model:
                    values = self._pre_format_model_dict(value, to_datetime=True)
                    values = self._del_values_from_dict(values, ['id', 'model'])
                    obj, _ = model.objects.get_or_create(**values)
                    nested_m2m_item.update({key: obj})

        return nested_m2m_item

    def _del_values_from_dict(self, obj: dict, values_to_del: list) -> dict:
        new_obj = obj.copy()
        for key in list(new_obj.keys()):
            if isinstance(new_obj.get(key), dict):
                new_obj[key] = self._del_values_from_dict(new_obj[key], values_to_del)
            else:
                for value in values_to_del:
                    if value in new_obj:
                        new_obj.pop(value)
        return new_obj

    def _pre_format_model_dict(self, obj_dict: dict, to_datetime: bool = False) -> dict:
        field_info = {}
        for key, value in obj_dict.items():
            if isinstance(value, datetime):
                value = datetime.strftime(value, '%Y-%m-%d %H:%M:%S.%f %Z')
            elif isinstance(value, date):
                value = datetime.strftime(value, '%Y-%m-%d')
            elif isinstance(value, str) and to_datetime:
                result = self._is_datetime(value)
                value = result if result else value
            elif isinstance(value, ImageFieldFile):
                if value and value.file:
                    with value.open('rb') as file:
                        file_bytes = file.read()
                    value = (value.name, file_bytes, obj_dict['model']) if file_bytes else None
                else:
                    value = None
            field_info.update({key: value})

        return field_info

    def _expand_model_relations(self, obj):
        m2m_exclude = [f.name for f in obj._meta.many_to_many]
        m2m_exclude.append('id')

        obj_dict = model_to_dict(obj, exclude=m2m_exclude)
        obj_dict['model'] = obj.__class__.__name__
        obj_dict = self._pre_format_model_dict(obj_dict)

        for field in obj._meta.fields:
            if isinstance(field, ForeignKey):
                related_obj = getattr(obj, field.name)
                if related_obj is not None:
                    related_obj_dict = self._expand_model_relations(related_obj)
                    obj_info = self._pre_format_model_dict(related_obj_dict)
                    obj_dict.update({field.name: obj_info})
        for field in obj._meta.many_to_many:
            if isinstance(field, ManyToManyField):
                m2m_field = getattr(obj, field.name).all()
                data = []
                for related_obj in m2m_field:
                    d = self._expand_model_relations(related_obj)
                    d = self._pre_format_model_dict(d)
                    d.update({'model': related_obj.__class__.__name__})
                    data.append(d)
                obj_dict[field.name] = data

        return obj_dict

    @staticmethod
    def _is_datetime(datetime_string: str) -> datetime | bool:
        try:
            return parse(datetime_string)
        except (ParserError, OverflowError):
            return False


class CopyPasteMixin(UtilsMixin):
    change_form_template = 'copy_paste_templates/copy_paste.html'

    def get_changeform_initial_data(self, request):
        initial_data = super().get_changeform_initial_data(request)
        if 'paste' in request.GET:
            try:
                copy_paste_from_clipboard = ast.literal_eval(clipboard.paste())
                new_copy_paste_from_clipboard = self._creating_actual_info_from_cb_process(copy_paste_from_clipboard)
                initial_data.update(**new_copy_paste_from_clipboard)
                request.session['initial_data'] = clipboard.paste()
                messages.success(request, 'Data pasted successfully.')
            except Exception as err:
                messages.error(request, f'Failed to paste - data in the clipboard is not valid. | {err}')

        return initial_data

    def change_view(self, request, object_id, form_url='', extra_context=None):
        copy = request.GET.get('copy')
        generate = request.GET.get('generate')
        extra_context = extra_context or {}
        if copy or generate:
            obj = self.model.objects.get(pk=object_id)
            info = self._expand_model_relations(obj)
            if copy:
                messages.success(request, 'Data copied successfully.')
            elif generate:
                messages.success(request, 'Data generated successfully.')
            extra_context['info'] = info

        extra_context['is_https'] = 'https://' in request.build_absolute_uri()
        return super().change_view(request, object_id, form_url, extra_context)

    def response_post_save_add(self, request, obj):
        data = request.POST
        initial_data_str = request.session.get('initial_data')
        if initial_data_str:
            initial_data = ast.literal_eval(initial_data_str)
            initial_data = self._creating_actual_info_from_cb_process(initial_data)

            for field, value in initial_data.items():
                if isinstance(value, ImageFieldFile):
                    image_info = data.get(field)
                    clear_checkbox = data.get(f"{field}-clear")
                    if clear_checkbox != 'on' and image_info == '':
                        setattr(obj, field, value)

            obj.save()
            request.session.pop('initial_data', None)

        return super().response_post_save_add(request, obj)
