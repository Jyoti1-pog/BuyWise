"""
Video Service — analyzes product videos using Gemini multimodal AI.

Supports:
  - YouTube URLs (passed directly to Gemini via file_uri)
  - Instagram Reel / TikTok URLs (downloaded via yt-dlp → Gemini Files API)
  - Uploaded video files (saved to MEDIA_ROOT → Gemini Files API)
  - Fallback: text-only analysis when no API key is configured

Flow:
  1. Detect source type from URL / file
  2. For YouTube: pass URL as FileData to Gemini
  3. For Instagram/TikTok: yt-dlp download → temp file → Gemini Files API
  4. For uploads: save file → Gemini Files API
  5. Parse JSON response → match catalog → return VideoAnalysis object
"""
from __future__ import annotations
import json
import logging
import os
import re
import tempfile
import time
from decimal import Decimal
from typing import Optional

from django.conf import settings

from agent.models import Session, VideoAnalysis, ProductCard
from agent.services.search_service import search_dummy_catalog

logger = logging.getLogger(__name__)

# ─── Video Analysis Prompt ───────────────────────────────────────────────────

VIDEO_ANALYSIS_PROMPT = """
Analyze this product video and extract information. Respond ONLY with valid JSON, no markdown:
{
  "product_name": "exact product name shown or mentioned",
  "brand": "brand name",
  "category": "one of: earbuds|headphones|laptops|smartphones|air_fryers|smartwatches|appliances|other",
  "specs": ["spec1", "spec2", "spec3"],
  "price_hint": "price mentioned in video like ₹3,990 or null if not mentioned",
  "video_type": "one of: review|unboxing|advertisement|tutorial|other",
  "confidence": "high if product is clear, medium if partially visible, low if unclear",
  "summary": "2-3 sentence description of what this video shows"
}

Rules:
- Extract the SPECIFIC product name (e.g. 'Sony WF-C500' not just 'headphones')
- Include key specs actually mentioned or shown (battery, weight, features, etc.)
- If multiple products shown, focus on the PRIMARY one being demonstrated
- If no product is identifiable, use confidence: 'low' and product_name: 'Unknown Product'
"""

# ─── URL Type Detection ──────────────────────────────────────────────────────

