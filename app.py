import streamlit as st
from io import BytesIO
import re
from PIL import Image
import pytesseract
import pdfplumber
from docx import Document
import pandas as pd

st.set_page_config(page_title="🇮🇳 Indian Payslip Tax Optimizer v2", layout="wide")
st.title("🇮🇳 Indian Payslip Tax Optimizer (FY 2025-26 / AY 2026-27)")
st.markdown("**Upload payslip (PDF/DOCX/Image) → Instant tax-saving plan with latest slabs + exports**")

# ====================== FIXED TAX CALCULATOR (Corrected logic) ======================
def calculate_tax(taxable_income, regime="new"):
    if regime == "new":
        std_ded = 75000
        rebate_max = 60000
        rebate_threshold = 1200000
        # Progressive calculation with 0% slab
        taxable = max(0, taxable_income - std_ded)
        if taxable <= 400000:
            tax = 0
        elif taxable <= 800000:
            tax = (taxable - 400000) * 0.05
        elif taxable <= 1200000:
            tax = (400000 * 0.05) + (taxable - 800000) * 0.10
        elif taxable <= 1600000:
            tax = (400000*0.05 + 400000*0.10) + (taxable - 1200000) * 0.15
        elif taxable <= 2000000:
            tax = (400000*0.05 + 400000*0.10 + 400000*0.15) + (taxable - 1600000) * 0.20
        elif taxable <= 2400000:
            tax = (400000*0.05 + 400000*0.10 + 400000*0.15 + 400000*0.20) + (taxable - 2000000) * 0.25
        else:
            tax = (400000*0.05 + 400000*0.10 + 400000*0.15 + 400000*0.20 + 400000*0.25) + (taxable - 2400000) * 0.30
    else:  # old
        std_ded = 50000
        rebate_max = 12500
        rebate_threshold = 500000
        taxable = max(0, taxable_income - std_ded)
        if taxable <= 250000:
            tax = 0
        elif taxable <= 500000:
            tax = (taxable - 250000) * 0.05
        elif taxable <= 1000000:
            tax = (250000 * 0.05) + (taxable - 500000) * 0.20
        else:
            tax = (250000*0.05 + 500000*0.20) + (taxable - 1000000) * 0.30

    # Rebate u/s 87A
    if taxable <= rebate_threshold:
        tax = max(0, tax - rebate_max)

    # 4% Cess
    tax = tax * 1.04
    return round(tax)

def hra_exemption(basic_annual, hra_annual, rent_annual, metro=True):
    salary_for_hra = basic_annual
    exempt = min(
        hra_annual,
        0.50 * salary_for_hra if metro else 0.40 * salary_for_hra,
        max(0, rent_annual - 0.10 * salary_for_hra)
    )
    return round(exempt)

# ====================== IMPROVED PARSER ======================
def extract_payslip_data(text):
    data = {"basic": 0, "hra": 0, "gross": 0, "tds": 0, "pf": 0, "net": 0}
    patterns = {
        "basic": r'(?:Basic(?:\s*Pay|\s*Salary)?|BASIC)[\s:₹,.\-]*(\d{1,8})',
        "hra": r'(?:HRA|House Rent Allowance)[\s:₹,.\-]*(\d{1,8})',
        "gross": r'(?:Gross\s*(?:Salary|Earnings|Total)|TOTAL EARNINGS)[\s:₹,.\-]*(\d{1,8})',
        "tds": r'(?:TDS|Income Tax|TAX DEDUCTED|IT)[\s:₹,.\-]*(\d{1,8})',
        "pf": r'(?:PF|Provident Fund|EPF)[\s:₹,.\-]*(\d{1,8})',
        "net": r'(?:Net Pay|Net Salary|Take Home)[\s:₹,.\-]*(\d{1,8})',
    }
    for key, pat in patterns.items():
        matches = re.findall(pat, text, re.IGNORECASE)
        if matches:
            data[key] = max(int(m.replace(',', '')) for m in matches)
    return data

# ====================== STREAMLIT APP ======================
uploaded = st.file_uploader("Upload payslip (PDF / DOCX / JPG / PNG)", 
                          type=["pdf", "docx", "jpg", "jpeg", "png"])

