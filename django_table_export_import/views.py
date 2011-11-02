import os

from django.http import HttpResponse, HttpResponseRedirect
from django.core.urlresolvers import reverse
from forms import ImportTableForm


__author__ = 'darvin'

from django.shortcuts import render_to_response

from django.conf import settings
from django.db.models.loading import get_model

TABLE_EXPORTS_IMPORTS_SCHEME = getattr(settings, "TABLE_EXPORTS_IMPORTS_SCHEME", {})

def _get_model_list():
    result = []
    for app_name, app in TABLE_EXPORTS_IMPORTS_SCHEME.items():
        for model_name, model in app.items():
            result.append(get_model(app_name, model_name))
    return result


def exports_list(request):
    return render_to_response("exports_list.html", {"models":[(model._meta.verbose_name_plural,
                                                               (model._meta.app_label, model.__name__),
                                                               model,
                                                               ImportTableForm.from_model(model))
                                        for model in _get_model_list()]})

def _set_field_data(obj, field_name, field_scheme, field_value):
    field_type = field_scheme.get("type", "plain")

    if "setter" in field_scheme:
        field_scheme["setter"](obj, field_value)
    elif field_type=="submodel":
        for submodel_field_name_and_scheme, submodel_field_value in zip(field_scheme["scheme"].items(), field_value):
            submodel_field_name, submodel_field_scheme = submodel_field_name_and_scheme
            _set_field_data(getattr(obj, field_name), submodel_field_name, submodel_field_scheme, submodel_field_value)
        getattr(obj, field_name).save()
    else:
        setattr(obj, field_name, field_value)


def _import_data_in_object(model, scheme, pk, data):
    try:
        obj = model.objects.get(pk=pk)
    except model.DoesNotExist:
        return False

    data_cursor = 0
    for field_name, field_scheme in scheme.items():

        field_type = field_scheme.get("type", "plain")
        if field_type=="submodel":
            data_length = len(field_scheme["scheme"])
        else:
            data_length = field_scheme.get("data_length", 1)
        field_value = data[data_cursor:data_cursor+data_length]
        data_cursor += data_length
        if data_length==1:
            field_value = field_value[0]

        read_only = field_scheme.get("read_only", False)
        if read_only:
            continue

        _set_field_data(obj, field_name, field_scheme, field_value)

    obj.save()
    return True

def import_table_file(model, scheme, file):
    result = {"unknown_objects":0}
    data = _read_table(file)
    if data[0]!=["pk"]+_get_headers_from_model(model, scheme):
        raise NotImplementedError
    for row in data[1:]:
        if not _import_data_in_object(model=model, scheme=scheme, pk=int(row[0]), data=row[1:]):
            result["unknown_objects"] += 1
    return result

def import_file(request):
    if request.method=="POST":
        form = ImportTableForm(request.POST, request.FILES)
        if form.is_valid():
            app_label = request.POST.get("app_name")
            model_name = request.POST.get("model_name")
            import_table_file(model=get_model(app_label, model_name),
                              scheme=TABLE_EXPORTS_IMPORTS_SCHEME[app_label][model_name],
                              file=request.FILES['file'])
            return HttpResponseRedirect(reverse("table_export_list"))


def _get_header_from_field(field, field_scheme, prefix=""):
    field_type = field_scheme.get("type", "plain")
    if "caption" in field_scheme:
        return field_scheme["caption"]
    if field_type=="plain":
        return "{prefix}{name}".format(prefix=prefix, name=field.verbose_name)
    elif field_type=="submodel":
        return _get_headers_from_model(get_model(*field_scheme["model"]), field_scheme["scheme"], prefix="{name}/".format(name=field.verbose_name))


def _get_data_from_field(field_value, field_scheme):
    field_type = field_scheme.get("type", "plain")
    if "getter" in field_scheme:
        return field_scheme["getter"](field_value)
    elif field_type=="submodel":
        return _get_data_from_object(field_value, field_scheme["scheme"])
    elif field_type=="plain":
        return field_value
    else:
        raise NotImplementedError

def _get_data_from_object(obj, scheme):
    obj_data = []
    for field_name, field_scheme in scheme.items():
        new_data = _get_data_from_field(getattr(obj, field_name), field_scheme)
        if isinstance(new_data, list):
            obj_data += new_data
        else:
            obj_data.append(new_data)
    return obj_data

def xls_to_response(xls, fname):
    response = HttpResponse(mimetype="application/ms-excel")
    response['Content-Disposition'] = 'attachment; filename=%s' % fname
    xls.save(response)
    return response

def _write_table(headers, data, extension, sheet_name="data", file_basename="some"):
    if extension=="xls":
        import xlwt
        wb = xlwt.Workbook()
        ws = wb.add_sheet(sheet_name)
        for col, header in enumerate(headers):
            ws.write(0,col, header)
        for row, data_row in enumerate(data):
            for col, data_cell in enumerate(data_row):
                ws.write(1+row, col, data_cell)
        return xls_to_response(wb, "{name}.{ext}".format(name=file_basename, ext=extension))
    elif extension=="csv":
        from utils.unicode_csv import UnicodeWriter
        response = HttpResponse(mimetype="text/csv") #fixme
        response['Content-Disposition'] = 'attachment; filename=%s' % "{name}.{ext}".format(name=file_basename, ext=extension)
        writer = UnicodeWriter(response)
        writer.writerows([headers]+data)
        return response

    else:
        raise NotImplementedError

def _read_table(uploaded_file):
    result = []
    extension = os.path.splitext(uploaded_file.name)[-1]
    if extension==".xls":
        import xlrd
        wb = xlrd.open_workbook(file_contents=uploaded_file.read())
        sheet = wb.sheet_by_index(0)
        for row_i in range(sheet.nrows):
            result.append([cell.value for cell in sheet.row(row_i)])
    elif extension==".csv":
        from utils.unicode_csv import unicode_csv_reader

        reader = unicode_csv_reader(uploaded_file)
        for row in reader:
            result.append(row)
    else:
        raise NotImplementedError
    return result

def _get_headers_from_model(model, scheme, prefix=""):
    headers = []
    for field_name, field_scheme in scheme.items():
        field_found = False
        for field in model._meta.fields:
            if field.name==field_name:
                new_headers = _get_header_from_field(field, field_scheme, prefix=prefix)
                if isinstance(new_headers, list):
                    headers += new_headers
                else:
                    headers.append(new_headers)
                field_found = True
                break
        if not field_found:
            headers.append(_get_header_from_field(None, field_scheme, prefix=prefix))
    return headers

def export_table(request, app_label, model_id, extension):
    model = get_model(app_label, model_id)
    scheme = TABLE_EXPORTS_IMPORTS_SCHEME[app_label][model_id]
    headers = ["pk"]

    headers += _get_headers_from_model(model, scheme)


    data = []
    for obj in model.objects.all():
        data.append([obj.pk]+_get_data_from_object(obj, scheme))
    return _write_table(headers, data, extension, sheet_name=model._meta.verbose_name, file_basename="{app_label}_{model}".format(app_label=app_label, model=model_id))