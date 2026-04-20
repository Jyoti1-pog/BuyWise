from django.contrib import admin
from agent.models import UserProfile, Session, Message, ProductCard, Order, OrderItem


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ["id", "state", "guest_id", "intent_summary", "created_at"]
    list_filter = ["state"]
    search_fields = ["id", "guest_id"]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ["id", "session", "role", "content_preview", "created_at"]
    list_filter = ["role"]
    search_fields = ["content"]

    def content_preview(self, obj):
        return obj.content[:80]
    content_preview.short_description = "Content"


@admin.register(ProductCard)
class ProductCardAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "brand", "price", "currency", "rating", "rank", "session"]
    list_filter = ["category", "source"]
    search_fields = ["name", "brand"]


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["order_ref", "status", "total_amount", "currency", "payment_method", "created_at"]
    list_filter = ["status"]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ["id", "order", "product_name", "unit_price", "quantity"]


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ["full_name", "city", "default_payment"]
