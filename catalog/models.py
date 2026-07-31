from django.db import models
from django.utils.text import slugify


class VatRate(models.Model):
    rate = models.DecimalField(max_digits=5, decimal_places=2)
    label = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.label} ({self.rate}%)"

    def __repr__(self):
        return f"<VatRate(id={self.id}, rate={self.rate}, label='{self.label}')>"


class OrderStatus(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"<OrderStatus(id={self.id}, code='{self.code}')>"


class User(models.Model):
    username = models.CharField(max_length=100, unique=True)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255)

    def __str__(self):
        return self.username

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"


class Category(models.Model):
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=150, unique=True, blank=True)
    is_active = models.BooleanField(default=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subcategories',
        db_column='parent_id'
    )

    class Meta:
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"<Category(id={self.id}, slug='{self.slug}')>"


class ShippingMethod(models.Model):
    name = models.CharField(max_length=100)
    price_net = models.DecimalField(max_digits=10, decimal_places=2)
    vat_rate = models.ForeignKey(VatRate, on_delete=models.PROTECT)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"<ShippingMethod(id={self.id}, name='{self.name}')>"


class PaymentMethod(models.Model):
    name = models.CharField(max_length=100)
    price_net = models.DecimalField(max_digits=10, decimal_places=2)
    vat_rate = models.ForeignKey(VatRate, on_delete=models.PROTECT)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"<PaymentMethod(id={self.id}, name='{self.name}')>"


class Product(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    description = models.TextField(blank=True, null=True)
    price_net = models.DecimalField(max_digits=10, decimal_places=2)
    package_weight = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True,
                                         verbose_name="Package weight (g)")
    package_height = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True,
                                         verbose_name="Package height (mm)")
    package_width = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True,
                                        verbose_name="Package width (mm)")
    package_length = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True,
                                         verbose_name="Package length (mm)")
    product_weight = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True,
                                         verbose_name="Product weight (g)")
    product_height = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True,
                                         verbose_name="Product height (mm)")
    product_width = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True,
                                        verbose_name="Product width (mm)")
    product_length = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True,
                                         verbose_name="Product length (mm)")
    stock = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products')
    vat_rate = models.ForeignKey(VatRate, on_delete=models.PROTECT)
    image = models.ImageField(upload_to='products/', blank=True, null=True)

    @property
    def price_gross(self):
        """Calculates the price including VAT."""
        if self.vat_rate and self.vat_rate.rate:
            return round(self.price_net * (1 + self.vat_rate.rate / 100), 2)
        return self.price_net

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"<Product(id={self.id}, slug='{self.slug}', price_net={self.price_net})>"


class Order(models.Model):
    # Nullable for guest checkout according to the diagram
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    status = models.ForeignKey(OrderStatus, on_delete=models.PROTECT, related_name='orders')
    shipping_method = models.ForeignKey(ShippingMethod, on_delete=models.PROTECT)
    payment_method = models.ForeignKey(PaymentMethod, on_delete=models.PROTECT)

    # Price and VAT rate snapshots
    shipping_price_net = models.DecimalField(max_digits=10, decimal_places=2)
    shipping_vat_rate = models.DecimalField(max_digits=5, decimal_places=2)
    payment_price_net = models.DecimalField(max_digits=10, decimal_places=2)
    payment_price_gross = models.DecimalField(max_digits=10, decimal_places=2)
    payment_vat_rate = models.DecimalField(max_digits=5, decimal_places=2)
    total_price_net = models.DecimalField(max_digits=10, decimal_places=2)
    total_price_gross = models.DecimalField(max_digits=10, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)

    # Customer and shipping information
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=50)
    shipping_first_name = models.CharField(max_length=100)
    shipping_last_name = models.CharField(max_length=100)
    shipping_street = models.CharField(max_length=255)
    shipping_city = models.CharField(max_length=100)
    shipping_zip_code = models.CharField(max_length=20)

    # Billing details (optional if matching shipping address)
    billing_first_name = models.CharField(max_length=100, blank=True, null=True)
    billing_last_name = models.CharField(max_length=100, blank=True, null=True)
    billing_company_name = models.CharField(max_length=150, blank=True, null=True)
    billing_ico = models.CharField(max_length=20, blank=True, null=True)
    billing_dic = models.CharField(max_length=20, blank=True, null=True)
    billing_street = models.CharField(max_length=255, blank=True, null=True)
    billing_city = models.CharField(max_length=100, blank=True, null=True)
    billing_zip_code = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return f"Order #{self.id} - {self.customer_email}"

    def __repr__(self):
        return f"<Order(id={self.id}, customer_email='{self.customer_email}', total_gross={self.total_price_gross})>"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.IntegerField()
    unit_price_net = models.DecimalField(max_digits=10, decimal_places=2)
    unit_price_gross = models.DecimalField(max_digits=10, decimal_places=2)
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2)

    def __str__(self):
        return f"{self.quantity}x {self.product.name} (Order #{self.order.id})"

    def __repr__(self):
        return f"<OrderItem(id={self.id}, order_id={self.order_id}, product_id={self.product_id}, qty={self.quantity})>"
