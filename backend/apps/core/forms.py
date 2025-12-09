# django imports
from django import forms
from django.core.exceptions import ValidationError

class BaseModelForm(forms.ModelForm):
    
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)