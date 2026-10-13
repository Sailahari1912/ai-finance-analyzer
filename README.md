# 💳 AI Finance & Spending Analyzer

An intelligent personal finance and spending analyzer powered by **Streamlit**, **Pandas**, **Plotly**, and **Google Gemini GenAI**. Supports universal bank statement parsing (CSV, Excel, and password-protected PDFs), automated merchant normalization, multi-currency reporting, category tracking, budget alerts, and an interactive AI financial advisor.

---

## 🌟 Key Features

* **Universal Multi-Format Ingestion:** Seamlessly parses statement data from `.csv`, `.xlsx`, `.xls`, and password-encrypted `.pdf` files.
* **Global & Multi-National Taxonomy:** Pre-configured rule sets and zero-shot fallback recognition for Canadian (TD, RBC, Scotiabank, BMO), Indian (SBI, HDFC, ICICI, UPI/PhonePe/GPay/Paytm), and worldwide bank formats.
* **Smart Transfer Isolation:** Automatically identifies credit card bill payoffs, self-transfers, and internal movements (e.g., `PAYMENT RECEIVED`, `AUTOPAY`, `CRED`, `IMPS/NEFT`) so they never distort genuine expense totals or merchant leaderboards.
* **Interactive Visual Analytics:** 
  * Real-time metric cards for Total Income, Total Expenses, and Net Savings.
  * Category breakdown donut chart excluding non-expense transfers.
  * Top merchant spending rankings.
* **Multi-Currency Support:** Switch between **$ (CAD / USD)** and **₹ (INR)** reporting with dynamic metric formatting.
* **AI Financial Advisor:** Powered by the official Google GenAI SDK (`gemini-2.5-flash`) to generate spending audits, answer natural language inquiries, and suggest personalized budget savings.

---

## 📂 Project Architecture

```text
ai-finance-analyzer/
│
├── app.py              # Streamlit web application, dashboard metrics, and interactive charts
├── categorizer.py      # Universal classification taxonomy, merchant text cleaner, & Gemini AI advisor
├── parser.py           # Robust document parser supporting CSV, Excel, and encrypted PDFs
├── schemas.py          # Data models and schema definitions
├── requirements.txt    # Pinned production dependencies
├── sample.csv          # Fallback statement for testing
└── README.md           # Documentation and setup guide
🚀 How to Run This Project Locally
Follow these instructions to set up the environment, install the required packages, and run the analyzer locally on your computer.

1. Prerequisites
Make sure you have the following installed on your machine:

Python 3.10+ (Verify with python --version or python3 --version)

Git (Verify with git --version)

2. Clone the Repository
Open your Terminal (macOS/Linux) or Command Prompt / PowerShell (Windows) and run:

Bash
git clone [https://github.com/Sailahari1912/ai-finance-analyzer.git](https://github.com/Sailahari1912/ai-finance-analyzer.git)
cd ai-finance-analyzer
3. Create and Activate a Virtual Environment
Using a virtual environment ensures that the project libraries do not conflict with your global Python packages.

macOS / Linux:

Bash
python3 -m venv venv
source venv/bin/activate
Windows (Command Prompt / PowerShell):

Bash
python -m venv venv
venv\Scripts\activate
4. Install Dependencies
Install all required libraries (including streamlit, pandas, plotly, pdfplumber, google-genai, openpyxl, and pydantic) using requirements.txt:

Bash
pip install --upgrade pip
pip install -r requirements.txt
5. Launch the Application
Run the Streamlit local development server:

Bash
streamlit run app.py
Your default web browser will automatically open:

Plaintext
Local URL: http://localhost:8501
💡 How to Use the App
Select Currency: Choose your preferred currency symbol ($ or ₹) in the sidebar settings.

Upload Bank Statement: Drag and drop your .csv, .xlsx, or .pdf statement. If your PDF is encrypted, enter the password in the sidebar field.

Run Categorization: Click Run Categorization to view your normalized transactions table, category spending breakdown, and top merchants.

Export Cleaned Data: Click Download Categorized Transactions (CSV) to export your processed data.

Ask the AI Advisor (Optional): Enter your Google Gemini API key in the sidebar and ask questions such as:

"How much did I spend on dining out this month?"

"Give me three areas where I can reduce discretionary spending."

🛡️ Privacy & Security
Transactions parsed locally or uploaded via the interface are processed in-memory.

Gemini AI queries only transmit necessary transaction metadata (merchant, category, amount) when an explicit user question or audit is triggered. No sensitive banking credentials or account numbers are passed.
