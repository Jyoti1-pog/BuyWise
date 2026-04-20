import os
import uuid
import logging

from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from agent.models import Session, ProductCard, Order, SellerQA, VideoAnalysis
from agent.serializers import (
    SessionSerializer, ProductCardSerializer, OrderSerializer,
    SellerQASerializer, VideoAnalysisSerializer,
)
from agent.services.agent_service import process_message
from agent.services.order_service import place_mock_order
from agent.services.seller_service import ask_seller
from agent.services.video_service import analyze_video

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

    return Session.objects.create(guest_id=guest_id or str(uuid.uuid4())[:16])


# ─── Existing Views ───────────────────────────────────────────────────────────

class HealthView(APIView):
    def get(self, request):
        gemini_configured = bool(getattr(settings, "GEMINI_API_KEY", ""))
        serpapi_configured = bool(getattr(settings, "SERPAPI_KEY", ""))
        return Response({
            "status": "ok",
            "gemini": "configured" if gemini_configured else "fallback mode (no key)",
            "serpapi": "configured" if serpapi_configured else "not configured (optional)",
            "video_analysis": "enabled" if gemini_configured else "limited (no key)",
        })


class SessionCreateView(APIView):
    def post(self, request):
        guest_id = request.data.get("guest_id", str(uuid.uuid4())[:16])
        session = Session.objects.create(guest_id=guest_id)
        return Response(
            {"session_id": str(session.id), "guest_id": session.guest_id},
            status=status.HTTP_201_CREATED,
        )


class SessionDetailView(APIView):
    def get(self, request, session_id):
        try:
            session = Session.objects.get(id=session_id)
        except (Session.DoesNotExist, ValueError):
            return Response({"error": "Session not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(SessionSerializer(session).data)


class AskView(APIView):
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
    def get(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id)
        except (Order.DoesNotExist, ValueError):
            return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(OrderSerializer(order).data)


class ProductDetailView(APIView):
    def get(self, request, card_id):
        try:
            card = ProductCard.objects.get(id=card_id)
        except (ProductCard.DoesNotExist, ValueError):
            return Response({"error": "Product not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(ProductCardSerializer(card).data)


# ─── NEW: Quick Order (One-Tap) ───────────────────────────────────────────────

class QuickOrderView(APIView):
    """
    POST /api/agent/quick_order/
    One-tap order — places immediately without confirmation modal.
    Response is same as confirm_purchase but faster (HTTP 201).
    """

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
            "product_id": product.id,
            "total": float(order.total_amount),
            "currency": order.currency,
            "payment_method": order.payment_method,
            "estimated_delivery_days": order.estimated_delivery_days,
            "quick": True,  # Flag to distinguish quick order in frontend
        }, status=status.HTTP_201_CREATED)


# ─── NEW: Ask the Seller ──────────────────────────────────────────────────────

class AskSellerView(APIView):
    """POST /api/agent/ask_seller/ — Q&A about a specific product."""

    def post(self, request):
        product_id = request.data.get("product_id")
        question = (request.data.get("question") or "").strip()
        session_id = request.data.get("session_id")

        if not (product_id and question):
            return Response(
                {"error": "product_id and question are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            product = ProductCard.objects.get(id=product_id)
        except (ProductCard.DoesNotExist, ValueError):
            return Response({"error": "Product not found."}, status=status.HTTP_404_NOT_FOUND)

        qa = ask_seller(product, question)
        return Response(SellerQASerializer(qa).data, status=status.HTTP_201_CREATED)


class SellerQAHistoryView(APIView):
    """GET /api/agent/seller_qa/<product_id>/ — full Q&A history for a product."""

    def get(self, request, product_id):
        try:
            product = ProductCard.objects.get(id=product_id)
        except (ProductCard.DoesNotExist, ValueError):
            return Response({"error": "Product not found."}, status=status.HTTP_404_NOT_FOUND)

        qa_list = SellerQA.objects.filter(product=product).order_by("created_at")
        return Response({
            "product": product.name,
            "qa": SellerQASerializer(qa_list, many=True).data,
        })


# ─── NEW: Video Analysis ──────────────────────────────────────────────────────

class AnalyzeVideoView(APIView):
    """
    POST /api/agent/analyze_video/
    Accepts: video_url (YouTube, Instagram, TikTok) OR uploaded video file.
    Returns: VideoAnalysis data + matched catalog product.
    """
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        session_id = request.data.get("session_id")
        guest_id = request.data.get("guest_id", "")
        video_url = (request.data.get("video_url") or "").strip()
        video_file = request.FILES.get("video_file")

        if not video_url and not video_file:
            return Response(
                {"error": "Either video_url or video_file is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        session = _get_or_create_session({"session_id": session_id, "guest_id": guest_id})

        # Handle uploaded file — save to media/videos/
        uploaded_file_path = ""
        uploaded_file_name = ""
        if video_file:
            upload_dir = os.path.join(str(settings.MEDIA_ROOT), "videos")
            os.makedirs(upload_dir, exist_ok=True)
            unique_name = f"{uuid.uuid4().hex[:8]}_{video_file.name}"
            save_path = os.path.join(upload_dir, unique_name)
            with open(save_path, "wb") as f:
                for chunk in video_file.chunks():
                    f.write(chunk)
            uploaded_file_path = save_path
            uploaded_file_name = video_file.name

        try:
            analysis = analyze_video(
                session=session,
                video_url=video_url,
                uploaded_file_path=uploaded_file_path,
                uploaded_file_name=uploaded_file_name,
            )
        except Exception as exc:
            logger.error("analyze_video failed: %s", exc, exc_info=True)
            return Response(
                {"error": f"Video analysis failed: {str(exc)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Build human-readable reply
        name = analysis.extracted_product_name or "the product"
        confidence = analysis.confidence
        conf_emoji = {"high": "🎯", "medium": "🔍", "low": "❓"}.get(confidence, "🔍")

        specs_text = ", ".join(analysis.extracted_specs[:4]) if analysis.extracted_specs else ""
        price_text = f" (approx. {analysis.extracted_price_hint})" if analysis.extracted_price_hint else ""

        if confidence == "low":
            reply = (
                f"❓ I couldn't clearly identify a product in this video. "
                f"Try a clearer product review or unboxing video, or add your Gemini API key for full analysis."
            )
        else:
            reply = (
                f"{conf_emoji} I found **{name}**{price_text} in this video! "
                + (f"Key specs: {specs_text}. " if specs_text else "")
                + f"\n\n{analysis.video_summary}\n\n"
                + ("You can ask me anything about this product, find similar options, or order it with one tap!" if analysis.matched_product else "Want me to search for similar products?")
            )

        response_data = {
            "session_id": str(session.id),
            "analysis": VideoAnalysisSerializer(analysis).data,
            "reply": reply,
        }

        if analysis.matched_product:
            from agent.services.agent_service import _rule_based_analysis
            card = analysis.matched_product
            pros, cons, verdict = _rule_based_analysis(card, "value for money")
            card.pros = pros
            card.cons = cons
            card.verdict = verdict
            card.save(update_fields=["pros", "cons", "verdict"])
            response_data["matched_product"] = ProductCardSerializer(card).data

        return Response(response_data, status=status.HTTP_201_CREATED)
