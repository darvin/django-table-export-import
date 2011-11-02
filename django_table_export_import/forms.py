from django import forms


class ImportTableForm(forms.Form):
    file  = forms.FileField()
    app_name = forms.CharField(widget=forms.widgets.HiddenInput())
    model_name = forms.CharField(widget=forms.widgets.HiddenInput())

    @classmethod
    def from_model(cls, model):
        return cls(initial={"model_name":model.__name__, "app_name":model._meta.app_label})