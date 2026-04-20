from rest_framework import serializers
from agent.models import Session, Message, ProductCard, Order, OrderItem, SellerQA, VideoAnalysis


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ["id", "role", "content", "tool_name", "created_at"]


class ProductCardSerializer(serializers.ModelSerializer):
    price = serializers.FloatField()
    rating = serializers.FloatField()

    class Meta:
        model = ProductCard
        fields = [
            "id", "name", "brand", "price", "currency",
            "image_url", "product_url", "category",
            "specs", "pros", "cons", "verdict",
            "rating", "review_count", "rank", "source",
        ]


class SessionSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)
    products = ProductCardSerializer(many=True, read_only=True)

    class Meta:
        model = Session
        fields = [
            "id", "guest_id", "intent_summary", "state",
            "created_at", "updated_at", "messages", "products",
        ]


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ["id", "product_name", "unit_price", "quantity", "subtotal"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "id", "order_ref", "status", "total_amount", "currency",
            "payment_method", "shipping_address", "estimated_delivery_days",
            "created_at", "items",
        ]


class SellerQASerializer(serializers.ModelSerializer):
    class Meta:
        model = SellerQA
        fields = ["id", "product", "question", "answer", "created_at"]


class VideoAnalysisSerializer(serializers.ModelSerializer):
    matched_product = ProductCardSerializer(read_only=True)

    class Meta:
        model = VideoAnalysis
        fields = [
            "id", "video_url", "video_source_type", "thumbnail_url",
            "extracted_product_name", "extracted_brand", "extracted_category",
            "extracted_specs", "extracted_price_hint",
            "video_type", "video_summary", "confidence",
            "matched_product", "created_at",
        ]
