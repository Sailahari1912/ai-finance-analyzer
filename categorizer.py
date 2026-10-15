import json
import re
import time
from typing import List, Dict, Any, Optional

# Universal Multi-National Taxonomy (Global, Canadian, Indian)
CATEGORY_RULES = {
    "Food & Dining": [
        "swiggy", "zomato", "eatclub", "dominos", "mcdonald", "kfc", "chai point", "haldiram",
        "tim horton", "starbucks", "juice dudez", "craig's cookies", "uber eats", "doordash", 
        "restaurant", "cafe", "gelato", "pizza", "dining", "subway"
    ],
    "Groceries": [
        "blinkit", "zepto", "instamart", "bigbasket", "dmart", "reliance fresh",
        "loblaws", "metro", "no frills", "freshco", "sobeys", "superstore", 
        "walmart", "grocery", "longo's", "costco"
    ],
    "Shopping": [
        "flipkart", "myntra", "ajio", "nykaa", "meesho", "croma", "reliance digital",
        "amazon", "dollarama", "winners", "h&m", "zara", "retail", "best buy", "apple"
    ],
    "Transportation": [
        "ola", "uber", "rapido", "irctc", "makemytrip", "easemytrip", "redbus", "indigo", "fastag",
        "shell", "esso", "petro", "transit", "gas", "presto", "parking", "lyft"
    ],
    "Entertainment": [
        "bookmyshow", "hotstar", "zee5", "sonyliv", "jiocinema", "prime video",
        "ticketmaster", "cinema", "cineplex", "netflix", "spotify", "theatre", "concert", "event"
    ],
    "Utilities & Bills": [
        "jio", "airtel", "vi", "bescom", "tata power", "recharge", "electricity", "broadband",
        "hydro", "enbridge", "rogers", "bell", "fido", "telus", "internet", "water"
    ]
}

# Transfers, credit card payoffs, and self transactions that distort real spending
TRANSFER_KEYWORDS = [
    "payment received", "autopay", "bill payment", "credit card payment", 
    "mbna payment", "citi payment", "cred", "cheq", "cc payment", 
    "imps transfer", "neft transfer", "rtgs", "self transfer", "direct debit"
]

def clean_merchant_text(raw_text: str) -> str:
    """Cleans up raw bank codes, UPI prefixes, and terminal IDs."""
    text = str(raw_text).strip()
    
    # Clean UPI format (e.g. UPI/DR/12345/SWIGGY/ICICI)
    if "upi/" in text.lower():
        parts = text.split("/")
        for part in parts:
            p = part.strip()
            if len(p) > 2 and not p.isdigit() and p.upper() not in ["UPI", "DR", "CR", "PY"]:
                return p.title()
                
    # Clean leading digits or symbols
    cleaned = re.sub(r"^[0-9#\-_*]+\s*", "", text)
    return cleaned.strip()

def classify_transaction(description: str, raw_merchant: str, amount: float) -> tuple[str, str]:
    """Classifies transaction, isolating credit card payoffs and transfers."""
    cleaned_name = clean_merchant_text(raw_merchant or description)
    text_to_search = f"{cleaned_name} {description}".lower()

    # 1. Detect internal transfers / credit card payments
    if any(k in text_to_search for k in TRANSFER_KEYWORDS):
        return "Card Payment / Bank Transfer", "Transfer / Payment"

    # 2. Match known global merchants
    for category, keywords in CATEGORY_RULES.items():
        if any(kw in text_to_search for kw in keywords):
            display_name = cleaned_name.split()[0].title() if cleaned_name else "Merchant"
            return display_name, category

    # 3. Default fallback
    fallback_name = cleaned_name.title() if cleaned_name else "Other Merchant"
    return fallback_name, "Other"

def fallback_categorize(transactions: Any) -> List[Any]:
    """Categorizes all records using rules."""
    # Convert DataFrame to records if passed directly
    if hasattr(transactions, "to_dict"):
        transactions = transactions.to_dict(orient="records")

    categorized = []
    for t in transactions:
        is_dict = isinstance(t, dict)
        desc = t.get("raw_description", "") if is_dict else getattr(t, "raw_description", "")
        merch = t.get("merchant", "") if is_dict else getattr(t, "merchant", "")
        amt = float(t.get("amount", 0.0) if is_dict else getattr(t, "amount", 0.0))

        cleaned_merchant, assigned_cat = classify_transaction(desc, merch, amt)

        if is_dict:
            t["merchant"] = cleaned_merchant
            t["category"] = assigned_cat
            categorized.append(t)
        else:
            t.merchant = cleaned_merchant
            t.category = assigned_cat
            categorized.append(t)

    return categorized

# Alias for backwards compatibility with app.py imports
categorize_transactions = fallback_categorize

def generate_spending_insights(transactions: Any, user_question: Optional[str] = None, api_key: Optional[str] = None) -> str:
    """Generates financial insights with quota and 503 retry/fallback protection."""
    # Safe check that supports DataFrame, None, or empty list
    if transactions is None:
        return "No transactions available to analyze."
    if hasattr(transactions, "empty") and transactions.empty:
        return "No transactions available to analyze."
    if isinstance(transactions, list) and len(transactions) == 0:
        return "No transactions available to analyze."

    # Convert DataFrame to record dicts if needed
    if hasattr(transactions, "to_dict"):
        transactions = transactions.to_dict(orient="records")

    if not api_key:
        return "⚠️ Gemini API key is missing. Please provide an API key in the sidebar to use the AI Financial Advisor."

    # Prepare concise summary to avoid token limits
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

    candidate_models = [
        "gemini-3.8-flash",
        "gemini-3.8-flash-lite",
        "gemini-3.5-flash"
    ]

    # Attempt via modern google-genai SDK
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        for model_name in candidate_models:
            for attempt in range(2):
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt
                    )
                    if response and response.text:
                        return response.text
                except Exception as err:
                    err_str = str(err)
                    if "503" in err_str or "UNAVAILABLE" in err_str:
                        time.sleep(1.5)
                        continue
                    break
    except ImportError:
        pass
    except Exception:
        pass

    # Fallback attempt via google-generativeai SDK
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
                    err_str = str(err)
                    if "503" in err_str or "UNAVAILABLE" in err_str:
                        time.sleep(1.5)
                        continue
                    break
    except Exception as e:
        return f"Error communicating with Gemini: {str(e)}"

    return "⚠️ The Gemini API is temporarily experiencing high demand across all endpoints. Please wait 10 seconds and try again."
