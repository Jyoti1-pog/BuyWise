import uuid
from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    """Extended profile for mock checkout — one per Django User."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    full_name = models.CharField(max_length=200)
    address_line1 = models.CharField(max_length=300)
    address_line2 = models.CharField(max_length=300, blank=True)
    city = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)
    phone = models.CharField(max_length=15, blank=True)
    default_payment = models.CharField(
        max_length=20,
        choices=[("card", "Card"), ("wallet", "Wallet"), ("upi", "UPI")],
        default="card",
    )
    card_last4 = models.CharField(max_length=4, blank=True)

    def __str__(self):
        return f"{self.full_name} ({self.user.username})"


class Session(models.Model):
    """One chat session per shopping intent. Supports guest users via cookie."""
    SESSION_STATES = [
        ("idle", "Idle"),
        ("searching", "Searching"),
        ("comparing", "Comparing"),
        ("awaiting_confirm", "Awaiting Confirmation"),
        ("ordered", "Ordered"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="sessions"
    )
    guest_id = models.CharField(max_length=64, blank=True, db_index=True)
    intent_summary = models.TextField(blank=True)
    state = models.CharField(max_length=30, choices=SESSION_STATES, default="idle")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Session {self.id} [{self.state}]"


class Message(models.Model):
    """Full multi-turn message history. Sent back to Gemini each turn."""
    ROLES = [
        ("user", "User"),
        ("model", "Model"),    # Gemini uses 'model' not 'assistant'
        ("tool", "Tool"),
    ]

    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=15, choices=ROLES)
    content = models.TextField()
    tool_call_id = models.CharField(max_length=200, blank=True)
    tool_name = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"[{self.role}] {self.content[:60]}"


class ProductCard(models.Model):
    """A product candidate surfaced during a session."""
    SOURCE_CHOICES = [("dummy", "Dummy Catalog"), ("serpapi", "SerpAPI")]

    session = models.ForeignKey(
        Session, on_delete=models.CASCADE, related_name="products"
    )
    external_id = models.CharField(max_length=200, blank=True)
    name = models.CharField(max_length=300)
    brand = models.CharField(max_length=100, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=5, default="INR")
    image_url = models.URLField(max_length=1000, blank=True)
    product_url = models.URLField(max_length=1000, blank=True)
    category = models.CharField(max_length=100, blank=True)
    specs = models.JSONField(default=dict)
    pros = models.JSONField(default=list)
    cons = models.JSONField(default=list)
    verdict = models.TextField(blank=True)
    rating = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    review_count = models.IntegerField(default=0)
    rank = models.IntegerField(default=0)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="dummy")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["rank"]

    def __str__(self):
        return f"#{self.rank} {self.name} ₹{self.price}"


class Order(models.Model):
    """Mock order record — no real payment."""
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("shipped", "Shipped"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        Session, on_delete=models.CASCADE, related_name="orders"
    )
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders"
    )
    guest_id = models.CharField(max_length=64, blank=True)
    order_ref = models.CharField(max_length=25, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="confirmed")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=5, default="INR")
    payment_method = models.CharField(max_length=30, default="card (mock)")
    shipping_address = models.TextField()
    estimated_delivery_days = models.IntegerField(default=5)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order {self.order_ref} — ₹{self.total_amount}"


class OrderItem(models.Model):
    """Line items within an order (supports multi-item carts in future)."""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        ProductCard, on_delete=models.SET_NULL, null=True, blank=True
    )
    product_name = models.CharField(max_length=300)   # snapshot at order time
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.IntegerField(default=1)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity}× {self.product_name}"
