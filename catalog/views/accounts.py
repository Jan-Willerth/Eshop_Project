from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from ..forms import ProfileUpdateForm, RegistrationForm
from ..models import CompanyBillingProfile, Profile


# ===================== AUTH VIEWS =====================
def register(request: HttpRequest) -> HttpResponse:
    """Display and process the registration form; log the user in on
    success.
    """
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            messages.success(
                request,
                'Registrace proběhla úspěšně, jste přihlášeni.',
            )
            return redirect('catalog:homepage')
    else:
        form = RegistrationForm()

    return render(request, 'catalog/register.html', {'form': form})


@login_required(login_url='catalog:login')
def profile_update(request: HttpRequest) -> HttpResponse:
    """Allow a signed-in customer to maintain their saved checkout details."""
    profile, _ = Profile.objects.get_or_create(user=request.user)
    company_billing = getattr(profile, 'company_billing', None)

    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, user=request.user)
        if form.is_valid():
            data = form.cleaned_data
            with transaction.atomic():
                request.user.email = data['email']
                request.user.first_name = data['first_name']
                request.user.last_name = data['last_name']
                request.user.save(update_fields=['first_name', 'last_name', 'email'])

                profile.phone = data['phone']
                profile.street = data['street']
                profile.city = data['city']
                profile.zip_code = data['zip_code']
                profile.billing_different = data['billing_different']
                profile.save()

                if data['billing_different']:
                    CompanyBillingProfile.objects.update_or_create(
                        profile=profile,
                        defaults={
                            'contact_first_name': data['billing_first_name'],
                            'contact_last_name': data['billing_last_name'],
                            'company_name': data['billing_company_name'],
                            'ico': data['billing_ico'],
                            'dic': data['billing_dic'],
                            'street': data['billing_street'],
                            'city': data['billing_city'],
                            'zip_code': data['billing_zip_code'],
                        },
                    )

            messages.success(request, 'Profil byl úspěšně aktualizován.')
            return redirect('catalog:profile_update')
    else:
        initial = {
            'email': request.user.email,
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'phone': profile.phone,
            'street': profile.street,
            'city': profile.city,
            'zip_code': profile.zip_code,
        }
        initial['billing_different'] = profile.billing_different
        if company_billing:
            initial.update({
                'billing_first_name': company_billing.contact_first_name,
                'billing_last_name': company_billing.contact_last_name,
                'billing_company_name': company_billing.company_name,
                'billing_ico': company_billing.ico,
                'billing_dic': company_billing.dic,
                'billing_street': company_billing.street,
                'billing_city': company_billing.city,
                'billing_zip_code': company_billing.zip_code,
            })
        form = ProfileUpdateForm(initial=initial, user=request.user)

    return render(request, 'catalog/profile_update.html', {'form': form})
