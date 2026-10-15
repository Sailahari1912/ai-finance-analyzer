import os
import tempfile
import streamlit as st
import pandas as pd
import plotly.express as px

import parser as stmt_parser

# Auto-detect parser function
if hasattr(stmt_parser, "parse_statement"):
    parse_statement = stmt_parser.parse_statement
elif hasattr(stmt_parser, "parse_file"):
    parse_statement = stmt_parser.parse_file
elif hasattr(stmt_parser, "parse_pdf"):
    parse_statement = stmt_parser.parse_pdf
elif hasattr(stmt_parser, "parse_transactions"):
    parse_statement = stmt_parser.parse_transactions
else:
    # Use any available parsing function
    _candidates = [
        getattr(stmt_parser, a)
        for a in dir(stmt_parser)
        if callable(getattr(stmt_parser, a)) and not a.startswith("_")
    ]
    parse_statement = _candidates[0] if _candidates else None

import categorizer as cat_module

# Auto-detect categorization function
categorize_transactions = getattr(cat_module, "categorize_transactions", None)
if not categorize_transactions:
    categorize_transactions = getattr(cat_module, "categorize_file", lambda x: x)

# Auto-detect insights function
generate_spending_insights = getattr(cat_module, "generate_spending_insights", None)
if not generate_spending_insights:
    generate_spending_insights = getattr(
        cat_module,
        "generate_spending_insight",
        lambda df, q, api_key=None: "Advisor ready."
    )

# Configure Streamlit Page
st.set_page_config(
    page_title="AI Finance & Spending Analyzer",
    page_icon="💳",
    layout="wide"
)

# Sidebar - Settings & Configuration
st.sidebar.header("Configuration")

# Currency Selection
currency_option = st.sidebar.selectbox(
    "Select Currency",
    options=["$ (CAD / USD)", "₹ (INR)"],
    index=0
)
currency_symbol = "$" if "$" in currency_option else "₹"

# File Uploader
uploaded_file = st.sidebar.file_uploader(
    "Upload Bank Statement (CSV, Excel, PDF)",
    type=["csv", "xlsx", "xls", "pdf"]
)

# Optional User Inputs
gemini_api_key = st.sidebar.text_input(
    "Gemini API Key (Optional)",
    type="password",
    help="Enter your Google Gemini API key to enable interactive AI advising."
)

pdf_password = st.sidebar.text_input(
    "PDF Password (if locked)",
    type="password",
    help="If your bank statement PDF is password-protected, enter it here."
)

# Process Button
if st.sidebar.button("Run Categorization"):
    with st.spinner("Processing statement..."):
        try:
            parsed_data = None
            if uploaded_file is not None:
                file_name = uploaded_file.name.lower()
                suffix = os.path.splitext(file_name)[1]

                # Direct CSV handling
                if suffix == ".csv":
                    try:
                        df_raw = pd.read_csv(uploaded_file)
                    except UnicodeDecodeError:
                        uploaded_file.seek(0)
                        df_raw = pd.read_csv(uploaded_file, encoding="latin1")
                    parsed_data = df_raw.to_dict(orient="records")

                # Direct Excel handling
                elif suffix in [".xlsx", ".xls"]:
                    df_raw = pd.read_excel(uploaded_file)
                    parsed_data = df_raw.to_dict(orient="records")

                # PDF handling via temp file and parser.py
                else:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                        tmp_file.write(uploaded_file.getvalue())
                        tmp_path = tmp_file.name

                    try:
                        if parse_statement:
                            parsed_data = parse_statement(
                                tmp_path,
                                password=pdf_password if pdf_password else None
                            )
                    finally:
                        if os.path.exists(tmp_path):
                            os.remove(tmp_path)
            else:
                # Load fallback sample statement
                if os.path.exists("sample.csv"):
                    df_raw = pd.read_csv("sample.csv")
                    parsed_data = df_raw.to_dict(orient="records")
                elif parse_statement:
                    parsed_data = parse_statement("sample.csv")

            if parsed_data:
                # Categorize and normalize transactions
                categorized_data = categorize_transactions(parsed_data)
                df = pd.DataFrame(categorized_data)

                # Ensure numeric amount
                if "amount" in df.columns:
                    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)

                st.session_state["categorized_df"] = df
                st.success("Statement processed and categorized successfully!")
            else:
                st.error("No valid transactions could be extracted from the file.")
        except Exception as e:
            st.error(f"Error parsing file: {e}")

