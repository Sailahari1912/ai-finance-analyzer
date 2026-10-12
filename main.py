from parser import parse_bank_csv
from categorizer import categorize_transactions

def run():
    print("Parsing sample.csv...")
    raw_txns = parse_bank_csv("sample.csv")
    print(f"Extracted {len(raw_txns)} records. Sending to AI for categorization...")

    enriched_txns = categorize_transactions(raw_txns)

    print("\nCategorized Results:")
    print("-" * 65)
    for t in enriched_txns:
        print(f"{t.date} | {t.amount:>8.2f} | {t.merchant:<15} | {t.category}")
    print("-" * 65)

if __name__ == "__main__":
    run()