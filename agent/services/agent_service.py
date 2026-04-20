"""
Agent Service — orchestrates the BuyWise AI shopping agent.

Two modes:
  1. Gemini mode   — uses gemini-2.0-flash with function calling (requires GEMINI_API_KEY)
  2. Fallback mode — deterministic keyword search + rule-based analysis (no API key needed)

Flow per user turn:
  user message → build_history → call Gemini → handle tool calls → final reply
"""
from __future__ import annotations
import json
import logging
import re
from decimal import Decimal
from typing import Optional

from django.conf import settings

from agent.models import Session, Message, ProductCard
from agent.services.search_service import search_products as do_search
from agent.services.order_service import place_mock_order

logger = logging.getLogger(__name__)

# ─── System Prompt ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are BuyWise, an expert AI shopping assistant.
Your mission: help users find the perfect product and guide them to a confident purchase.

━━━ ROLE ━━━
- Be a knowledgeable, trustworthy friend — not a pushy sales bot.
- Always explain WHY you're recommending a product.
- Stay concise: users dislike walls of text.
- Use ₹ for Indian Rupees.

━━━ WORKFLOW ━━━
1. Understand the user's need. If vague, ask exactly ONE clarifying question.
2. Call search_products with a refined query + any price ceiling.
3. From results, pick the 3–5 best candidates. Call rank_and_analyze.
4. Present clearly: name, price, top 2 pros, 1 con, and a verdict.
5. Handle follow-ups:
   - "Find cheaper" → search again with lower max_price
   - "Compare X and Y" → call compare_products
   - "Buy this / go ahead / order it" → call place_order (ONLY then)
6. NEVER call place_order without explicit user confirmation.

━━━ TONE ━━━
- Warm, direct, confident.
- Flag uncertainty: "I couldn't verify specs for X — double-check on Amazon."
- If budget is too tight for any real option, say so honestly.

