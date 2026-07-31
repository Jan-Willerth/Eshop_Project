from django.contrib import admin

from .models import Category, Product, VatRate, ShippingMethod, PaymentMethod, Order, OrderItem


@admin.register(VatRate)
class VatRateAdmin(admin.ModelAdmin):
    list_display = ('rate', 'label', 'is_active')
    list_filter = ('is_active',)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'parent', 'is_active')
    list_filter = ('is_active', 'parent')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price_net', 'stock', 'is_active')
    list_filter = ('is_active', 'category', 'vat_rate')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(ShippingMethod)
class ShippingMethodAdmin(admin.ModelAdmin):
    list_display = ('name', 'price_net', 'vat_rate', 'is_active')
    list_filter = ('is_active', 'vat_rate')


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ('name', 'price_net', 'vat_rate', 'is_active')
    list_filter = ('is_active', 'vat_rate')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer_email', 'total_price_gross', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('customer_email', 'id')
    readonly_fields = ('created_at',)


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'product', 'quantity', 'unit_price_net')
