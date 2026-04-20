import uuid
import logging

from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from agent.models import Session, ProductCard, Order
from agent.serializers import (
    SessionSerializer, ProductCardSerializer, OrderSerializer
)
from agent.services.agent_service import process_message
from agent.services.order_service import place_mock_order

logger = logging.getLogger(__name__)


def _get_or_create_session(data: dict) -> Session:
    """Resolve an existing session or create a new one from the request data."""
    session_id = data.get("session_id")
    guest_id = data.get("guest_id", "")

    if session_id:
        try:
            return Session.objects.get(id=session_id)
        except Session.DoesNotExist:
            pass

    # Create new session
    return Session.objects.create(guest_id=guest_id or str(uuid.uuid4())[:16])


class HealthView(APIView):
    def get(self, request):
        gemini_configured = bool(getattr(settings, "GEMINI_API_KEY", ""))
        serpapi_configured = bool(getattr(settings, "SERPAPI_KEY", ""))
        return Response({
            "status": "ok",
            "gemini": "configured" if gemini_configured else "fallback mode (no key)",
            "serpapi": "configured" if serpapi_configured else "not configured (optional)",
        })


class SessionCreateView(APIView):
    """POST /api/agent/session/ — create a new chat session."""

    def post(self, request):
        guest_id = request.data.get("guest_id", str(uuid.uuid4())[:16])
        session = Session.objects.create(guest_id=guest_id)
        return Response(
            {"session_id": str(session.id), "guest_id": session.guest_id},
            status=status.HTTP_201_CREATED,
        )


class SessionDetailView(APIView):
    """GET /api/agent/session/<session_id>/ — full session history."""

    def get(self, request, session_id):
        try:
            session = Session.objects.get(id=session_id)
        except (Session.DoesNotExist, ValueError):
            return Response({"error": "Session not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(SessionSerializer(session).data)


class AskView(APIView):
    """POST /api/agent/ask/ — send a user message and get an agent reply."""

    def post(self, request):
        user_message = (request.data.get("message") or "").strip()
        if not user_message:
            return Response({"error": "message is required."}, status=status.HTTP_400_BAD_REQUEST)

        session = _get_or_create_session(request.data)

        try:
            reply_text, product_cards = process_message(session, user_message)
        except Exception as exc:
            logger.error("process_message failed: %s", exc, exc_info=True)
            return Response(
                {"error": "The agent encountered an error. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response({
            "reply": reply_text,
            "products": ProductCardSerializer(product_cards, many=True).data,
            "session_id": str(session.id),
            "session_state": session.state,
        })


class CompareView(APIView):
    """POST /api/agent/compare/ — side-by-side comparison of two product IDs."""

    def post(self, request):
        id_a = request.data.get("product_id_a")
        id_b = request.data.get("product_id_b")
        session_id = request.data.get("session_id")

        if not (id_a and id_b and session_id):
            return Response(
                {"error": "product_id_a, product_id_b, and session_id are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            session = Session.objects.get(id=session_id)
            a = ProductCard.objects.get(id=id_a, session=session)
            b = ProductCard.objects.get(id=id_b, session=session)
        except (Session.DoesNotExist, ProductCard.DoesNotExist, ValueError):
            return Response({"error": "Session or products not found."}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            "product_a": ProductCardSerializer(a).data,
            "product_b": ProductCardSerializer(b).data,
        })


class ConfirmPurchaseView(APIView):
    """POST /api/agent/confirm_purchase/ — place a mock order for a product."""

    def post(self, request):
        product_id = request.data.get("product_id")
        session_id = request.data.get("session_id")

        if not (product_id and session_id):
            return Response(
                {"error": "product_id and session_id are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            session = Session.objects.get(id=session_id)
            product = ProductCard.objects.get(id=product_id, session=session)
        except (Session.DoesNotExist, ProductCard.DoesNotExist, ValueError):
            return Response({"error": "Session or product not found."}, status=status.HTTP_404_NOT_FOUND)

        guest_id = request.data.get("guest_id", session.guest_id)
        order = place_mock_order(session, product, guest_id)

        return Response({
            "order_ref": order.order_ref,
            "product": product.name,
            "total": float(order.total_amount),
            "currency": order.currency,
            "payment_method": order.payment_method,
            "shipping_to": order.shipping_address,
            "estimated_delivery_days": order.estimated_delivery_days,
            "message": (
                f"✅ Order placed! Your {product.name} will arrive in "
                f"{order.estimated_delivery_days} days."
            ),
        }, status=status.HTTP_201_CREATED)


class OrderDetailView(APIView):
    """GET /api/orders/<order_id>/ — get order details."""

    def get(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id)
        except (Order.DoesNotExist, ValueError):
            return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(OrderSerializer(order).data)


class ProductDetailView(APIView):
    """GET /api/products/<card_id>/ — get single product card."""

    def get(self, request, card_id):
        try:
            card = ProductCard.objects.get(id=card_id)
        except (ProductCard.DoesNotExist, ValueError):
            return Response({"error": "Product not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(ProductCardSerializer(card).data)
