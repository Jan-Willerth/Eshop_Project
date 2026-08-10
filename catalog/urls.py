from django.urls import path

from . import views

app_name = 'catalog'

urlpatterns = [
    # ===================== CATALOG =====================
    path('', views.product_list, name='product_list'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),

    # ===================== CART =====================
    path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/remove/<int:product_id>/', views.cart_remove, name='cart_remove'),
    path('cart/', views.cart_detail, name='cart_detail'),

    # ===================== ORDER =====================
    path('checkout/', views.checkout, name='checkout'),
    path('checkout/summary/', views.checkout_summary, name='checkout_summary'),

    # ===================== QUOTE =====================
    path('quote/', views.custom_quote, name='custom_quote'),
]
