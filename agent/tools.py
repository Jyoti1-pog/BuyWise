"""
Gemini tool/function schemas for the BuyWise shopping agent.
These are passed to google.generativeai as FunctionDeclaration objects.
"""
import google.generativeai as genai

# ─── Tool: Search Products ───────────────────────────────────────────────────
search_products_schema = genai.protos.FunctionDeclaration(
    name="search_products",
    description=(
        "Search for products matching a user's query. "
        "Returns up to 10 product candidates with name, price, specs and ratings."
    ),
    parameters=genai.protos.Schema(
        type=genai.protos.Type.OBJECT,
        properties={
            "query": genai.protos.Schema(
                type=genai.protos.Type.STRING,
                description="Refined product search query (e.g. 'wireless earbuds under 5000')",
            ),
            "max_price": genai.protos.Schema(
                type=genai.protos.Type.NUMBER,
                description="Maximum price in INR, if user specified a budget",
            ),
            "category": genai.protos.Schema(
                type=genai.protos.Type.STRING,
                description=(
                    "Product category. One of: earbuds, headphones, laptops, "
                    "smartphones, air_fryers, smartwatches, appliances"
                ),
            ),
        },
        required=["query"],
    ),
)

# ─── Tool: Rank and Analyse ───────────────────────────────────────────────────
rank_and_analyze_schema = genai.protos.FunctionDeclaration(
    name="rank_and_analyze",
    description=(
        "Given a list of product IDs from the current session, rank them "
        "and generate pros, cons, and a verdict for each based on the user's priorities."
    ),
    parameters=genai.protos.Schema(
        type=genai.protos.Type.OBJECT,
        properties={
            "product_ids": genai.protos.Schema(
                type=genai.protos.Type.ARRAY,
                items=genai.protos.Schema(type=genai.protos.Type.INTEGER),
                description="List of ProductCard IDs to rank",
            ),
            "user_priority": genai.protos.Schema(
                type=genai.protos.Type.STRING,
                description=(
                    "What matters most to the user, e.g. 'price', 'battery life', "
                    "'performance', 'brand reliability', 'portability'"
                ),
            ),
        },
        required=["product_ids"],
    ),
)

# ─── Tool: Compare Two Products ───────────────────────────────────────────────
compare_products_schema = genai.protos.FunctionDeclaration(
    name="compare_products",
    description="Generate a side-by-side comparison of exactly two products.",
    parameters=genai.protos.Schema(
        type=genai.protos.Type.OBJECT,
        properties={
            "product_id_a": genai.protos.Schema(
                type=genai.protos.Type.INTEGER,
                description="ID of the first product",
            ),
            "product_id_b": genai.protos.Schema(
                type=genai.protos.Type.INTEGER,
                description="ID of the second product",
            ),
        },
        required=["product_id_a", "product_id_b"],
    ),
)

# ─── Tool: Place Order ────────────────────────────────────────────────────────
place_order_schema = genai.protos.FunctionDeclaration(
    name="place_order",
    description=(
        "Place a MOCK order for the selected product. "
        "ONLY call this tool after the user has given explicit confirmation "
        "with phrases like 'buy this', 'go ahead', 'place order', 'yes, order it'."
    ),
    parameters=genai.protos.Schema(
        type=genai.protos.Type.OBJECT,
        properties={
            "product_id": genai.protos.Schema(
                type=genai.protos.Type.INTEGER,
                description="ID of the ProductCard to purchase",
            ),
            "session_id": genai.protos.Schema(
                type=genai.protos.Type.STRING,
                description="The current chat session UUID",
            ),
        },
        required=["product_id", "session_id"],
    ),
)

# ─── Exported Tool Set ────────────────────────────────────────────────────────
BUYWISE_TOOLS = genai.protos.Tool(
    function_declarations=[
        search_products_schema,
        rank_and_analyze_schema,
        compare_products_schema,
        place_order_schema,
    ]
)
