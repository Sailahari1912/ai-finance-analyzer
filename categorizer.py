import os
import json
import re
import time
from typing import List, Optional
from dotenv import load_dotenv
from google import genai
from schemas import NormalizedTransaction

load_dotenv()

def get_gemini_client(custom_key: Optional[str] = None):
    key = custom_key or os.getenv("GEMINI_API_KEY")
    if not key:
        return None
    try:
        return genai.Client(api_key=key)
    except Exception:
        return None

# Fallback keyword rules when API key is missing or quota limits trigger
KEYWORD_RULES = [
    (r"starbucks|coffee|dunkin|mcdonald|chipotle|cafe|subway", "Starbucks", "Food & Dining"),
    (r"amazon|amzn|walmart|target|ebay|flipkart|myntra", "Amazon", "Shopping"),
    (r"shell|exxon|bp|chevron|gas|fuel|uber|lyft|ola|petrol", "Shell", "Transportation"),
    (r"payroll|salary|direct dep|deposit|credit", "Payroll", "Income"),
    (r"kroger|safeway|trader joe|whole foods|costco|grocer|dmart|blinkit|zepto|instamart", "Groceries", "Groceries"),
    (r"netflix|spotify|hulu|disney|apple|prime", "Subscription", "Entertainment"),
    (r"electric|water|gas bill|internet|comcast|verizon|at&t|airtel|jio|electricity", "Utility Co", "Utilities"),
]

def fallback_categorize(transactions: List[NormalizedTransaction]) -> List[NormalizedTransaction]:
    """Local fallback categorizer if API quota limit is reached or no key provided."""
    for txn in transactions:
        desc_lower = txn.raw_description.lower()
        matched = False
        for pattern, clean_m, cat in KEYWORD_RULES:
            if re.search(pattern, desc_lower):
                txn.merchant = clean_m
                txn.category = cat
                matched = True
                break
        if not matched:
            txn.merchant = txn.raw_description[:20].strip()
            txn.category = "Income" if txn.amount > 0 else "Other"
    return transactions

def clean_json_text(text: str) -> str:
    """Extract raw JSON substring from the response."""
    text = text.strip()
    match = re.search(r"\[\s*\{.*?\}\s*\]", text, re.DOTALL)
    if match:
        return match.group(0)
    return text

def categorize_transactions(transactions: List[NormalizedTransaction], api_key: Optional[str] = None) -> List[NormalizedTransaction]:
    """Classifies transactions with Gemini, including rate-limit backoff and offline fallback."""
    if not transactions:
        return []

    client = get_gemini_client(api_key)
    if not client:
        return fallback_categorize(transactions)

    payload = [
        {"index": idx, "description": txn.raw_description, "amount": txn.amount}
        for idx, txn in enumerate(transactions)
    ]

    prompt = (
        "Clean the merchant name and assign an accurate spending category for each transaction.\n"
        "Categories must be one of: Food & Dining, Groceries, Shopping, Transportation, Utilities, Income, Entertainment, Other.\n"
        "Return ONLY a raw JSON array of objects without any markdown ticks or explanations.\n"
        'Example format: [{"index": 0, "clean_merchant": "Starbucks", "category": "Food & Dining"}]\n\n'
        f"Transactions to process:\n{json.dumps(payload)}"
    )

    # Attempt with retry backoff
    for attempt in range(3):
        try:
            interaction = client.interactions.create(
                model="gemini-3.8-flash",
                input=prompt
            )
            raw_text = clean_json_text(interaction.output_text)
            items = json.loads(raw_text)
            result_map = {item["index"]: item for item in items}

            for idx, txn in enumerate(transactions):
                if idx in result_map:
                    txn.merchant = result_map[idx].get("clean_merchant")
                    txn.category = result_map[idx].get("category")
            return transactions
        except Exception as e:
            if "too_many_requests" in str(e).lower() or "quota" in str(e).lower():
                time.sleep(3 * (attempt + 1))
            else:
                break

    # If API attempts fail, fall back locally
    return fallback_categorize(transactions)

def generate_spending_insights(transactions, user_question: str = None