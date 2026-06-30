from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User, CCTVStream

class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)
    phone = forms.CharField(required=True, max_length=20)
    rtsp_url = forms.URLField(required=False)

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
