"""
Seller Service — Gemini acts as the knowledgeable seller of a specific product.

The AI answers customer questions about a product using:
 1. Actual product specs from the DB
 2. General Gemini knowledge about the product
 3. Honest uncertainty when specs are missing

Falls back to rule-based spec matching when no API key is configured.
"""
from __future__ import annotations
import logging
from typing import Optional

from django.conf import settings

from agent.models import ProductCard, SellerQA

logger = logging.getLogger(__name__)

# ─── Seller Persona Prompt ────────────────────────────────────────────────────

def _build_seller_prompt(product: ProductCard, question: str) -> str:
    specs_text = "\n".join(f"  - {k}: {v}" for k, v in (product.specs or {}).items())
    pros_text  = "\n".join(f"  • {p}" for p in (product.pros or []))
    cons_text  = "\n".join(f"  • {c}" for c in (product.cons or []))

    return f"""You are a helpful, honest seller of the {product.name} by {product.brand or 'this brand'}.

PRODUCT DETAILS:
  Name: {product.name}
  Brand: {product.brand}
  Price: ₹{product.price}
  Category: {product.category}
  Rating: {product.rating}★ ({product.review_count:,} reviews)

KNOWN SPECS:
{specs_text or '  (Not specified)'}

KNOWN PROS:
{pros_text or '  (Not specified)'}

KNOWN CONS:
{cons_text or '  (Not specified)'}

SELLER GUIDELINES:
- Answer as a knowledgeable, honest seller — not a marketer.
- Use the specs above as ground truth; supplement with your knowledge.
- If a spec is NOT in the list above, say "I don't see that spec listed — please verify on the product page" rather than guessing.
- Keep answers under 3 short sentences.
- For warranty/return questions: mention standard e-commerce policies (typically 7–30 days returns, manufacturer warranty varies).
- For compatibility questions: be specific (iOS/Android, Windows/Mac, etc.)
- Use a friendly, conversational tone.

CUSTOMER QUESTION:
{question}

Answer:"""


# ─── Gemini Seller Response ───────────────────────────────────────────────────

def _ask_gemini_seller(product: ProductCard, question: str) -> Optional[str]:
    """Call Gemini with seller persona. Returns answer string or None."""
    api_key = getattr(settings, "GEMINI_API_KEY", "") or ""
    if not api_key:
        return None

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name="gemini-2.0-flash")
        prompt = _build_seller_prompt(product, question)
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as exc:
        logger.error("Gemini seller Q&A failed: %s", exc)
        return None


# ─── Rule-Based Fallback ──────────────────────────────────────────────────────

_QUESTION_PATTERNS = {
    # Battery
    "battery": lambda s: s.get("battery_total") or s.get("battery") or s.get("battery_earbuds"),
    "charge": lambda s: s.get("charging") or s.get("battery_total") or s.get("battery"),
    # Connectivity
    "bluetooth": lambda s: s.get("connectivity"),
    "wireless": lambda s: s.get("connectivity"),
    "wifi": lambda s: s.get("connectivity"),
    # Water
    "waterproof": lambda s: s.get("water_resistance"),
    "water resistant": lambda s: s.get("water_resistance"),
    "water": lambda s: s.get("water_resistance"),
    "ip": lambda s: s.get("water_resistance"),
    # Processor
    "processor": lambda s: s.get("processor"),
    "chip": lambda s: s.get("processor"),
    "cpu": lambda s: s.get("processor"),
    # Ram
    "ram": lambda s: s.get("ram"),
    "memory": lambda s: s.get("ram"),
    # Storage
    "storage": lambda s: s.get("storage"),
    "ssd": lambda s: s.get("storage"),
    # Display
    "display": lambda s: s.get("display"),
    "screen": lambda s: s.get("display"),
    # Camera
    "camera": lambda s: s.get("camera"),
    "mp": lambda s: s.get("camera"),
    # Weight
    "weight": lambda s: s.get("weight"),
    # Warranty
    "warranty": lambda s: s.get("warranty"),
    # Driver
    "driver": lambda s: s.get("driver"),
    # Anc
    "anc": lambda s: s.get("anc") or s.get("noise cancell"),
    "noise cancel": lambda s: s.get("anc") or s.get("noise cancell"),
}


def _rule_based_seller_answer(product: ProductCard, question: str) -> str:
    """Fallback seller answer using spec pattern matching."""
    q_lower = question.lower()
    specs = product.specs or {}

    # Try to match question to a known spec
    for keyword, getter in _QUESTION_PATTERNS.items():
        if keyword in q_lower:
            value = getter(specs)
            if value:
                return (
                    f"Yes! The {product.name} has the following for {keyword}: **{value}**. "
                    f"Check the product page to confirm the latest details."
                )

    # Warranty / return policy catch-all
    if any(w in q_lower for w in ["return", "refund", "policy"]):
        return (
            f"Most sellers offer a 7–10 day return policy for electronics in original packaging. "
            f"The {product.name} also typically comes with the manufacturer's warranty — "
            f"check the specific retailer for exact terms."
        )

    # iOS/Android compatibility
    if any(w in q_lower for w in ["iphone", "ios", "apple"]):
        cat = product.category.lower()
        if cat in ("earbuds", "headphones", "smartwatches"):
            conn = specs.get("connectivity", "Bluetooth")
            return (
                f"Yes, the {product.name} uses standard {conn}, so it works with iPhones and "
                f"iOS devices. No special app required for basic functionality."
            )

    if any(w in q_lower for w in ["android", "samsung", "oneplus"]):
        cat = product.category.lower()
        if cat in ("earbuds", "headphones", "smartwatches"):
            return (
                f"Absolutely! The {product.name} works with all Android devices via standard "
                f"Bluetooth pairing. Some features may require the companion app."
            )

    # Availability
    if any(w in q_lower for w in ["available", "stock", "buy", "where"]):
        return (
            f"The {product.name} is widely available on Amazon, Flipkart, and the official "
            f"{product.brand} website. Prices may vary slightly between platforms."
        )

    # Generic fallback
    return (
        f"That's a great question about the {product.name}! "
        f"I'd recommend checking the official {product.brand} product page or Amazon listing "
        f"for the most accurate and up-to-date information on that spec."
    )


# ─── Main Entrypoint ──────────────────────────────────────────────────────────

def ask_seller(product: ProductCard, question: str) -> SellerQA:
    """
    Answer a customer question about a product as a knowledgeable seller.
    Tries Gemini first, falls back to rule-based matching.
    Returns a saved SellerQA object.
    """
    # Try Gemini first
    answer = _ask_gemini_seller(product, question)

    # Fallback
    if not answer:
        answer = _rule_based_seller_answer(product, question)

    # Save and return
    qa = SellerQA.objects.create(
        product=product,
        question=question,
        answer=answer,
    )
    return qa
