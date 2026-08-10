from decimal import Decimal
import io

from django.db import models
from django.core.mail import EmailMessage
from django.db.models.signals import post_save
from django.dispatch import receiver
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

# ===================== VAT RATE =====================
class VatRate(models.Model):
    """VAT percentage rate applied to products and services."""

    rate = models.DecimalField(max_digits=5, decimal_places=2)
    label = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f"{self.label} ({self.rate}%)"

    def __repr__(self) -> str:
        return f"<VatRate(id={self.id}, rate={self.rate}, label='{self.label}')>"


# ===================== ORDER STATUS =====================
class OrderStatus(models.Model):
    """Operational state of an order (pending, paid, shipped, etc.)."""

    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"<OrderStatus(id={self.id}, code='{self.code}')>"


# ===================== USER =====================
class User(models.Model):
    """Registered user account."""

    username = models.CharField(max_length=100, unique=True)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255)

    def __str__(self) -> str:
        return self.username

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}')>"


# ===================== CATEGORY =====================
class Category(models.Model):
    """Hierarchical product category with optional parent."""

    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=150, unique=True, blank=True)
    is_active = models.BooleanField(default=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subcategories'
    )

    class Meta:
        verbose_name_plural = 'Categories'

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"<Category(id={self.id}, slug='{self.slug}')>"


# ===================== SHIPPING METHOD =====================
class ShippingMethod(models.Model):
    """Available delivery option."""

    name = models.CharField(max_length=100)
    price_net = models.DecimalField(max_digits=10, decimal_places=2)
    vat_rate = models.ForeignKey(VatRate, on_delete=models.PROTECT)
    is_active = models.BooleanField(default=True)

    @property
    def price_gross(self) -> Decimal:
        """Return gross price including VAT."""
        if self.vat_rate and self.vat_rate.rate:
            return round(self.price_net * (1 + self.vat_rate.rate / 100), 2)
        return self.price_net

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"<ShippingMethod(id={self.id}, name='{self.name}')>"


# ===================== PAYMENT METHOD =====================
class PaymentMethod(models.Model):
    """Available payment option."""

    name = models.CharField(max_length=100)
    price_net = models.DecimalField(max_digits=10, decimal_places=2)
    vat_rate = models.ForeignKey(VatRate, on_delete=models.PROTECT)
    is_active = models.BooleanField(default=True)

    @property
    def price_gross(self) -> Decimal:
        """Return gross price including VAT."""
        if self.vat_rate and self.vat_rate.rate:
            return round(self.price_net * (1 + self.vat_rate.rate / 100), 2)
        return self.price_net

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"<PaymentMethod(id={self.id}, name='{self.name}')>"


# ===================== PRODUCT =====================
class Product(models.Model):
    """Catalog product with dimensions, pricing, and stock tracking."""

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    description = models.TextField(blank=True, null=True)
    price_net = models.DecimalField(max_digits=10, decimal_places=2)

    package_weight = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True, verbose_name="Package weight (g)"
    )
    package_height = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True, verbose_name="Package height (mm)"
    )
    package_width = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True, verbose_name="Package width (mm)"
    )
    package_length = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True, verbose_name="Package length (mm)"
    )

    product_weight = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True, verbose_name="Product weight (g)"
    )
    product_height = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True, verbose_name="Product height (mm)"
    )
    product_width = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True, verbose_name="Product width (mm)"
    )
    product_length = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True, verbose_name="Product length (mm)"
    )

    stock = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products')
    vat_rate = models.ForeignKey(VatRate, on_delete=models.PROTECT)
    image = models.ImageField(upload_to='products/', blank=True, null=True)

    @property
    def price_gross(self) -> Decimal:
        """Return gross price including VAT."""
        if self.vat_rate and self.vat_rate.rate:
            return round(self.price_net * (1 + self.vat_rate.rate / 100), 2)
        return self.price_net

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"<Product(id={self.id}, slug='{self.slug}', price_net={self.price_net})>"


