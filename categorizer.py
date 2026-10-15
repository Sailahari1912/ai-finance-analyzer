import json
import re
import time
from typing import List, Dict, Any, Optional

# Universal Multi-National Taxonomy (Global, US, Canada, India, UK)
CATEGORY_RULES = {
    "Food & Dining": [
        "swiggy", "zomato", "eatclub", "dominos", "mcdonald", "kfc", "chai point", "haldiram",
        "tim horton", "starbucks", "juice dudez", "craig's cookies", "uber eats", "doordash", 
        "restaurant", "cafe", "gelato", "pizza", "dining", "subway", "burger king", "wendy",
        "chipotle", "bar", "bakery", "bistro", "pub", "coffee", "dunkin", "tacobell", "grubhub"
    ],
    "Groceries": [
        "blinkit", "zepto", "instamart", "bigbasket", "dmart", "reliance fresh",
        "loblaws", "metro", "no frills", "freshco", "sobeys", "superstore", 
        "walmart", "grocery", "longo", "costco", "trader joe", "safeway", "whole foods",
        "supermarket", "spencer", "kirana", "mart", "farm boy", "foodland"
    ],
    "Shopping": [
        "flipkart", "myntra", "ajio", "nykaa", "meesho", "croma", "reliance digital",
        "amazon", "amzn", "dollarama", "winners", "h&m", "zara", "retail", "best buy", "apple",
        "ikea", "marshalls", "target", "clothing", "apparel", "shoes", "mall", "eaton centre",
        "uniqlo", "sephora", "gap", "old navy"
    ],
    "Entertainment": [
        "bookmyshow", "hotstar", "zee5", "sonyliv", "jiocinema", "prime video",
        "ticketmaster", "cinema", "cineplex", "netflix", "spotify", "theatre", "concert", "event",
        "disney", "stubhub", "hulu", "paramount", "youtube", "playstation", "xbox", "steam",
        "membership fee"
    ],
    "Transportation": [
        "ola", "uber", "rapido", "irctc", "makemytrip", "easemytrip", "redbus", "indigo", "fastag",
        "shell", "esso", "petro", "transit", "gas", "presto", "parking", "lyft", "ttc", "metro",
        "fuel", "air canada", "delta", "united", "airline", "train", "cab", "taxi"
    ],
    "Utilities & Bills": [
        "jio", "airtel", "vi", "bescom", "tata power", "recharge", "electricity", "broadband",
        "hydro", "enbridge", "rogers", "bell", "fido", "telus", "internet", "water", "bill payment",
        "utility", "gas bill"
    ],
    "Health & Wellness": [
        "pharmacy", "shoppers drug mart", "rexall", "apollo", "1mg", "medplus", "hospital",
        "clinic", "dental", "doctor", "gym", "fitness", "goodlife", "cult.fit"
    ]
}

# Transfers, payoffs, and self-movements
TRANSFER_KEYWORDS = [
    "payment received", "autopay", "bill payment", "credit card payment", 
    "mbna payment", "citi payment", "cred", "cheq", "cc payment", 
    "imps transfer", "neft transfer", "rtgs", "self transfer", "direct debit", "ach deposit",
    "wire transfer", "e-transfer", "interac e-transfer"
]

def clean_universal_merchant(raw_text: str) -> str:
    """Cleans raw banking terminal clutter, codes, and location suffixes."""
    text = str(raw_text).strip()
    if not text or text.lower() in ["nan", "none"]:
        return "General Merchant"

    # 1. Clean UPI strings (e.g. UPI/DR/12345/SWIGGY/ICICI)
    if "upi/" in text.lower():
        parts = text.split("/")
        for part in parts:
            p = part.strip()
            if len(p) > 2 and not p.isdigit() and p.upper() not in ["UPI", "DR", "CR", "PY"]:
                return p.title()

    # 2. Remove common bank operational prefixes
    text = re.sub(r"^(pos\s+|dbt\s+|crd\s+|txn\s+|purchase\s+|debit\s+|credit\s+)", "", text, flags=re.IGNORECASE)

    # 3. Remove leading digits, dates, or symbols
    text = re.sub(r"^[0-9#\-_*]+\s*", "", text)

    # 4. Remove bank location tags and store metadata
    city_filters = [
        r"\bTORONTO\b", r"\bVANCOUVER\b", r"\bMONTREAL\b", r"\bBURBANK\b", 
        r"\bMUMBAI\b", r"\bDELHI\b", r"\bBANGALORE\b", r"\bHYDERABAD\b", r"\bCHENNAI\b",
        r"\bNEW YORK\b", r"\bCALGARY\b", r"\bOTTAWA\b", r"\bWALMART_CA\b", r"\bAMAZON\.CA\b"
    ]
    for city in city_filters:
        text = re.sub(city, "", text, flags=re.IGNORECASE)

    # 5. Remove store numbers (#1201), reference IDs (*5O0U72), and phone numbers
    text = re.sub(r"#\d+", "", text)
    text = re.sub(r"\*\S+", "", text)
    text = re.sub(r"\d{3}-\d{3}-\d{4}", "", text)
    text = re.sub(r"\s+", " ", text).strip(" -*#/")

    return text.title() if text else "General Merchant"

