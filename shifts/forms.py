import datetime

from django import forms


class WorkerLoginForm(forms.Form):
    phone = forms.CharField(label="Telefon")
    password = forms.CharField(widget=forms.PasswordInput, label="Kodeord")
    remember_me = forms.BooleanField(required=False, label="Husk mig på denne enhed")


class RegisterForm(forms.Form):
    date = forms.CharField()
    shift = forms.CharField()
    register = forms.BooleanField(required=False)
    unregister = forms.BooleanField(required=False)

    def clean(self):
        super().clean()
        if self.is_valid():
            if self.cleaned_data["register"] and self.cleaned_data["unregister"]:
                self.add_error("unregister", "Cannot both register and unregister")
            elif (
                not self.cleaned_data["register"]
                and not self.cleaned_data["unregister"]
            ):
                self.add_error("register", "Must register or unregister")

    def clean_date(self):
        date_str = self.cleaned_data.pop("date", None)
        try:
            date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            self.add_error("date", "Date must be YYYY-MM-DD")
            return
        return date