def detect_source_type(url: str) -> str:
    """Detect the type of video source from URL."""
    url_lower = url.lower()
    if "youtube.com" in url_lower or "youtu.be" in url_lower:
        return "youtube"
    if "instagram.com" in url_lower:
        return "instagram"
    if "tiktok.com" in url_lower:
        return "tiktok"
    if any(url_lower.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp"]):
        return "image"
    return "other"


def extract_youtube_thumbnail(url: str) -> str:
    """Extract YouTube video ID and return thumbnail URL."""
    patterns = [
        r"youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
        r"youtu\.be/([a-zA-Z0-9_-]{11})",
        r"youtube\.com/shorts/([a-zA-Z0-9_-]{11})",
        r"youtube\.com/embed/([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            vid_id = match.group(1)
            return f"https://img.youtube.com/vi/{vid_id}/hqdefault.jpg"
    return ""


# ─── Gemini Client ────────────────────────────────────────────────────────────

def _get_genai_client():
    """Get a google-genai client. Returns None if no API key."""
    api_key = getattr(settings, "GEMINI_API_KEY", "") or ""
    if not api_key:
        return None
    try:
        from google import genai
        return genai.Client(api_key=api_key)
    except Exception as exc:
        logger.error("Failed to init genai client: %s", exc)
        return None


# ─── YouTube Analysis ─────────────────────────────────────────────────────────

def analyze_youtube_url(client, url: str) -> dict:
    """Pass YouTube URL directly to Gemini — no download needed."""
    from google.genai import types

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[
            types.Part(
                file_data=types.FileData(
                    file_uri=url,
                    mime_type="video/mp4",
                )
            ),
            VIDEO_ANALYSIS_PROMPT,
        ],
    )
    return _parse_gemini_response(response.text)


# ─── Social Video Download (Instagram, TikTok) ───────────────────────────────

def download_social_video(url: str) -> Optional[str]:
    """
    Download a video from Instagram / TikTok using yt-dlp.
    Returns the path to the downloaded file, or None on failure.
    Saves to Django MEDIA_ROOT/videos/temp/.
    """
    import yt_dlp

    media_root = getattr(settings, "MEDIA_ROOT", None)
    if not media_root:
        return None

    output_dir = os.path.join(str(media_root), "videos", "temp")
    os.makedirs(output_dir, exist_ok=True)

    # Use a unique temp filename
    import uuid
    tmp_id = str(uuid.uuid4())[:8]
    out_template = os.path.join(output_dir, f"{tmp_id}.%(ext)s")

    ydl_opts = {
        "format": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]/best",
        "outtmpl": out_template,
        "quiet": True,
        "no_warnings": True,
        "max_filesize": "50M",
        "merge_output_format": "mp4",
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded = ydl.prepare_filename(info)

        # Ensure we got an mp4
        if not os.path.exists(downloaded):
            # Try .mp4 extension
            base = os.path.splitext(downloaded)[0]
            downloaded = base + ".mp4"

        return downloaded if os.path.exists(downloaded) else None
    except Exception as exc:
        logger.error("yt-dlp download failed for %s: %s", url, exc)
        return None


def analyze_via_files_api(client, file_path: str) -> dict:
    """Upload a video file to Gemini Files API and analyze it."""
    from google.genai import types

    with open(file_path, "rb") as f:
        uploaded = client.files.upload(
            file=f,
            config=types.UploadFileConfig(mime_type="video/mp4"),
        )

    # Wait for Gemini to process the file
    max_wait = 120  # seconds
    waited = 0
    while getattr(uploaded.state, "name", str(uploaded.state)) == "PROCESSING":
        time.sleep(3)
        waited += 3
        uploaded = client.files.get(name=uploaded.name)
        if waited >= max_wait:
            raise TimeoutError("Gemini file processing timed out")

    state_name = getattr(uploaded.state, "name", str(uploaded.state))
    if state_name == "FAILED":
        raise ValueError("Gemini file upload/processing failed")

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[
            types.Part(
                file_data=types.FileData(file_uri=uploaded.uri)
            ),
            VIDEO_ANALYSIS_PROMPT,
        ],
    )

    # Clean up file from Gemini (optional — free tier has limits)
    try:
        client.files.delete(name=uploaded.name)
    except Exception:
        pass

    return _parse_gemini_response(response.text)


# ─── Response Parser ──────────────────────────────────────────────────────────

def _parse_gemini_response(text: str) -> dict:
    """Parse Gemini's JSON response, stripping markdown fences if present."""
    text = text.strip()
    # Strip ```json ... ``` or ``` ... ```
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to extract JSON object from the text
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
        logger.error("Could not parse Gemini JSON: %s", text[:200])
        return {
            "product_name": "Unknown Product",
            "brand": "",
            "category": "other",
            "specs": [],
            "price_hint": None,
            "video_type": "other",
            "confidence": "low",
            "summary": "Could not extract product information from this video.",
        }


# ─── Fallback (no Gemini) ─────────────────────────────────────────────────────