# Header
st.title("💳 AI Finance & Spending Analyzer")
st.write("Universal bank statement analysis: CSV, Excel, PDF parsing, automated category tagging, budget tracking, and AI insights.")

# Display Dashboard
if "categorized_df" in st.session_state:
    df = st.session_state["categorized_df"]

    # Normalize column names to lowercase for consistency
    df.columns = [str(c).strip().lower() for c in df.columns]

    # Map possible amount column names
    amount_col = None
    for possible_name in ["amount", "debit", "transaction amount", "trans amount", "total"]:
        if possible_name in df.columns:
            amount_col = possible_name
            break

    if amount_col:
        df["amount"] = pd.to_numeric(df[amount_col], errors="coerce").fillna(0.0)
    else:
        # Fallback if no amount column found: create an empty amount column
        df["amount"] = 0.0

    # Filter out Transfers & Payments for spending charts
    if "category" in df.columns:
        expenses_df = df[
            (~df["category"].isin(["Transfers & Payments", "Income"])) &
            (df["amount"] > 0)
        ]
        income_df = df[
            (df["category"] == "Income") |
            (df["amount"] < 0)
        ]
    else:
        expenses_df = df[df["amount"] > 0]
        income_df = df[df["amount"] < 0]
    # Calculate Core Metrics
    total_expenses = expenses_df["amount"].sum()
    total_income = income_df["amount"].abs().sum() if not income_df.empty else 0.0
    net_savings = total_income - total_expenses

    # Metric Cards
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Income", f"{currency_symbol}{total_income:,.2f}")
    col2.metric("Total Expenses", f"{currency_symbol}{total_expenses:,.2f}")
    col3.metric("Net Savings", f"{currency_symbol}{net_savings:,.2f}")

    st.write("---")

    # Visual Charts
    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.subheader("Spending by Category")
        if not expenses_df.empty and "category" in expenses_df.columns:
            cat_summary = expenses_df.groupby("category")["amount"].sum().reset_index()
            fig_pie = px.pie(
                cat_summary,
                values="amount",
                names="category",
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig_pie.update_traces(textposition="inside", textinfo="percent+label")
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No expense transactions to display in category chart.")

    with col_chart2:
        st.subheader("Top Spending Merchants")
        if not expenses_df.empty and "merchant" in expenses_df.columns:
            merchant_summary = (
                expenses_df.groupby("merchant")["amount"]
                .sum()
                .reset_index()
                .sort_values(by="amount", ascending=True)
                .tail(5)
            )
            fig_bar = px.bar(
                merchant_summary,
                x="amount",
                y="merchant",
                orientation="h",
                labels={"amount": f"Amount ({currency_symbol})", "merchant": "Merchant"},
                color_discrete_sequence=["#1f77b4"]
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("No merchant spending data available.")

    st.write("---")

    # Transaction Table
    st.subheader("📋 Normalized & Categorized Transactions")
    display_cols = [c for c in ["date", "merchant", "category", "amount", "raw_description"] if c in df.columns]
    st.dataframe(df[display_cols] if display_cols else df, use_container_width=True)

    # Download Button
    csv_export = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download Categorized Transactions (CSV)",
        data=csv_export,
        file_name="categorized_transactions.csv",
        mime="text/csv"
    )

    st.write("---")

    # AI Financial Advisor Section
    st.subheader("💬 AI Financial Advisor")
    user_q = st.text_input(
        "Ask a question about your spending (e.g., 'How much did I spend on dining out?'):"
    )

    if st.button("Generate AI Spending Insights") or user_q:
        if not gemini_api_key:
            st.warning("⚠️ Gemini API key is missing. Please provide an API key in the sidebar to use the AI Financial Advisor.")
        else:
            with st.spinner("Analyzing spending habits with Gemini AI..."):
                insights = generate_spending_insights(
                    df,
                    user_q if user_q else "Provide a detailed spending analysis and budget optimization recommendations.",
                    api_key=gemini_api_key
                )
                st.markdown(insights)
