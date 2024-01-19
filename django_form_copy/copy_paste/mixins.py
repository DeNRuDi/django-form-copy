from django.db.models import ForeignKey, ManyToManyField
from django.forms import model_to_dict
from django.contrib import messages
from django.apps import apps

import clipboard
import ast


class CopyPasteMixin:
    change_form_template = 'copy_paste_templates/copy_paste.html'

    def get_changeform_initial_data(self, request):
        initial_data = super().get_changeform_initial_data(request)
        if 'paste' in request.GET:
            try:
                copy_paste_from_clipboard = ast.literal_eval(clipboard.paste())
                new_copy_paste_from_clipboard = self.creating_actual_info_from_cb_process(copy_paste_from_clipboard)
                initial_data.update(**new_copy_paste_from_clipboard)
                messages.success(request, 'Data pasted successfully.')
            except Exception as err:
                messages.error(request, f'Failed to paste - data in the clipboard is not valid. | {err}')

        return initial_data

    def change_view(self, request, object_id, form_url='', extra_context=None):
        if 'copy' in request.GET:
            obj = self.model.objects.get(pk=object_id)
            info = self.expand_model_relations(obj)
            messages.success(request, 'Data copied successfully.')
            extra_context = extra_context or {}
            extra_context['info'] = info
        return super().change_view(request, object_id, form_url, extra_context)

    @staticmethod
    def creating_actual_info_from_cb_process(model_info: dict) -> dict:
        models = apps.get_models()
        models_dict = {model.__name__: model for model in models}

        for field, values in model_info.items():
            if isinstance(values, dict):
                # foreign key
                model = models_dict.get(values['model'])
                if model:
                    values.pop('model', None)
                    values.pop('id', None)
                    obj, _ = model.objects.get_or_create(**values)
                    model_info.update({field: obj.id})
            elif isinstance(values, list):
                # manytomany field
                m2m_ids = []
                for m2m_item in values:
                    model = models_dict.get(m2m_item['model'])
                    if model:
                        m2m_item.pop('model', None)
                        m2m_item.pop('id', None)
                        obj, created = model.objects.get_or_create(**m2m_item)
                        m2m_ids.append(obj.id)
                model_info.update({field: m2m_ids})
        return model_info

    def expand_model_relations(self, obj):
        m2m_exclude = [f.name for f in obj._meta.many_to_many]
        m2m_exclude.append('id')

        obj_dict = model_to_dict(obj, exclude=m2m_exclude)
        obj_dict['model'] = obj.__class__.__name__

        for field in obj._meta.fields:
            if isinstance(field, ForeignKey):
                related_obj = getattr(obj, field.name)
                if related_obj is not None:
                    related_obj_dict = self.expand_model_relations(related_obj)
                    obj_dict.update({field.name: {k: v for k, v in related_obj_dict.items()}})

        for field in obj._meta.many_to_many:
            if isinstance(field, ManyToManyField):
                m2m_field = getattr(obj, field.name).all()
                data = []
                for related_obj in m2m_field:
                    d = model_to_dict(related_obj, exclude='id')
                    d.update({'model': related_obj.__class__.__name__})
                    data.append(d)
                obj_dict[field.name] = data

        return obj_dict