def fallback_video_analysis(url: str = "", filename: str = "") -> dict:
    """
    Rule-based fallback when Gemini is not available.
    Does basic keyword matching on URL/filename.
    """
    text = (url + " " + filename).lower()

    cat_map = {
        "earbuds": "earbuds", "tws": "earbuds", "airdopes": "earbuds", "buds": "earbuds",
        "headphone": "headphones", "rockerz": "headphones",
        "laptop": "laptops", "notebook": "laptops",
        "phone": "smartphones", "smartphone": "smartphones", "mobile": "smartphones",
        "airfryer": "air_fryers", "air fryer": "air_fryers",
        "smartwatch": "smartwatches", "watch": "smartwatches",
    }

    detected_category = "other"
    for kw, cat in cat_map.items():
        if kw in text:
            detected_category = cat
            break

    return {
        "product_name": "Unknown Product",
        "brand": "",
        "category": detected_category,
        "specs": [],
        "price_hint": None,
        "video_type": "other",
        "confidence": "low",
        "summary": (
            "Video analysis requires a Gemini API key. "
            "Set GEMINI_API_KEY in your .env file for full video understanding."
        ),
    }


# ─── Catalog Matching ─────────────────────────────────────────────────────────

def match_to_catalog(extracted: dict, session: Session) -> Optional[ProductCard]:
    """Try to find a matching product in the catalog and save as ProductCard."""
    name = extracted.get("product_name", "")
    category = extracted.get("category", "")
    if not name or name == "Unknown Product":
        return None

    results = search_dummy_catalog(name, category=category if category != "other" else None, top_n=1)
    if not results:
        # Try just by category
        results = search_dummy_catalog(category, top_n=1)

    if not results:
        return None

    item = results[0]
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
        rank=1,
        source="dummy",
    )
    return card


# ─── Main Entrypoint ──────────────────────────────────────────────────────────

def analyze_video(
    session: Session,
    video_url: str = "",
    uploaded_file_path: str = "",
    uploaded_file_name: str = "",
) -> VideoAnalysis:
    """
    Main entry: analyze a video from URL or uploaded file.
    Returns a saved VideoAnalysis object.
    """
    client = _get_genai_client()
    source_type = "upload" if uploaded_file_path else detect_source_type(video_url)
    thumbnail_url = ""
    raw_response = ""
    extracted = {}

    try:
        if not client:
            # Fallback mode
            extracted = fallback_video_analysis(
                url=video_url, filename=uploaded_file_name
            )
        elif uploaded_file_path:
            # Uploaded file → Files API
            extracted = analyze_via_files_api(client, uploaded_file_path)
            raw_response = str(extracted)
        elif source_type == "youtube":
            # YouTube → direct URL
            thumbnail_url = extract_youtube_thumbnail(video_url)
            extracted = analyze_youtube_url(client, video_url)
            raw_response = str(extracted)
        elif source_type in ("instagram", "tiktok"):
            # Download first, then Files API
            logger.info("Downloading %s video: %s", source_type, video_url)
            local_path = download_social_video(video_url)
            if local_path:
                extracted = analyze_via_files_api(client, local_path)
                raw_response = str(extracted)
                # Clean up local file after upload
                try:
                    os.remove(local_path)
                except Exception:
                    pass
            else:
                extracted = fallback_video_analysis(url=video_url)
        else:
            extracted = fallback_video_analysis(url=video_url)

    except Exception as exc:
        logger.error("Video analysis failed: %s", exc, exc_info=True)
        extracted = fallback_video_analysis(url=video_url, filename=uploaded_file_name)

    # Try to match with catalog
    matched_product = match_to_catalog(extracted, session)

    # Save VideoAnalysis record
    analysis = VideoAnalysis.objects.create(
        session=session,
        video_url=video_url,
        video_source_type=source_type,
        thumbnail_url=thumbnail_url,
        extracted_product_name=extracted.get("product_name", ""),
        extracted_brand=extracted.get("brand", ""),
        extracted_category=extracted.get("category", ""),
        extracted_specs=extracted.get("specs", []),
        extracted_price_hint=str(extracted.get("price_hint") or ""),
        video_type=extracted.get("video_type", "other"),
        video_summary=extracted.get("summary", ""),
        confidence=extracted.get("confidence", "low"),
        raw_gemini_response=raw_response[:2000],
        matched_product=matched_product,
    )

    return analysis