━━━ CONSTRAINTS ━━━
- Only recommend products from search results.
- Never fabricate specs, prices, or availability.
- Maximum 5 products per search result set.
"""

# ─── Gemini client initialisation ────────────────────────────────────────────

def _get_gemini_model():
    """Lazy-initialise Gemini client. Returns None if no API key."""
    api_key = getattr(settings, "GEMINI_API_KEY", "") or ""
    if not api_key:
        return None
    try:
        import google.generativeai as genai
        from agent.tools import BUYWISE_TOOLS
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            system_instruction=SYSTEM_PROMPT,
            tools=[BUYWISE_TOOLS],
        )
        return model
    except Exception as exc:
        logger.warning("Gemini init failed: %s", exc)
        return None


# ─── Tool dispatcher ─────────────────────────────────────────────────────────

def _dispatch_tool(
    tool_name: str,
    tool_args: dict,
    session: Session,
) -> dict:
    """Execute a tool call and return a JSON-serialisable result dict."""

    if tool_name == "search_products":
        query = tool_args.get("query", "")
        max_price = tool_args.get("max_price")
        category = tool_args.get("category")
        raw_results = do_search(query, max_price, category, top_n=8)

        # Save ProductCards to DB
        created_cards = []
        for rank, item in enumerate(raw_results[:5], start=1):
            card = ProductCard.objects.create(
                session=session,
                external_id=str(item.get("external_id", "")),
                name=item["name"],
                brand=item.get("brand", ""),
                price=Decimal(str(item["price"])),
                currency=item.get("currency", "INR"),
                image_url=item.get("image_url", ""),
                product_url=item.get("product_url", ""),
                category=item.get("category", ""),
                specs=item.get("specs", {}),
                rating=item.get("rating"),
                review_count=item.get("review_count", 0),
                rank=rank,
                source=item.get("source", "dummy"),
            )
            created_cards.append({
                "id": card.id,
                "name": card.name,
                "brand": card.brand,
                "price": float(card.price),
                "currency": card.currency,
                "rating": float(card.rating) if card.rating else None,
                "review_count": card.review_count,
                "image_url": card.image_url,
                "product_url": card.product_url,
                "category": card.category,
                "specs": card.specs,
                "rank": card.rank,
            })

        session.state = "searching"
        session.save(update_fields=["state", "updated_at"])
        return {"products": created_cards, "count": len(created_cards)}

    elif tool_name == "rank_and_analyze":
        product_ids = tool_args.get("product_ids", [])
        user_priority = tool_args.get("user_priority", "value for money")
        cards = ProductCard.objects.filter(id__in=product_ids, session=session)

        analyzed = []
        for card in cards:
            pros, cons, verdict = _rule_based_analysis(card, user_priority)
            card.pros = pros
            card.cons = cons
            card.verdict = verdict
            card.save(update_fields=["pros", "cons", "verdict"])
            analyzed.append({
                "id": card.id,
                "name": card.name,
                "pros": pros,
                "cons": cons,
                "verdict": verdict,
            })

        session.state = "comparing"
        session.save(update_fields=["state", "updated_at"])
        return {"analyzed": analyzed}

    elif tool_name == "compare_products":
        id_a = tool_args.get("product_id_a")
        id_b = tool_args.get("product_id_b")
        try:
            a = ProductCard.objects.get(id=id_a, session=session)
            b = ProductCard.objects.get(id=id_b, session=session)
        except ProductCard.DoesNotExist:
            return {"error": "One or both product IDs not found in current session."}

        comparison = {
            "product_a": {
                "id": a.id,
                "name": a.name,
                "price": float(a.price),
                "rating": float(a.rating) if a.rating else None,
                "specs": a.specs,
                "pros": a.pros,
                "cons": a.cons,
            },
            "product_b": {
                "id": b.id,
                "name": b.name,
                "price": float(b.price),
                "rating": float(b.rating) if b.rating else None,
                "specs": b.specs,
                "pros": b.pros,
                "cons": b.cons,
            },
        }
        return {"comparison": comparison}

    elif tool_name == "place_order":
        product_id = tool_args.get("product_id")
        try:
            product = ProductCard.objects.get(id=product_id, session=session)
        except ProductCard.DoesNotExist:
            return {"error": "Product not found in current session."}

        guest_id = session.guest_id or ""
        order = place_mock_order(session, product, guest_id)
        return {
            "order_ref": order.order_ref,
            "product_name": product.name,
            "total_amount": float(order.total_amount),
            "currency": order.currency,
            "payment_method": order.payment_method,
            "shipping_address": order.shipping_address,
            "estimated_delivery_days": order.estimated_delivery_days,
            "status": order.status,
        }

    else:
        return {"error": f"Unknown tool: {tool_name}"}


# ─── Rule-based analysis (fallback + helper) ──────────────────────────────────

def _rule_based_analysis(
    card: ProductCard, user_priority: str
) -> tuple[list[str], list[str], str]:
    """
    Generate pros, cons, and a verdict for a product using deterministic rules.
    Used both in fallback mode and by rank_and_analyze tool.
    """
    pros: list[str] = []
    cons: list[str] = []
    price = float(card.price)
    specs = card.specs or {}

    # Rating
    rating = float(card.rating) if card.rating else 0
    if rating >= 4.3:
        pros.append(f"Highly rated ({rating}★ from {card.review_count:,} reviews)")
    elif rating >= 4.0:
        pros.append(f"Good rating — {rating}★")
    elif rating > 0:
        cons.append(f"Average rating ({rating}★)")

    # Price positioning
    if price < 2000:
        pros.append("Very affordable — great entry-level pick")
    elif price < 5000:
        pros.append("Good value for the price")
    elif price < 15000:
        pros.append("Mid-range — solid quality without overspending")
    else:
        cons.append("Premium pricing — ensure you need all the features")

    # Category-specific pros/cons
    cat = card.category.lower()
    if cat in ("earbuds", "headphones"):
        batt = specs.get("battery_total") or specs.get("battery", "")
        if batt:
            hours = re.search(r"(\d+)", str(batt))
            if hours:
                h = int(hours.group(1))
                if h >= 30:
                    pros.append(f"Excellent battery life ({batt})")
                elif h >= 15:
                    pros.append(f"Decent battery ({batt})")
                else:
                    cons.append(f"Limited battery ({batt})")
        if specs.get("anc") or "anc" in str(specs).lower():
            pros.append("Has ANC (noise cancellation)")
        if specs.get("water_resistance"):
            pros.append(f"Water resistant ({specs['water_resistance']})")

    elif cat == "laptops":
        ram = specs.get("ram", "")
        storage = specs.get("storage", "")
        proc = specs.get("processor", "")
        if "16gb" in ram.lower():
            pros.append("Generous 16GB RAM — great for multitasking")
        elif "8gb" in ram.lower():
            pros.append("8GB RAM — sufficient for most tasks")
        if "ssd" in storage.lower():
            pros.append("SSD storage — fast boot and load times")
        if "ryzen 7" in proc.lower() or "i7" in proc.lower():
            pros.append("High-performance processor")
        elif "ryzen 5" in proc.lower() or "i5" in proc.lower():
            pros.append("Mid-tier processor — good for coding and office work")
        elif "i3" in proc.lower():
            cons.append("Entry-level processor — may struggle with heavy tasks")

    elif cat == "smartphones":
        batt = specs.get("battery", "")
        if "6000" in str(batt):
            pros.append("Massive 6000mAh battery — all-day use")
        elif "5000" in str(batt):
            pros.append("Strong 5000mAh battery")
        cam = specs.get("camera", "")
        if "108mp" in str(cam).lower():
            pros.append("High-resolution 108MP camera")
        charging = specs.get("charging", "")
        if charging:
            w = re.search(r"(\d+)W", str(charging))
            if w and int(w.group(1)) >= 65:
                pros.append(f"Super-fast {charging} charging")

    elif cat == "air_fryers":
        cap_str = specs.get("capacity", "")
        cap_match = re.search(r"([\d.]+)", str(cap_str))
        if cap_match:
            cap = float(cap_match.group(1))
            if cap >= 5:
                pros.append(f"Large {cap_str} capacity — great for families")
            elif cap >= 4:
                pros.append(f"Good {cap_str} capacity — fits 3–4 people")
            else:
                cons.append(f"Compact {cap_str} — may be small for large families")
        if specs.get("warranty", "").startswith("2"):
            pros.append("2-year warranty included")

    # Priority boosts
    priority_lower = user_priority.lower()
    if "price" in priority_lower or "budget" in priority_lower:
        if price < 5000:
            pros.append("Fits a budget-conscious purchase")
        else:
            cons.append("May exceed your budget target")
    if "battery" in priority_lower:
        if not any("battery" in p.lower() for p in pros):
            cons.append("Battery life data unavailable — verify before buying")

    # Fallback
    if not pros:
        pros.append("Reputable brand with good availability")
    if not cons:
        cons.append("No major drawbacks identified from available data")

    # Verdict
    if rating >= 4.3 and price < 5000:
        verdict = f"⭐ Best overall pick — great value at ₹{price:,.0f}."
    elif rating >= 4.3:
        verdict = f"Top-rated option. Worth the ₹{price:,.0f} if quality is your priority."
    elif price < 2000:
        verdict = f"Best budget pick at ₹{price:,.0f} — ideal if minimising spend."
    else:
        verdict = f"Solid choice at ₹{price:,.0f} — reliable and well-reviewed."

    return pros, cons, verdict


# ─── Fallback simulator ───────────────────────────────────────────────────────

def _fallback_reply(session: Session, user_message: str) -> tuple[str, list]:
    """
    Deterministic fallback when Gemini API is unavailable.
    Extracts budget hints and category, searches dummy catalog,
    saves ProductCards, returns (reply_text, product_cards).
    """
    msg_lower = user_message.lower()

    # Detect max price from message
    max_price = None
    price_match = re.search(
        r"(?:under|below|less than|within|budget[:\s]+|max[:\s]+)[\s₹]*([\d,]+)", msg_lower
    )
    if price_match:
        max_price = float(price_match.group(1).replace(",", ""))

    # Detect category keywords
    cat_map = {
        "earbuds": "earbuds",
        "earbud": "earbuds",
        "tws": "earbuds",
        "headphone": "headphones",
        "headphones": "headphones",
        "laptop": "laptops",
        "notebook": "laptops",
        "phone": "smartphones",
        "smartphone": "smartphones",
        "mobile": "smartphones",
        "air fryer": "air_fryers",
        "airfryer": "air_fryers",
        "smartwatch": "smartwatches",
        "watch": "smartwatches",
        "fitness band": "smartwatches",
        "fan": "appliances",
        "kettle": "appliances",
    }
    detected_category = None
    for kw, cat in cat_map.items():
        if kw in msg_lower:
            detected_category = cat
            break

    # Check if user is confirming purchase
    buy_signals = ["buy", "order", "go ahead", "place order", "confirm", "yes, order",
                   "purchase", "get this", "i want this", "proceed"]
    if any(sig in msg_lower for sig in buy_signals):
        # Try to find the last selected product
        recent_product = ProductCard.objects.filter(session=session).order_by("rank").first()
        if recent_product:
            from agent.services.order_service import place_mock_order
            order = place_mock_order(session, recent_product, session.guest_id)
            reply = (
                f"✅ **Order Placed!**\n\n"
                f"**{recent_product.name}** has been ordered successfully.\n\n"
                f"🔖 Order Ref: `{order.order_ref}`\n"
                f"💰 Total: ₹{order.total_amount:,.0f}\n"
                f"💳 Payment: {order.payment_method}\n"
                f"📦 Delivery in {order.estimated_delivery_days} days\n\n"
                f"Your order is confirmed and will arrive soon!"
            )
            return reply, []
        return "Please select a product first before placing an order.", []

    raw = do_search(user_message, max_price, detected_category, top_n=5)
    if not raw:
        return (
            "I couldn't find products matching your request in my catalog. "
            "Try a different search term or adjust your budget.",
            [],
        )

    # Save cards to DB
    cards: list[ProductCard] = []
    for rank, item in enumerate(raw[:5], start=1):
        card = ProductCard.objects.create(
            session=session,
            name=item["name"],
            brand=item.get("brand", ""),
            price=Decimal(str(item["price"])),
            currency=item.get("currency", "INR"),
            image_url=item.get("image_url", ""),
            product_url=item.get("product_url", ""),
            category=item.get("category", ""),
            specs=item.get("specs", {}),
            rating=item.get("rating"),
            review_count=item.get("review_count", 0),
            rank=rank,
            source=item.get("source", "dummy"),
        )
        pros, cons, verdict = _rule_based_analysis(card, "value for money")
        card.pros = pros
        card.cons = cons
        card.verdict = verdict
        card.save(update_fields=["pros", "cons", "verdict"])
        cards.append(card)

    session.state = "comparing"
    session.save(update_fields=["state", "updated_at"])

    # Build reply
    top = cards[0]
    budget_note = f" under ₹{max_price:,.0f}" if max_price else ""
    reply_lines = [
        f"Great! I found **{len(cards)} options**{budget_note} for you. "
        f"My top pick is the **{top.name}** at ₹{top.price:,.0f}.\n",
        "Here's the shortlist — click **Buy** on any card to order, "
        "or tell me to compare two of them side-by-side! 👇",
    ]
    return "\n".join(reply_lines), cards


# ─── Main agent entrypoint ────────────────────────────────────────────────────

def process_message(
    session: Session,
    user_message: str,
) -> tuple[str, list[ProductCard]]:
    """
    Process a user message and return (reply_text, list_of_product_cards).
    Tries Gemini function-calling first; falls back to deterministic simulator.
    """
    # Save user message
    Message.objects.create(session=session, role="user", content=user_message)

    # Try Gemini
    model = _get_gemini_model()
    if model is None:
        logger.info("Gemini unavailable — using fallback simulator")
        reply, cards = _fallback_reply(session, user_message)
        Message.objects.create(session=session, role="model", content=reply)
        return reply, cards

    # Build history for Gemini (skip system prompt — it's in GenerativeModel)
    history = []
    past_messages = Message.objects.filter(session=session).exclude(
        content=user_message
    ).order_by("created_at")

    for msg in past_messages:
        role = "user" if msg.role == "user" else "model"
        history.append({"role": role, "parts": [msg.content]})

    try:
        chat = model.start_chat(history=history)
        response = chat.send_message(user_message)

        # Tool-calling loop
        final_cards: list[ProductCard] = []
        max_iterations = 5
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            parts = response.candidates[0].content.parts

            # Check for function calls
            fn_calls = [p for p in parts if hasattr(p, "function_call") and p.function_call.name]

            if not fn_calls:
                # Final text response
                text = "".join(
                    p.text for p in parts if hasattr(p, "text") and p.text
                ).strip()
                if not text:
                    text = "I've processed your request. What would you like to do next?"
                Message.objects.create(session=session, role="model", content=text)

                # Collect latest ProductCards from session
                final_cards = list(
                    ProductCard.objects.filter(session=session).order_by("rank")[:5]
                )
                return text, final_cards

            # Execute tool calls
            tool_results = []
            for part in fn_calls:
                fc = part.function_call
                tool_name = fc.name
                tool_args = dict(fc.args)
                logger.info("Tool call: %s(%s)", tool_name, tool_args)

                result = _dispatch_tool(tool_name, tool_args, session)
                tool_results.append({"function_name": tool_name, "result": result})

                # Log tool message
                Message.objects.create(
                    session=session,
                    role="tool",
                    content=json.dumps(result),
                    tool_name=tool_name,
                )

            # Send tool results back to Gemini
            import google.generativeai as genai
            fn_response_parts = []
            for tr in tool_results:
                fn_response_parts.append(
                    genai.protos.Part(
                        function_response=genai.protos.FunctionResponse(
                            name=tr["function_name"],
                            response={"result": tr["result"]},
                        )
                    )
                )
            response = chat.send_message(fn_response_parts)

    except Exception as exc:
        logger.error("Gemini agent error: %s", exc, exc_info=True)
        # Fall through to deterministic fallback
        reply, cards = _fallback_reply(session, user_message)
        Message.objects.create(session=session, role="model", content=reply)
        return reply, cards
