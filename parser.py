import os
import re
import pandas as pd
from datetime import datetime
from typing import List, Optional
from schemas import NormalizedTransaction

def clean_amount(val) -> float:
    if pd.isna(val) or val is None or str(val).strip() == "":
        return 0.0
    val_str = str(val).replace("$", "").replace("₹", "").replace("INR", "").replace(",", "").strip()
    match = re.match(r"\((.*?)\)", val_str)
    if match:
        val_str = f"-{match.group(1)}"
    try:
        return float(val_str)
    except ValueError:
        return 0.0

def clean_date(val):
    if pd.isna(val) or val is None:
        return datetime.today().date()
    val_str = str(val).split("T")[0].strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%m-%d-%Y", "%b %d, %Y", "%d %b %Y"):
        try:
            return datetime.strptime(val_str, fmt).date()
        except ValueError:
            pass
    try:
        parsed = pd.to_datetime(val_str, dayfirst=True, errors="coerce")
        if not pd.isna(parsed):
            return parsed.date()
    except Exception:
        pass
    return datetime.today().date()

def extract_from_df(df: pd.DataFrame) -> List[NormalizedTransaction]:
    df = df.dropna(how="all")
    col_map = {col: str(col).strip().lower() for col in df.columns}
    df = df.rename(columns=col_map)

    date_col = next((c for c in df.columns if any(k in c for k in ["date", "time", "posted", "txn date", "value date"])), None)
    desc_col = next((c for c in df.columns if any(k in c for k in ["desc", "narration", "particular", "merchant", "details", "memo", "remarks"])), None)
    
    amount_col = next((c for c in df.columns if any(k in c for k in ["amount", "total", "txn amt"])), None)
    debit_col = next((c for c in df.columns if any(k in c for k in ["debit", "withdrawal", "dr"])), None)
    credit_col = next((c for c in df.columns if any(k in c for k in ["credit", "deposit", "cr"])), None)

    if not date_col or not desc_col:
        if len(df.columns) >= 3:
            date_col, desc_col, amount_col = df.columns[0], df.columns[1], df.columns[2]
        else:
            return []

    records: List[NormalizedTransaction] = []
    for _, row in df.iterrows():
        try:
            raw_desc = str(row[desc_col]).strip()
            if not raw_desc or raw_desc.lower() == "nan":
                continue

            # Amount లేదా Debit/Credit లెక్కింపు
            if amount_col and not pd.isna(row[amount_col]):
                final_amt = clean_amount(row[amount_col])
            elif debit_col or credit_col:
                dr = clean_amount(row.get(debit_col, 0.0))
                cr = clean_amount(row.get(credit_col, 0.0))
                final_amt = -dr if dr > 0 else cr
            else:
                continue

            if final_amt == 0.0:
                continue

            records.append(NormalizedTransaction(
                date=clean_date(row[date_col]),
                raw_description=raw_desc,
                amount=final_amt
            ))
        except Exception:
            continue
    return records

def parse_pdf(file_path: str, password: Optional[str] = None) -> List[NormalizedTransaction]:
    import pdfplumber
    records: List[NormalizedTransaction] = []
    date_regex = re.compile(r"(\d{1,4}[/-]\d{1,2}[/-]\d{2,4})")
    amount_regex = re.compile(r"(-?[\$₹]?\d+[\.,]\d{2})")

    with pdfplumber.open(file_path, password=password or "") as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if len(table) > 1:
                    df = pd.DataFrame(table[1:], columns=table[0])
                    parsed = extract_from_df(df)
                    if parsed:
                        records.extend(parsed)
            if not records:
                text = page.extract_text()
                if text:
                    for line in text.split("\n"):
                        d_match = date_regex.search(line)
                        a_match = amount_regex.search(line)
                        if d_match and a_match:
                            d_str = d_match.group(1)
                            a_str = a_match.group(1)
                            desc = line.replace(d_str, "").replace(a_str, "").strip()
                            try:
                                amt = clean_amount(a_str)
                                if amt != 0.0:
                                    records.append(NormalizedTransaction(
                                        date=clean_date(d_str),
                                        raw_description=desc if desc else "Unknown Transaction",
                                        amount=amt
                                    ))
                            except Exception:
                                continue
    return records

def parse_bank_file(file_path: str, password: Optional[str] = None) -> List[NormalizedTransaction]:
    """Universal loader for CSV, Excel (.xlsx, .xls), and PDF statements."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".csv":
        try:
            df = pd.read_csv(file_path)
        except Exception:
            df = pd.read_csv(file_path, skiprows=1)
        return extract_from_df(df)
    elif ext in [".xlsx", ".xls"]:
        df = pd.read_excel(file_path)
        return extract_from_df(df)
    elif ext == ".pdf":
        return parse_pdf(file_path, password=password)
    else:
        df = pd.read_csv(file_path)
        return extract_from_df(df)