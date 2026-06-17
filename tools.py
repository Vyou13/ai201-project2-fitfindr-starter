"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


_MODEL = "llama-3.3-70b-versatile"


def _chat(prompt: str, *, temperature: float = 0.7) -> str:
    """Send a single user prompt to the Groq chat model and return the text."""
    client = _get_groq_client()
    response = client.chat.completions.create(
        model=_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    return response.choices[0].message.content.strip()


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    listings = load_listings()

    # Tokenize the search query into lowercase keywords.
    keywords = [w for w in description.lower().split() if w]

    scored: list[tuple[int, dict]] = []
    for item in listings:
        # Price filter (inclusive).
        if max_price is not None and item.get("price", 0) > max_price:
            continue

        # Size filter (case-insensitive substring match), skipped for None/"Any".
        if size and size.strip().lower() not in ("", "any"):
            item_size = str(item.get("size", "")).lower()
            if size.strip().lower() not in item_size:
                continue

        # Score by keyword overlap against title, description, and style tags.
        haystack = " ".join([
            str(item.get("title", "")),
            str(item.get("description", "")),
            " ".join(item.get("style_tags", [])),
            str(item.get("category", "")),
            " ".join(item.get("colors", [])),
            str(item.get("brand") or ""),
        ]).lower()

        score = sum(1 for kw in keywords if kw in haystack)
        if score > 0:
            scored.append((score, item))

    # Sort by relevance score, highest first (stable for ties).
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    def _fmt_item(it: dict) -> str:
        bits = [
            it.get("title") or it.get("name", "item"),
            f"category: {it.get('category', 'n/a')}",
            f"colors: {', '.join(it.get('colors', [])) or 'n/a'}",
            f"style: {', '.join(it.get('style_tags', [])) or 'n/a'}",
        ]
        return " | ".join(bits)

    item_desc = _fmt_item(new_item)
    items = (wardrobe or {}).get("items", [])

    if not items:
        prompt = (
            "You are a friendly personal stylist. A user is considering buying "
            f"this thrifted item:\n{item_desc}\n\n"
            "They haven't told you what's in their closet yet. Give general "
            "styling advice in 3-4 sentences: what kinds of pieces (universal "
            "staples like white tees, straight-leg denim, minimalist sneakers) "
            "pair well with it, what vibe it suits, and concrete styling notes."
        )
    else:
        wardrobe_lines = "\n".join(f"- {_fmt_item(it)}" for it in items)
        prompt = (
            "You are a friendly personal stylist. A user is considering buying "
            f"this thrifted item:\n{item_desc}\n\n"
            "Here is what they already own:\n"
            f"{wardrobe_lines}\n\n"
            "Suggest 1-2 complete outfits that pair the new item with specific, "
            "named pieces from their wardrobe. Be concrete about proportions, "
            "color interactions, and styling notes (e.g., 'cuff the hems', "
            "'tuck the front'). Keep it to 3-4 encouraging sentences."
        )

    return _chat(prompt, temperature=0.7)


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    if not outfit or not outfit.strip():
        return (
            "Error: Cannot generate a fit card caption without a valid "
            "outfit description."
        )

    name = new_item.get("title") or new_item.get("name", "this find")
    price = new_item.get("price")
    platform = new_item.get("platform", "the app")
    price_str = f"${price:.0f}" if isinstance(price, (int, float)) else str(price)

    prompt = (
        "Write a short, casual, authentic OOTD social caption (2-4 sentences) "
        "for a thrifted find. Sound like a real person posting on Instagram/"
        "TikTok, not a product listing. Mention the item name, its price, and "
        "the platform naturally, once each. Capture the outfit vibe in specific "
        "terms. A couple of emojis are welcome.\n\n"
        f"Item: {name}\n"
        f"Price: {price_str}\n"
        f"Platform: {platform}\n"
        f"Outfit: {outfit.strip()}\n\n"
        "Return only the caption."
    )

    return _chat(prompt, temperature=0.9)
