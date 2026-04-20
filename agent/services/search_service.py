"""
Search service — queries dummy catalog (always available) and
optionally SerpAPI Google Shopping (when SERPAPI_KEY is set).
"""
from __future__ import annotations
import re
import os
import json
import logging
import requests
from typing import Optional
from django.conf import settings

from agent.catalog import DUMMY_CATALOG

logger = logging.getLogger(__name__)


# ─── Keyword-based dummy catalog search ──────────────────────────────────────

def _score_product(product: dict, query: str, max_price: Optional[float],
                   category: Optional[str]) -> float:
    """Return a relevance score for a product given the query parameters."""
    query_tokens = set(re.split(r"[\s,]+", query.lower()))
    score = 0.0

    # Category filter — hard disqualification
    if category and product["category"] != category.lower():
        return 0.0

    # Price ceiling — hard disqualification
    if max_price is not None and float(product["price"]) > max_price:
        return 0.0

    # Keyword matches on name, brand, keywords list
    for kw in product.get("keywords", []):
        if kw in query.lower():
            score += 2.0

    for token in query_tokens:
        if token in product["name"].lower():
            score += 1.5
        if token in product["brand"].lower():
            score += 1.0
        if token in product.get("category", "").lower():
            score += 1.0
        # Partial spec value matches
        for val in product.get("specs", {}).values():
            if token in str(val).lower():
                score += 0.5

    # Rating bonus
    score += float(product.get("rating", 0)) * 0.3

    return score


def search_dummy_catalog(
    query: str,
    max_price: Optional[float] = None,
    category: Optional[str] = None,
    top_n: int = 10,
) -> list[dict]:
    """Search the local dummy catalog and return top_n scored products."""
    scored = []
    for product in DUMMY_CATALOG:
        s = _score_product(product, query, max_price, category)
        if s > 0:
            scored.append((s, product))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored[:top_n]]


# ─── SerpAPI Google Shopping search ──────────────────────────────────────────

def search_serpapi(
    query: str,
    max_price: Optional[float] = None,
    top_n: int = 10,
) -> list[dict]:
    """Query SerpAPI Google Shopping. Returns normalized product dicts."""
    api_key = getattr(settings, "SERPAPI_KEY", "") or os.getenv("SERPAPI_KEY", "")
    if not api_key:
        return []

    params = {
        "engine": "google_shopping",
        "q": query,
        "gl": "in",
        "hl": "en",
        "currency": "INR",
        "api_key": api_key,
        "num": 20,
    }
    if max_price:
        params["price_max"] = int(max_price)

    try:
        resp = requests.get("https://serpapi.com/search", params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.error("SerpAPI request failed: %s", exc)
        return []

    results = []
    for item in data.get("shopping_results", [])[:top_n]:
        price_str = str(item.get("price", "0")).replace("₹", "").replace(",", "").strip()
        try:
            price = float(price_str)
        except ValueError:
            price = 0.0

        if max_price and price > max_price:
            continue

        results.append({
            "id": None,              # will be assigned after DB save
            "external_id": item.get("product_id", ""),
            "name": item.get("title", "Unknown Product"),
            "brand": item.get("source", ""),
            "category": "",
            "price": price,
            "currency": "INR",
            "rating": float(item.get("rating", 0) or 0),
            "review_count": int(item.get("reviews", 0) or 0),
            "image_url": item.get("thumbnail", ""),
            "product_url": item.get("link", ""),
            "specs": {},
            "keywords": [],
            "source": "serpapi",
        })

    return results


# ─── Unified search entrypoint ────────────────────────────────────────────────

def search_products(
    query: str,
    max_price: Optional[float] = None,
    category: Optional[str] = None,
    top_n: int = 10,
) -> list[dict]:
    """
    Primary search function. Merges dummy catalog results with SerpAPI
    results (if key is available). Dummy catalog results are always included.
    """
    dummy_results = search_dummy_catalog(query, max_price, category, top_n)
    serp_results = search_serpapi(query, max_price, top_n) if not category else []

    # Deduplicate: prefer dummy over serp for same name
    seen_names = {r["name"].lower() for r in dummy_results}
    merged = list(dummy_results)
    for sr in serp_results:
        if sr["name"].lower() not in seen_names:
            merged.append(sr)
            seen_names.add(sr["name"].lower())

    return merged[:top_n]
