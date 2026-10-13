import streamlit as st
import pandas as pd
import plotly.express as px
from parser import parse_bank_file
from categorizer import fallback_categorize, generate_spending_insights

st.set_page_config(page_title="AI Finance & Spending Analyzer", layout="wide")

# Sidebar - Settings & Uploads
st.sidebar.title("Configuration")
currency_option = st.sidebar.selectbox("Select Currency", ["$ (CAD / USD)", "₹ (INR)"], index=0)
currency_symbol = "₹" if "₹" in currency_option else "$"

uploaded_file = st.sidebar.file_uploader("Upload Bank Statement (CSV, Excel, PDF)", type=["csv", "xlsx", "xls", "pdf"])
gemini_api_key = st.sidebar.text_input("Gemini API Key (Optional)", type="password")
pdf_password = st.sidebar.text_input("PDF Password (if locked)", type="password")

run_btn = st.sidebar.button("Run Categorization")

st.title("💳 AI Finance & Spending Analyzer")
st.write("Universal bank statement analysis: CSV, Excel, PDF parsing, automated category tagging, budget tracking, and AI insights.")

if "transactions_df" not in st.session_state:
    st.session_state.transactions_df = None

# Process Statement
if run_btn:
    with st.spinner("Processing statement..."):
        try:
            if uploaded_file is not None:
                parsed_data = parse_bank_file(uploaded_file, password=pdf_password if pdf_password else None)
            else:
                # Load fallback sample
                parsed_data = parse_bank_file("sample.csv")

            if parsed_data:
                # Categorize using the updated universal categorizer
                categorized_data = fallback_categorize(parsed_data)
                df = pd.DataFrame(categorized_data)
                
                # Ensure correct types
                if "amount" in df.columns:
                    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
                    
                st.session_state.transactions_df = df
            else:
                st.error("Could not extract valid transactions from this file.")
        except Exception as e:
            st.error(f"Error parsing file: {str(e)}")

# Display Dashboard
if st.session_state.transactions_df is not None:
    df = st.session_state.transactions_df

    # Filter out Transfers and Payments so genuine spending metrics are accurate
    expense_df = df[
        (df["category"] != "Transfer / Payment") & 
        (df["category"] != "Income")
    ].copy()

    # Calculate Core Metrics
    total_income = df[df["category"] == "Income"]["amount"].sum()
    total_expenses = expense_df["amount"].sum()
    net_savings = total_income - total_expenses

    # Metric Cards
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Income", f"{currency_symbol}{total_income:,.2f}")
    col2.metric("Total Expenses", f"{currency_symbol}{total_expenses:,.2f}")
    col3.metric("Net Savings", f"{currency_symbol}{net_savings:,.2f}")

    st.markdown("---")

    # Visualizations Row
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.subheader("Expenses by Category")
        if not expense_df.empty:
            cat_summary = expense_df.groupby("category")["amount"].sum().reset_index()
            fig_pie = px.pie(
                cat_summary, 
                values="amount", 
                names="category", 
                hole=0.45,
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No expense transactions to display in chart.")

    with chart_col2:
        st.subheader("Top Spending Merchants")
        if not expense_df.empty:
            merchant_summary = (
                expense_df.groupby("merchant")["amount"]
                .sum()
                .sort_values(ascending=False)
                .head(5)
                .reset_index()
            )
            fig_bar = px.bar(
                merchant_summary, 
                x="merchant", 
                y="amount", 
                labels={"amount": f"Spend ({currency_symbol})", "merchant": "Merchant"},
                color="amount",
                color_continuous_scale="Tealgrn"
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("No merchant spending data available.")

    st.markdown("---")

    # Transaction Table
    st.subheader("📑 Normalized & Categorized Transactions")
    display_cols = [c for c in ["date", "amount", "merchant", "category", "raw_description"] if c in df.columns]
    st.dataframe(df[display_cols], use_container_width=True)

    # Download CSV
    csv_data = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Categorized Transactions (CSV)",
        data=csv_data,
        file_name="categorized_transactions.csv",
        mime="text/csv"
    )

    st.markdown("---")

    # AI Financial Advisor Section
    st.subheader("🤖 AI Financial Advisor")
    user_q = st.text_input("Ask a question about your spending (e.g., 'How can I save on dining?')")
    
    if st.button("Generate Comprehensive Spending Audit"):
        with st.spinner("AI analyzing your expenses..."):
            advice = generate_spending_insights(
                transactions=df.to_dict(orient="records"),
                user_question=user_q if user_q else None,
                api_key=gemini_api_key if gemini_api_key else None
            )
            st.markdown(advice)