# ===================== ORDER =====================
class Order(models.Model):
    """Customer order with frozen price snapshots, delivery, and billing details."""

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    status = models.ForeignKey(OrderStatus, on_delete=models.PROTECT, related_name='orders')
    shipping_method = models.ForeignKey(ShippingMethod, on_delete=models.PROTECT)
    payment_method = models.ForeignKey(PaymentMethod, on_delete=models.PROTECT)

    # Price and VAT rate snapshots frozen at time of purchase
    shipping_price_net = models.DecimalField(max_digits=10, decimal_places=2)
    shipping_vat_rate = models.DecimalField(max_digits=5, decimal_places=2)
    payment_price_net = models.DecimalField(max_digits=10, decimal_places=2)
    payment_price_gross = models.DecimalField(max_digits=10, decimal_places=2)
    payment_vat_rate = models.DecimalField(max_digits=5, decimal_places=2)
    total_price_net = models.DecimalField(max_digits=10, decimal_places=2)
    total_price_gross = models.DecimalField(max_digits=10, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)

    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=50)
    shipping_first_name = models.CharField(max_length=100)
    shipping_last_name = models.CharField(max_length=100)
    shipping_street = models.CharField(max_length=255)
    shipping_city = models.CharField(max_length=100)
    shipping_zip_code = models.CharField(max_length=20)

    billing_first_name = models.CharField(max_length=100, blank=True, null=True)
    billing_last_name = models.CharField(max_length=100, blank=True, null=True)
    billing_company_name = models.CharField(max_length=150, blank=True, null=True)
    billing_ico = models.CharField(max_length=20, blank=True, null=True)
    billing_dic = models.CharField(max_length=20, blank=True, null=True)
    billing_street = models.CharField(max_length=255, blank=True, null=True)
    billing_city = models.CharField(max_length=100, blank=True, null=True)
    billing_zip_code = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self) -> str:
        return f"Order #{self.id} - {self.customer_email}"

    def __repr__(self) -> str:
        return f"<Order(id={self.id}, customer_email='{self.customer_email}', total_gross={self.total_price_gross})>"


# ===================== ORDER ITEM =====================
class OrderItem(models.Model):
    """Line item within an order storing frozen unit prices and quantity."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.IntegerField()
    unit_price_net = models.DecimalField(max_digits=10, decimal_places=2)
    unit_price_gross = models.DecimalField(max_digits=10, decimal_places=2)
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2)

    def __str__(self) -> str:
        return f"{self.quantity}x {self.product.name} (Order #{self.order.id})"

    def __repr__(self) -> str:
        return f"<OrderItem(id={self.id}, order_id={self.order_id}, product_id={self.product_id}, qty={self.quantity})>"


# ===================== QUOTE REQUEST =====================
class QuoteRequest(models.Model):
    """Individual quote request for bulk or custom orders."""

    first_name = models.CharField(max_length=100, default='', verbose_name="Jméno")
    last_name = models.CharField(max_length=100, default='', verbose_name="Příjmení")
    email = models.EmailField()
    phone = models.CharField(max_length=50, blank=True)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    quantity = models.IntegerField()
    message = models.TextField(blank=True)
    agreed_to_terms = models.BooleanField(
        default=False,
        verbose_name="Souhlas s podmínkami individuální objednávky"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Poptávka na míru"
        verbose_name_plural = "Poptávky na míru"

    def __str__(self) -> str:
        return f"Poptávka #{self.id} – {self.first_name} {self.last_name} ({self.quantity} ks)"

    def __repr__(self) -> str:
        return f"<QuoteRequest(id={self.id}, email='{self.email}', processed={self.processed})>"


# ===================== SIGNALS =====================
def generate_invoice_pdf(order):
    """Generate a PDF invoice for a business order and return bytes."""
    buf = io.BytesIO()
    p = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, height - 60, f"Faktura č. {order.id}")
    p.setFont("Helvetica", 12)
    y = height - 100
    p.drawString(50, y, f"Dodavatel: Můj E-shop s.r.o.")
    y -= 20
    p.drawString(50, y, f"Odběratel: {order.billing_company_name or ''}, {order.billing_street}, {order.billing_city}")
    y -= 20
    p.drawString(50, y, f"IČO: {order.billing_ico or ''}, DIČ: {order.billing_dic or ''}")
    y -= 40
    p.drawString(50, y, "Položky:")
    y -= 20
    for item in order.items.all():
        line = f"{item.product.name} x {item.quantity} = {item.unit_price_gross * item.quantity:.2f} Kč"
        p.drawString(70, y, line)
        y -= 20
    y -= 10
    p.drawString(50, y, f"Celkem: {order.total_price_gross:.2f} Kč")

    p.showPage()
    p.save()
    pdf = buf.getvalue()
    buf.close()
    return pdf


@receiver(post_save, sender=Order)
def send_order_confirmation(sender, instance, created, **kwargs):
    """Send confirmation email, with PDF invoice for business orders."""
    if not created:
        return

    subject = f'Potvrzení objednávky č. {instance.id}'
    body = 'Děkujeme za objednávku. Daňový doklad, případně fakturu, vám zašleme e-mailem.'
    email = EmailMessage(
        subject=subject,
        body=body,
        from_email=None,
        to=[instance.customer_email],
    )

    if instance.billing_company_name:
        pdf = generate_invoice_pdf(instance)
        email.attach(f'faktura_{instance.id}.pdf', pdf, 'application/pdf')

    email.send()
