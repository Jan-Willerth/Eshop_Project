from django.urls import path

from . import views

app_name = 'catalog'

urlpatterns = [
    # ===================== CATALOG =====================
    path('', views.product_list, name='product_list'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),

    # ===================== CART =====================
    path('cart/', views.cart_detail, name='cart_detail'),
    path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
]