if uploaded:
    file_type = uploaded.name.split(".")[-1].lower()
    full_text = ""
    
    with st.spinner("🔍 Reading payslip..."):
        try:
            if file_type == "pdf":
                with pdfplumber.open(BytesIO(uploaded.read())) as pdf:
                    for page in pdf.pages:
                        txt = page.extract_text() or ""
                        full_text += txt + "\n"
                        for table in page.extract_tables():
                            for row in table:
                                if row:
                                    full_text += " | ".join(str(cell or "") for cell in row) + "\n"
            
            elif file_type == "docx":
                doc = Document(BytesIO(uploaded.read()))
                full_text = "\n".join(p.text for p in doc.paragraphs)
            
            else:  # image
                img = Image.open(BytesIO(uploaded.read()))
                full_text = pytesseract.image_to_string(img)
            
            if not full_text.strip():
                st.error("❌ No text found. Try a clearer scan or text-based PDF.")
                st.stop()
                
            data = extract_payslip_data(full_text)
            
            # Annualize (monthly payslip assumed)
            monthly = {k: v for k, v in data.items() if v > 0}
            annual = {k: v * 12 for k, v in monthly.items()}
            
            st.success("✅ Payslip parsed successfully!")
            
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Monthly Figures")
                st.json(monthly)
            with col2:
                st.subheader("Annual Figures")
                st.json(annual)
            
            # ====================== USER INPUTS ======================
            st.subheader("Tell us a bit more")
            colA, colB, colC = st.columns(3)
            with colA:
                rent_monthly = st.number_input("Monthly Rent Paid ₹", 0, value=15000, step=1000)
                metro = st.checkbox("Metro city (Delhi/Mumbai/Bengaluru/Kolkata/Chennai)", True)
            with colB:
                invested_80c = st.number_input("Already invested in 80C this year ₹", 0, value=50000, step=5000)
            with colC:
                regime = st.radio("Analysis mode", ["Auto Compare", "Old Regime", "New Regime"])
            
            rent_annual = rent_monthly * 12
            hra_exempt = hra_exemption(annual.get("basic", 0), annual.get("hra", 0), rent_annual, metro)
            
            gross_annual = annual.get("gross", 0) or annual.get("basic", 0) * 1.5
            
            # ====================== CALCULATIONS ======================
            new_tax = calculate_tax(gross_annual, "new")
            old_deductions = 50000 + hra_exempt + invested_80c
            old_tax = calculate_tax(gross_annual - old_deductions, "old")  # rough with current investments
            
            # Max possible old regime
            max_old_ded = 50000 + hra_exempt + 150000 + 50000  # 80C + NPS 80CCD(1B)
            max_old_tax = calculate_tax(gross_annual - max_old_ded, "old")
            
            savings_potential = new_tax - max_old_tax if max_old_tax < new_tax else 0
            
            # Best regime
            best_regime = "Old" if old_tax < new_tax else "New"
            diff = abs(new_tax - old_tax)
            
            # ====================== RESULTS ======================
            st.subheader("📊 Tax Liability (Annual)")
            c1, c2, c3 = st.columns(3)
            c1.metric("New Regime", f"₹{new_tax:,}")
            c2.metric("Old Regime (current investments)", f"₹{old_tax:,}")
            c3.metric("After Max Optimisation", f"₹{max_old_tax:,}", delta=f"-₹{savings_potential:,}")
            
            st.success(f"**Best: {best_regime} Regime** — saves you ₹{diff:,} this year!")
            
            # ====================== ACTIONABLE PLAN ======================
            st.subheader("🚀 Your Personal Tax-Saving Action Plan")
            recs = []
            if hra_exempt > 0:
                recs.append(f"**Claim HRA ₹{hra_exempt:,}** — Submit rent agreement + PAN + Form 12BB to HR today")
            if 150000 - invested_80c > 0:
                recs.append(f"**Invest remaining 80C ₹{150000 - invested_80c:,}** before 31 Mar (ELSS / PPF / NSC)")
            recs.append("**Open NPS Tier-1** for extra ₹50,000 deduction (Old regime) — ~₹15k–20k extra saving")
            recs.append("**Buy Health Insurance (80D)** — ₹25k–50k policy for self/parents")
            recs.append("**Submit proofs to HR by 15 March** so TDS drops from next salary")
            
            for i, r in enumerate(recs, 1):
                st.write(f"{i}. {r}")
            
            st.caption(f"💰 **Potential total savings: ₹{savings_potential:,}** if you act fast!")
            
            # ====================== DOWNLOADS ======================
            summary = {
                "Item": ["Gross Annual", "New Regime Tax", "Old Regime Tax", "Max Savings", "Recommended"],
                "Amount": [f"₹{gross_annual:,}", f"₹{new_tax:,}", f"₹{old_tax:,}", f"₹{savings_potential:,}", best_regime]
            }
            df = pd.DataFrame(summary)
            
            colD, colE = st.columns(2)
            with colD:
                st.download_button("📥 Download Tax Summary (CSV)", 
                                 df.to_csv(index=False).encode(), 
                                 "tax_summary.csv", "text/csv")
            with colE:
                form12bb = f"""FORM 12BB
Name: ________________
PAN: ________________
1. House Rent Allowance: ₹{hra_exempt:,}
2. Rent paid: ₹{rent_annual:,}
3. 80C investments: ₹{invested_80c:,}
Declaration: I declare the above is true.
Date: {pd.Timestamp.today().date()}"""
                st.download_button("📥 Download Form 12BB Draft (TXT)", form12bb, "Form_12BB.txt", "text/plain")
            
            with st.expander("Raw extracted text"):
                st.text(full_text[:1500])
                
        except Exception as e:
            st.error(f"⚠️ Error processing file: {str(e)}")
            st.info("Tip: For images, make sure Tesseract OCR is installed. Try a clearer PDF instead.")

else:
    st.info("👆 Upload your payslip to begin. Supports TCS, Infosys, Wipro, Accenture, govt, startups — almost all formats.")
    st.caption("Pro tip: Take a clear photo of your payslip if you don't have the PDF.")

with st.expander("How to run (one-time setup)"):
    st.code("""
pip install streamlit pdfplumber python-docx pillow pytesseract pandas
# Windows: Download Tesseract → https://github.com/UB-Mannheim/tesseract/wiki
# Ubuntu: sudo apt install tesseract-ocr
# Mac: brew install tesseract

streamlit run payslip_optimizer_v2.py
    """, language="bash")
