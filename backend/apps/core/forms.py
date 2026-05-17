from django import forms


class BaseModelForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css_class = "input"
            existing = field.widget.attrs.get("class", "").strip()
            field.widget.attrs["class"] = f"{existing} {css_class}".strip()
