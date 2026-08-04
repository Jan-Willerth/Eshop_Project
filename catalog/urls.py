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

    # ===================== AJAX CART =====================
    path('cart/ajax/add/<int:product_id>/', views.add_to_cart_ajax, name='add_to_cart_ajax'),
    path('cart/ajax/update/<int:product_id>/', views.update_cart_ajax, name='update_cart_ajax'),
    path('cart/ajax/remove/<int:product_id>/', views.remove_from_cart_ajax, name='remove_from_cart_ajax'),
]
