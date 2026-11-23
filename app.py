import os
import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv
from groq import Groq

# Load environment variables from .env if present
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY") or st.secrets.get("GROQ_API_KEY", "")

st.set_page_config(
    page_title="Budget vs. Actuals AI | Variance Analysis & Commentary",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Budget vs. Actuals AI – Variance Analysis & Commentary")
st.write("Upload your Budget vs. Actuals file (.xlsx / .csv) and get AI-driven financial insights!")

if not GROQ_API_KEY:
    st.error("🔑 API Key is missing! Set GROQ_API_KEY in a .env file or Streamlit Secrets.")
    st.stop()

if "ai_commentary" not in st.session_state:
    st.session_state.ai_commentary = None

uploaded_file = st.file_uploader(
    "Upload your dataset (Excel or CSV)",
    type=["xlsx", "csv"],
)

if uploaded_file is None:
    st.info("Silakan upload file `.xlsx` atau `.csv` yang memuat data kategori/akun, nilai Budget, dan nilai Actual.")
    st.stop()

# Read Excel (with sheet selector) or CSV
file_name = uploaded_file.name.lower()
try:
    if file_name.endswith(".xlsx"):
        excel_file = pd.ExcelFile(uploaded_file)
        sheet_names = excel_file.sheet_names
        selected_sheet = st.sidebar.selectbox("Pilih Sheet Excel", sheet_names)
        raw_df = pd.read_excel(excel_file, sheet_name=selected_sheet)
    else:
        raw_df = pd.read_csv(uploaded_file)
except Exception as e:
    st.error(f"Gagal membaca file: {e}")
    st.stop()

if raw_df.empty or len(raw_df.columns) < 3:
    st.error("File kosong atau memiliki kurang dari 3 kolom.")
    st.stop()

# Sidebar column mapping so different column names still work smoothly
st.sidebar.header("Pemetaan Kolom")
columns = list(raw_df.columns)

default_cat_idx = next((i for i, c in enumerate(columns) if str(c).strip().lower() in {"category", "kategori", "akun", "account"}), 0)
default_bud_idx = next((i for i, c in enumerate(columns) if str(c).strip().lower() in {"budget", "anggaran", "plan"}), min(1, len(columns) - 1))
default_act_idx = next((i for i, c in enumerate(columns) if str(c).strip().lower() in {"actual", "realisasi", "real"}), min(2, len(columns) - 1))

cat_col = st.sidebar.selectbox("Kolom Kategori / Akun", columns, index=default_cat_idx)
budget_col = st.sidebar.selectbox("Kolom Budget", columns, index=default_bud_idx)
actual_col = st.sidebar.selectbox("Kolom Actual", columns, index=default_act_idx)

# Build standardized analysis DataFrame
df = pd.DataFrame(
    {
        "Category": raw_df[cat_col].astype(str).str.strip(),
        "Budget": pd.to_numeric(raw_df[budget_col], errors="coerce").fillna(0.0),
        "Actual": pd.to_numeric(raw_df[actual_col], errors="coerce").fillna(0.0),
    }
)
df = df[df["Category"] != ""].reset_index(drop=True)

if df.empty:
    st.warning("Tidak ada baris data valid setelah pembersihan kategori.")
    st.stop()

df["Variance"] = df["Actual"] - df["Budget"]
df["Variance_Pct"] = df.apply(
    lambda row: ((row["Actual"] - row["Budget"]) / row["Budget"] * 100.0) if row["Budget"] != 0 else 0.0,
    axis=1,
)
df["Status"] = df["Variance"].apply(
    lambda v: "Over Budget" if v > 0 else ("Under Budget" if v < 0 else "On Budget")
)

# Sidebar filters
st.sidebar.header("Filter Data")
status_options = ["Over Budget", "Under Budget", "On Budget"]
selected_statuses = st.sidebar.multiselect("Status Varians", status_options, default=status_options)
search_query = st.sidebar.text_input("Cari Kategori", "").strip().lower()

filtered_df = df.copy()
if selected_statuses:
    filtered_df = filtered_df[filtered_df["Status"].isin(selected_statuses)]
else:
    filtered_df = filtered_df.iloc[0:0]

if search_query:
    filtered_df = filtered_df[filtered_df["Category"].str.lower().str.contains(search_query, na=False)]

# Summary metrics based on filtered data
total_budget = float(filtered_df["Budget"].sum())
total_actual = float(filtered_df["Actual"].sum())
total_variance = total_actual - total_budget
total_var_pct = (total_variance / total_budget * 100.0) if total_budget != 0 else 0.0

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Budget", f"{total_budget:,.2f}")
c2.metric("Total Actual", f"{total_actual:,.2f}")
c3.metric("Total Variance", f"{total_variance:+,.2f}", f"{total_var_pct:+.2f}%")
c4.metric("Over Budget Items", int((filtered_df["Status"] == "Over Budget").sum()))

# Table & CSV download
st.subheader("Ringkasan Tabel Varians")
st.dataframe(
    filtered_df.style.format(
        {
            "Budget": "{:,.2f}",
            "Actual": "{:,.2f}",
            "Variance": "{:+,.2f}",
            "Variance_Pct": "{:+.2f}%",
        }
    ),
    use_container_width=True,
)

csv_data = filtered_df.to_csv(index=False).encode("utf-8")
st.download_button(
    label="⬇️ Download Variance Table (CSV)",
    data=csv_data,
    file_name="budget_variance_report.csv",
    mime="text/csv",
)

# Charts
if not filtered_df.empty:
    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.subheader("Budget vs. Actual per Kategori")
        df_melted = filtered_df.melt(
            id_vars="Category",
            value_vars=["Budget", "Actual"],
            var_name="Type",
            value_name="Amount",
        )
        fig_bar = px.bar(
            df_melted,
            x="Category",
            y="Amount",
            color="Type",
            barmode="group",
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_chart2:
        st.subheader("Varians Nominal per Kategori")
        fig_var = px.bar(
            filtered_df.sort_values("Variance", ascending=True),
            x="Variance",
            y="Category",
            color="Status",
            orientation="h",
        )
        st.plotly_chart(fig_var, use_container_width=True)

# AI Commentary via Groq
st.subheader("Komentar & Insight AI (Groq)")
focus_mode = st.selectbox(
    "Fokus Analisis AI",
    [
        "Executive Summary & Varians Utama",
        "Root-Cause & Risiko Over Budget",
        "Rekomendasi Efisiensi & Kontrol Anggaran",
    ],
)

if st.button("✨ Generate AI Commentary"):
    if filtered_df.empty:
        st.warning("Tidak ada data terfilter untuk dianalisis oleh AI.")
    else:
        client = Groq(api_key=GROQ_API_KEY)
        summary_text = filtered_df[
            ["Category", "Budget", "Actual", "Variance", "Variance_Pct", "Status"]
        ].to_string(index=False)

        prompt = (
            "Kamu adalah analis keuangan senior. Berikan analisis varians Budget vs. Actual "
            f"dengan fokus '{focus_mode}' secara ringkas, jelas, dan actionable dalam bahasa Indonesia.\n\n"
            f"Total Budget: {total_budget:,.2f}\n"
            f"Total Actual: {total_actual:,.2f}\n"
            f"Total Variance: {total_variance:+,.2f} ({total_var_pct:+.2f}%)\n\n"
            f"Rincian Data:\n{summary_text}"
        )

        try:
            with st.spinner("Menghasilkan analisis AI..."):
                completion = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                )
            st.session_state.ai_commentary = completion.choices[0].message.content
        except Exception as e:
            st.error(f"Gagal menghasilkan analisis AI: {e}")

if st.session_state.ai_commentary:
    st.markdown(st.session_state.ai_commentary)