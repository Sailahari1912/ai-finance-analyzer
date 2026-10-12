import os
import re
import pandas as pd
from datetime import datetime
from typing import List
from schemas import NormalizedTransaction

def clean_amount(val) -> float:
    if pd.isna(val):
        return 0.0
    val_str = str(val).replace("$", "").replace(",", "").strip()
    match = re.match(r"\((.*?)\)", val_str)
    if match:
        return -float(match.group(1))
    return float(val_str)

def clean_date(val):
    if pd.isna(val):
        return datetime.today().date()
    val_str = str(val).split("T")[0].strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%m-%d-%Y", "%d-%m-%Y", "%b %d, %Y"):
        try:
            return datetime.strptime(val_str, fmt).date()
        except ValueError:
            pass
    return datetime.today().date()

def extract_from_df(df: pd.DataFrame) -> List[NormalizedTransaction]:
    col_map = {col: str(col).strip().lower() for col in df.columns}
    df = df.rename(columns=col_map)

    date_col = next((c for c in df.columns if any(k in c for k in ["date", "time", "posted"])), None)
    amount_col = next((c for c in df.columns if any(k in c for k in ["amount", "total", "debit", "price"])), None)
    desc_col = next((c for c in df.columns if any(k in c for k in ["desc", "merchant", "name", "memo", "details"])), None)

    if not date_col or not amount_col or not desc_col:
        if len(df.columns) >= 3:
            date_col, desc_col, amount_col = df.columns[0], df.columns[1], df.columns[2]
        else:
            return []

    records: List[NormalizedTransaction] = []
    for _, row in df.iterrows():
        try:
            records.append(NormalizedTransaction(
                date=clean_date(row[date_col]),
                raw_description=str(row[desc_col]),
                amount=clean_amount(row[amount_col])
            ))
        except Exception:
            continue
    return records

def parse_pdf(file_path: str) -> List[NormalizedTransaction]:
    import pdfplumber
    records: List[NormalizedTransaction] = []
    date_regex = re.compile(r"(\d{1,4}[/-]\d{1,2}[/-]\d{2,4})")
    amount_regex = re.compile(r"(-?\$?\d+[\.,]\d{2})")

    with pdfplumber.open(file_path) as pdf:
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
                                records.append(NormalizedTransaction(
                                    date=clean_date(d_str),
                                    raw_description=desc if desc else "Unknown Transaction",
                                    amount=clean_amount(a_str)
                                ))
                            except Exception:
                                continue
    return records

def parse_bank_file(file_path: str) -> List[NormalizedTransaction]:
    """Universal loader for CSV, Excel (.xlsx, .xls), and PDF statements."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".csv":
        df = pd.read_csv(file_path)
        return extract_from_df(df)
    elif ext in [".xlsx", ".xls"]:
        df = pd.read_excel(file_path)
        return extract_from_df(df)
    elif ext == ".pdf":
        return parse_pdf(file_path)
    else:
        df = pd.read_csv(file_path)
        return extract_from_df(df)