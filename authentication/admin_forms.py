'''The Django admin's sign-in asks for the two-factor code too: no side door around it.'''

from django import forms
from django.contrib.admin.forms import AdminAuthenticationForm
from django.core.exceptions import ValidationError

from . import services, two_factor


class TwoFactorAdminAuthenticationForm(AdminAuthenticationForm):
    code = forms.CharField(
        label='Two-factor code',
        required=False,
        max_length=20,
        widget=forms.TextInput(attrs={'autocomplete': 'one-time-code', 'inputmode': 'numeric'}),
        help_text='From your authenticator app (or a recovery code). Leave blank if you don\'t use two-factor sign-in.',
    )

    def clean(self):
        cleaned = super().clean()  # the password (with lockout), and staff access
        user = self.user_cache
        if user is None:
            return cleaned
        if two_factor.is_enabled(user):
            if not two_factor.verify(user, cleaned.get('code')):
                services.record_failed_login(user.email)
                raise ValidationError('Enter the current code from your authenticator app.', code='invalid_code')
            services.record_successful_login(user)
        elif two_factor.setup_required(user):
            raise ValidationError(
                'Set up two-factor sign-in in the web app first, then sign in here with a code.',
                code='two_factor_setup_required',
            )
        return cleaned
