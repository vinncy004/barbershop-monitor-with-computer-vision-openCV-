from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User, CCTVStream, InventoryItem, BusinessPerformanceEntry
from .validators import validate_stream_url

class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)
    phone = forms.CharField(required=True, max_length=20)
    rtsp_url = forms.CharField(
        required=False, max_length=500, validators=[validate_stream_url]
    )

    class Meta:
        model = User
        fields = ["username", "email", "phone", "rtsp_url", "password1", "password2"]

class StreamForm(forms.ModelForm):
    class Meta:
        model = CCTVStream
        fields = ["name", "rtsp_url", "active"]

class StreamUpdateForm(forms.ModelForm):
    class Meta:
        model = CCTVStream
        fields = ["name", "rtsp_url", "active"]

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["email", "phone", "rtsp_url"]

class DashboardLoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={"autofocus": True}))


class InventoryItemForm(forms.ModelForm):
    class Meta:
        model = InventoryItem
        fields = ["product", "cost", "created_at"]
        widgets = {
            "created_at": forms.DateInput(attrs={"type": "date"}),
        }


class BusinessPerformanceEntryForm(forms.ModelForm):
    class Meta:
        model = BusinessPerformanceEntry
        fields = ["month", "expenses", "outcome"]
        widgets = {
            "month": forms.TextInput(attrs={"placeholder": "YYYY-MM"}),
        }
