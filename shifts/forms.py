import datetime

from django import forms


class WorkerLoginForm(forms.Form):
    phone = forms.CharField(label="Telefon")
    password = forms.CharField(widget=forms.PasswordInput, label="Kodeord")
    remember_me = forms.BooleanField(required=False, label="Husk mig på denne enhed")


class RegisterForm(forms.Form):
    action = forms.CharField()
    date = forms.CharField()
    shift = forms.CharField()
    owncomment = forms.CharField(required=False, max_length=500)
    # Legacy checkboxes:
    register = forms.BooleanField(required=False)
    unregister = forms.BooleanField(required=False)

    def __init__(self, **kwargs):
        try:
            data = kwargs["data"]
        except KeyError:
            pass
        else:
            ACTIONS = ("register_", "unregister_", "savecomment_", "registercomment_")
            actions = [k for k in data if k.startswith(ACTIONS)]
            if len(actions) == 1 and actions[0].count("_") == 2:
                action, date, shift = actions[0].split("_")
                kwargs["data"] = {
                    **data,
                    "action": action,
                    "date": date,
                    "shift": shift,
                }
                if action in ("savecomment", "registercomment"):
                    k = "owncomment_%s_%s" % (date, shift)
                    if k in data:
                        kwargs["data"]["owncomment"] = data[k]
            else:
                if data.get("register") and data.get("unregister"):
                    kwargs["data"] = {**data, "action": "register_and_unregister"}
                elif data.get("register"):
                    kwargs["data"] = {**data, "action": "register"}
                elif data.get("unregister"):
                    kwargs["data"] = {**data, "action": "unregister"}
        super().__init__(**kwargs)

    def clean_action(self):
        action_str = self.cleaned_data.pop("action", None)
        if not action_str:
            self.add_error("action", "Must register or unregister")
        elif action_str == "register_and_unregister":
            self.add_error("action", "Cannot both register and unregister")
        elif action_str not in (
            "register",
            "unregister",
            "savecomment",
            "registercomment",
        ):
            self.add_error("action", "Unknown action")
        return action_str

    def clean_date(self):
        date_str = self.cleaned_data.pop("date", None)
        try:
            date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            self.add_error("date", "Date must be YYYY-MM-DD")
            return
        return date