def classify_transaction(description: str, raw_merchant: str, amount: float) -> tuple[str, str]:
    """Universal classifier: maps any bank description to category and clean merchant."""
    cleaned_name = clean_universal_merchant(raw_merchant or description)
    search_text = f"{cleaned_name} {description}".lower()

    # Detect internal account transfers / credit card bill payments
    if any(k in search_text for k in TRANSFER_KEYWORDS):
        return "Bank Transfer / Card Payment", "Transfers & Payments"

    # Match categorized domains
    for category, keywords in CATEGORY_RULES.items():
        if any(kw in search_text for kw in keywords):
            return cleaned_name, category

    # If uncategorized, keep the actual merchant name rather than generic 'Other'
    return cleaned_name, "General & Other"

def fallback_categorize(transactions: Any) -> List[Any]:
    """Universal pipeline supporting any world bank statement schema."""
    if hasattr(transactions, "to_dict"):
        transactions = transactions.to_dict(orient="records")

    categorized = []
    for t in transactions:
        is_dict = isinstance(t, dict)

        # Universal lookup across possible column names from any bank
        if is_dict:
            # Flexible Description lookup
            desc = ""
            for key in ["description", "Description", "raw_description", "particulars", "Particulars", 
                        "narration", "Narration", "transaction details", "details", "Details", "memo", "Memo"]:
                if key in t and str(t[key]).strip():
                    desc = str(t[key]).strip()
                    break

            # Flexible Amount lookup (handles Amount, Debit, Withdrawal, Total)
            amt_val = 0.0
            for key in ["amount", "Amount", "debit", "Debit", "withdrawal", "Withdrawal", "total", "Total"]:
                if key in t and t[key] is not None and str(t[key]).strip() != "":
                    try:
                        clean_num = str(t[key]).replace("$", "").replace("₹", "").replace(",", "").strip()
                        amt_val = float(clean_num)
                        break
                    except (ValueError, TypeError):
                        continue
        else:
            desc = str(getattr(t, "description", getattr(t, "raw_description", "")))
            amt_val = float(getattr(t, "amount", 0.0))

        cleaned_merchant, assigned_cat = classify_transaction(desc, desc, amt_val)

        record = dict(t) if is_dict else vars(t).copy()
        record["merchant"] = cleaned_merchant
        record["category"] = assigned_cat
        record["amount"] = amt_val
        record["raw_description"] = desc
        categorized.append(record)

    return categorized

# Alias for backwards compatibility
categorize_transactions = fallback_categorize

def generate_spending_insights(transactions: Any, user_question: Optional[str] = None, api_key: Optional[str] = None) -> str:
    """Generates financial insights with quota and 503 retry protection."""
    if transactions is None:
        return "No transactions available to analyze."
    if hasattr(transactions, "empty") and transactions.empty:
        return "No transactions available to analyze."
    if isinstance(transactions, list) and len(transactions) == 0:
        return "No transactions available to analyze."

    if hasattr(transactions, "to_dict"):
        transactions = transactions.to_dict(orient="records")

    if not api_key:
        return "⚠️ Gemini API key is missing. Please provide an API key in the sidebar."

    summary = []
    for t in transactions[:35]:
        is_dict = isinstance(t, dict)
        m = t.get("merchant") if is_dict else getattr(t, "merchant", "")
        c = t.get("category") if is_dict else getattr(t, "category", "")
        a = t.get("amount") if is_dict else getattr(t, "amount", 0.0)
        summary.append(f"{m} ({c}): {a}")

    prompt = f"""
    Act as a professional financial advisor. Analyze this spending data:
    {json.dumps(summary)}

    User Question: {user_question if user_question else "Provide an executive summary of my spending habits and suggestions to save."}
    Keep the response clear, structured, and under 150 words.
    """

    candidate_models = ["gemini-3.8-flash", "gemini-3.8-flash-lite", "gemini-3.5-flash"]

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        for model_name in candidate_models:
            for attempt in range(2):
                try:
                    response = client.models.generate_content(model=model_name, contents=prompt)
                    if response and response.text:
                        return response.text
                except Exception as err:
                    if "503" in str(err) or "UNAVAILABLE" in str(err):
                        time.sleep(1.5)
                        continue
                    break
    except Exception:
        pass

    try:
        import google.generativeai as legacy_genai
        legacy_genai.configure(api_key=api_key)
        for model_name in candidate_models:
            for attempt in range(2):
                try:
                    model = legacy_genai.GenerativeModel(model_name)
                    response = model.generate_content(prompt)
                    if response and response.text:
                        return response.text
                except Exception as err:
                    if "503" in str(err) or "UNAVAILABLE" in str(err):
                        time.sleep(1.5)
                        continue
                    break
    except Exception as e:
        return f"Error communicating with Gemini: {str(e)}"

    return "⚠️ The Gemini API is temporarily busy. Please wait 10 seconds and try again."
