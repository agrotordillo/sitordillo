from django import forms


class BaseModelForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                css_class = "h-4 w-4 border border-gray-300 rounded-base text-primary-600 cursor-pointer"
            else:
                css_class = "input"
            existing = field.widget.attrs.get("class", "").strip()
            field.widget.attrs["class"] = f"{existing} {css_class}".strip()
