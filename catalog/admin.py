from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Category, Product, VatRate, ShippingMethod, PaymentMethod,
    Order, OrderItem
)


# ===================== VAT RATES =====================
@admin.register(VatRate)
class VatRateAdmin(admin.ModelAdmin):
    list_display = ('rate', 'label', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('label',)


# ===================== CATEGORIES =====================
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Admin configuration for product categories with hierarchical parent support."""
    list_display = ('name', 'slug', 'parent', 'is_active')
    list_filter = ('is_active', 'parent')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}


# ===================== ORDER ITEMS (INLINE) =====================
class OrderItemInline(admin.TabularInline):
    """Inline view to display order items within the Order detail page."""
    model = OrderItem
    extra = 0  # Prevents rendering empty extra forms by default
    readonly_fields = ('product', 'quantity', 'unit_price_net', 'unit_price_gross', 'vat_rate')
    can_delete = False  # Order items should remain historical audit trail


# ===================== ORDERS =====================
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer_email', 'total_price_gross', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('customer_email', 'id')
    readonly_fields = ('total_price_net', 'total_price_gross', 'created_at')
    inlines = [OrderItemInline]

    fieldsets = (
        (None, {'fields': ('user', 'status', 'shipping_method', 'payment_method')}),
        ('Pricing', {'fields': (
            'shipping_price_net', 'shipping_vat_rate',
            'payment_price_net', 'payment_price_gross', 'payment_vat_rate',
            'total_price_net', 'total_price_gross'
        )}),
        ('Customer', {'fields': ('customer_email', 'customer_phone')}),
        ('Shipping address', {'fields': (
            'shipping_first_name', 'shipping_last_name',
            'shipping_street', 'shipping_city', 'shipping_zip_code'
        )}),
        ('Billing address', {'fields': (
            'billing_first_name', 'billing_last_name',
            'billing_company_name', 'billing_ico', 'billing_dic',
            'billing_street', 'billing_city', 'billing_zip_code'
        )}),
    )


# ===================== SHIPPING METHODS =====================
@admin.register(ShippingMethod)
class ShippingMethodAdmin(admin.ModelAdmin):
    list_display = ('name', 'price_net', 'vat_rate', 'is_active')
    list_filter = ('is_active', 'vat_rate')
    search_fields = ('name',)


# ===================== PAYMENT METHODS =====================
@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ('name', 'price_net', 'vat_rate', 'is_active')
    list_filter = ('is_active', 'vat_rate')
    search_fields = ('name',)


# ===================== PRODUCTS =====================
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price_net', 'display_price_gross', 'stock', 'is_active')
    list_filter = ('category', 'is_active', 'vat_rate')
    search_fields = ('name', 'slug', 'description')
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ('price_net', 'stock', 'is_active')

    fieldsets = (
        (None, {'fields': ('name', 'slug', 'description', 'category', 'vat_rate')}),
        ('Pricing', {'fields': ('price_net',)}),
        ('Stock', {'fields': ('stock', 'is_active')}),
        ('Package dimensions', {'fields': (
            'package_weight', 'package_height', 'package_width', 'package_length'
        )}),
        ('Product dimensions', {'fields': (
            'product_weight', 'product_height', 'product_width', 'product_length'
        )}),
        ('Image', {'fields': ('image',)}),
    )

    @admin.display(description='Price gross (incl. VAT)')
    def display_price_gross(self, obj: Product) -> str:
        """Return formatted gross price using the model's property."""
        return f"{obj.price_gross:.2f} Kč"


# ===================== ORDER ITEMS (STANDALONE) =====================
@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    """Standalone admin view for auditing and searching individual order items across orders."""
    list_display = ('order', 'product', 'quantity', 'unit_price_net', 'unit_price_gross')
    list_filter = ('order__status',)
    search_fields = ('product__name', 'order__customer_email')
