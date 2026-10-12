import os
import streamlit as st
import pandas as pd
import plotly.express as px
from parser import parse_bank_file
from categorizer import categorize_transactions, generate_spending_insights

st.set_page_config(page_title="AI Finance & Spending Analyzer", layout="wide")

st.title("💳 AI Finance & Spending Analyzer")
st.caption("Universal bank statement analysis: CSV, Excel, PDF parsing, automated category tagging, budget tracking, and AI insights.")

# --- SIDEBAR: Upload & Processing ---
uploaded_file = st.sidebar.file_uploader(
    "Upload Bank Statement", 
    type=["csv", "xlsx", "xls", "pdf"]
)
user_api_key = st.sidebar.text_input(
    "Gemini API Key (Optional)", 
    type="password", 
    help="aistudio.google.com లో ఉచితంగా పొందవచ్చు. ఇవ్వకపోతే ఆఫ్లైన్ రూల్స్ పనిచేస్తాయి."
)

pdf_password = None
if uploaded_file is not None and uploaded_file.name.lower().endswith(".pdf"):
    pdf_password = st.sidebar.text_input("PDF Password (if locked)", type="password")

file_to_process = uploaded_file if uploaded_file is not None else "sample.csv"

if st.sidebar.button("Run Categorization"):
    with st.spinner("Processing statement and running AI categorization..."):
        if uploaded_file is not None:
            temp_path = f"temp_{uploaded_file.name}"
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            txns = parse_bank_file(temp_path, password=pdf_password)
            if os.path.exists(temp_path):
                os.remove(temp_path)
        else:
            txns = parse_bank_file(file_to_process)

        if txns:
            enriched_txns = categorize_transactions(
                txns, 
                api_key=user_api_key.strip() if user_api_key else None
            )
            data = [
                {
                    "Date": str(t.date),
                    "Amount": t.amount,
                    "Merchant": t.merchant or "Unknown",
                    "Category": t.category or "Other",
                    "Raw Description": t.raw_description,
                }
                for t in enriched_txns
            ]
            st.session_state["df"] = pd.DataFrame(data)
        else:
            st.sidebar.error("Could not extract valid transactions from this file.")

# --- MAIN DASHBOARD ---
if "df" in st.session_state:
    df = st.session_state["df"]

    # Key Metrics
    income = df[df["Amount"] > 0]["Amount"].sum()
    expenses = abs(df[df["Amount"] < 0]["Amount"].sum())
    net_savings = income - expenses

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Income", f"${income:,.2f}")
    col2.metric("Total Expenses", f"${expenses:,.2f}")
    col3.metric("Net Savings", f"${net_savings:,.2f}")

    st.markdown("---")

    # Visualizations
    expense_df = df[df["Amount"] < 0].copy()
    expense_df["Spend"] = abs(expense_df["Amount"])

    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.subheader("Expenses by Category")
        if not expense_df.empty:
            cat_fig = px.pie(
                expense_df,
                names="Category",
                values="Spend",
                hole=0.4,
                title="Spending Distribution"
            )
            st.plotly_chart(cat_fig, use_container_width=True)
        else:
            st.info("No expense transactions to display.")

    with chart_col2:
        st.subheader("Top Spending Merchants")
        if not expense_df.empty:
            merchant_agg = expense_df.groupby("Merchant")["Spend"].sum().reset_index()
            bar_fig = px.bar(
                merchant_agg.sort_values(by="Spend", ascending=False),
                x="Merchant",
                y="Spend",
                text_auto=".2f",
                title="Expenses by Merchant"
            )
            st.plotly_chart(bar_fig, use_container_width=True)

    st.markdown("---")

    # --- FEATURE 1: BUDGET CAPS & ALERTS ---
    st.subheader("🎯 Monthly Budget Tracking & Alerts")
    
    categories_present = sorted(expense_df["Category"].unique().tolist()) if not expense_df.empty else []
    
    default_budgets = {
        "Food & Dining": 200.0,
        "Shopping": 150.0,
        "Transportation": 100.0,
        "Groceries": 300.0,
        "Utilities": 150.0,
        "Entertainment": 100.0,
        "Other": 100.0
    }

    if categories_present:
        st.write("Set spending targets to check current budget utilization:")
        budget_cols = st.columns(min(len(categories_present), 4))
        
        category_spending = expense_df.groupby("Category")["Spend"].sum().to_dict()

        for idx, cat in enumerate(categories_present):
            target_col = budget_cols[idx % min(len(categories_present), 4)]
            current_spend = category_spending.get(cat, 0.0)
            default_val = default_budgets.get(cat, 200.0)
            
            with target_col:
                budget_cap = st.number_input(f"{cat} Budget ($)", min_value=1.0, value=default_val, step=10.0, key=f"budget_{cat}")
                ratio = min(current_spend / budget_cap, 1.0)
                
                if current_spend > budget_cap:
                    st.error(f"🚨 **{cat}**: Spent ${current_spend:.2f} /${budget_cap:.2f} (Over Budget!)")
                elif current_spend >= 0.8 * budget_cap:
                    st.warning(f"⚠️ **{cat}**: Spent ${current_spend:.2f} /${budget_cap:.2f} (Near Limit)")
                else:
                    st.success(f"✅ **{cat}**: Spent ${current_spend:.2f} /${budget_cap:.2f}")
                
                st.progress(ratio)
    else:
        st.info("No expense categories found to track budgets.")

    st.markdown("---")

    # --- FEATURE 2: EXPORT CATEGORIZED DATA ---
    st.subheader("📋 Normalized & Categorized Transactions")
    st.dataframe(df, use_container_width=True)

    csv_data = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Download Categorized Transactions (CSV)",
        data=csv_data,
        file_name="categorized_spending_report.csv",
        mime="text/csv"
    )

    st.markdown("---")

    # --- FEATURE 3: AI FINANCIAL ADVISOR ---
    st.subheader("🤖 AI Financial Advisor")
    records = df.to_dict(orient="records")

    current_key = user_api_key.strip() if user_api_key else None

    if st.button("Generate Comprehensive Spending Audit"):
        with st.spinner("AI is analyzing your finances..."):
            audit = generate_spending_insights(records, api_key=current_key)
            st.markdown(audit)

    query = st.chat_input("Ask a question about your spending (e.g., 'How can I save on dining?')")
    if query:
        st.chat_message("user").write(query)
        with st.spinner("Thinking..."):
            ans = generate_spending_insights(records, user_question=query, api_key=current_key)
            st.chat_message("assistant").markdown(ans)

else:
    st.info("Click **Run Categorization** in the left sidebar to start analyzing `sample.csv` or an uploaded statement.")