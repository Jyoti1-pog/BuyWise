from django.contrib import admin
from agent.models import UserProfile, Session, Message, ProductCard, Order, OrderItem, SellerQA, VideoAnalysis


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display  = ["id", "state", "guest_id", "intent_summary", "created_at"]
    list_filter   = ["state"]
    search_fields = ["id", "guest_id"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display  = ["id", "session", "role", "content_preview", "created_at"]
    list_filter   = ["role"]
    search_fields = ["content"]

    def content_preview(self, obj):
        return obj.content[:80]
    content_preview.short_description = "Content"


@admin.register(ProductCard)
class ProductCardAdmin(admin.ModelAdmin):
    list_display  = ["id", "name", "brand", "price", "currency", "rating", "rank", "category", "session"]
    list_filter   = ["category", "source"]
    search_fields = ["name", "brand"]
    readonly_fields = ["created_at"]


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display  = ["order_ref", "status", "total_amount", "currency", "payment_method", "guest_id", "created_at"]
    list_filter   = ["status"]
    search_fields = ["order_ref", "guest_id"]
    readonly_fields = ["id", "created_at"]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ["id", "order", "product_name", "unit_price", "quantity", "subtotal"]


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ["full_name", "city", "default_payment", "phone"]


@admin.register(SellerQA)
class SellerQAAdmin(admin.ModelAdmin):
    list_display  = ["id", "product", "question_preview", "answer_preview", "created_at"]
    search_fields = ["question", "answer"]
    readonly_fields = ["created_at"]

    def question_preview(self, obj):
        return obj.question[:60]
    question_preview.short_description = "Question"

    def answer_preview(self, obj):
        return obj.answer[:80]
    answer_preview.short_description = "Answer"


@admin.register(VideoAnalysis)
class VideoAnalysisAdmin(admin.ModelAdmin):
    list_display  = [
        "id", "extracted_product_name", "extracted_brand",
        "confidence", "video_type", "video_source_type", "created_at"
    ]
    list_filter   = ["confidence", "video_type", "video_source_type"]
    search_fields = ["extracted_product_name", "extracted_brand", "video_url"]
    readonly_fields = ["created_at", "raw_gemini_response"]
