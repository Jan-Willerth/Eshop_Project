from django.urls import path
from django.contrib.auth import views as auth_views

from . import views

app_name = 'catalog'

urlpatterns = [
    # ===================== CATALOG =====================
    path('', views.homepage, name='homepage'),
    path('products/', views.product_list, name='product_list'),
    path('kategorie/<slug:slug>/', views.category_detail, name='category_detail'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),

    # =========== PRODUCT MANAGEMENT (STAFF) ============
    path('sklad/pridat/', views.product_create, name='product_create'),
    path('sklad/<int:pk>/upravit/', views.product_update, name='product_update'),
    path('sklad/<int:pk>/smazat/', views.product_delete, name='product_delete'),

    # ===================== CART =====================
    path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/remove/<int:product_id>/', views.cart_remove, name='cart_remove'),
    path('cart/', views.cart_detail, name='cart_detail'),

    # ===================== ORDER =====================
    path('checkout/', views.checkout, name='checkout'),
    path('checkout/summary/', views.checkout_summary, name='checkout_summary'),
    path('order/<int:order_id>/success/', views.order_success, name='order_success'),
    path('order/<int:order_id>/', views.order_detail, name='order_detail'),
    path('order/<int:order_id>/invoice/', views.order_invoice_download, name='order_invoice_download'),

    # ===================== AUTH =====================
    path('registrace/', views.register, name='register'),
    path('prihlaseni/', auth_views.LoginView.as_view(template_name='catalog/login.html'), name='login'),
    path('odhlaseni/', auth_views.LogoutView.as_view(), name='logout'),
    path('muj-profil/', views.profile_update, name='profile_update'),
    path('moje-objednavky/', views.order_history, name='order_history'),

    # ===================== QUOTE =====================
    path('quote/', views.custom_quote, name='custom_quote'),
]
