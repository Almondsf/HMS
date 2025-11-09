# accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django import forms
from .models import User


class UserCreationForm(forms.ModelForm):
    """Form for creating new users in admin"""
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Password confirmation', widget=forms.PasswordInput)
    
    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'user_type', 'phone_number')
    
    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match")
        return password2
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class UserChangeForm(forms.ModelForm):
    """Form for updating users in admin"""
    password = ReadOnlyPasswordHashField(
        label="Password",
        help_text=(
            "Raw passwords are not stored, so there is no way to see this "
            "user's password, but you can change the password using "
            "<a href=\"../password/\">this form</a>."
        ),
    )
    
    class Meta:
        model = User
        fields = (
            'email', 'password', 'first_name', 'last_name',
            'user_type', 'phone_number', 'is_active',
            'is_staff', 'is_admin', 'is_superuser'
        )


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom User Admin"""
    form = UserChangeForm
    add_form = UserCreationForm
    
    list_display = (
        'email', 'first_name', 'last_name', 'user_type',
        'phone_number', 'is_active', 'is_staff', 'last_login'
    )
    
    list_filter = ('user_type', 'is_active', 'is_staff', 'is_admin', 'created_at')
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'phone_number')}),
        ('User Type', {'fields': ('user_type',)}),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_admin', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Important Dates', {'fields': ('last_login', 'date_joined', 'created_at', 'updated_at')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email', 'first_name', 'last_name', 'user_type',
                'phone_number', 'password1', 'password2',
                'is_active', 'is_staff', 'is_admin'
            ),
        }),
    )
    
    search_fields = ('email', 'first_name', 'last_name', 'phone_number')
    ordering = ('-created_at',)
    filter_horizontal = ('groups', 'user_permissions')
    readonly_fields = ('last_login', 'date_joined', 'created_at', 'updated_at')