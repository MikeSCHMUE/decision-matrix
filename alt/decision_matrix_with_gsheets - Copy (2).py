# decision_matrix_with_gsheets.py (Frontend = Master, Sheets = Storage)

import streamlit as st
import pandas as pd
import numpy as np
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from fpdf import FPDF

st.set_page_config(layout="wide")
st.title("🏝️ Land Decision Matrix – Frontend First")

# --- Google Sheets Setup ---
SHEET_NAME = "Decision Matrix Data"
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)

# --- Session Init ---
if "criteria_list" not in st.session_state:
    st.session_state.criteria_list = [
        "Price per m²", "Land Size", "Beach Quality", "Orientation & View",
        "Access & Infrastructure", "Ownership Status", "Surrounding Environment",
        "Development Potential", "Natural Risks", "Emotional Impact"
    ]

# --- Initial Load from Sheets ---
try:
    sheet_setup = client.open(SHEET_NAME).worksheet("setup")
    setup_data = pd.DataFrame(sheet_setup.get_all_records())
    if "Criteria" in setup_data.columns and "Weight" in setup_data.columns:
        st.session_state.criteria_list = setup_data["Criteria"].tolist()
        for i, row in setup_data.iterrows():
            st.session_state[f"weight_{row['Criteria']}"] = float(row["Weight"])
except:
    pass

try:
    sheet_opts = client.open(SHEET_NAME).worksheet("options")
    opt_data = pd.DataFrame(sheet_opts.get_all_records())
    option_labels = dict(zip(opt_data["Key"], opt_data["Label"]))
    options = list(option_labels.keys())
except:
    option_labels = {}
    options = []

# --- Dynamische Optionenzahl ---
col_count = st.number_input("How many land options?", min_value=1, max_value=10, value=len(options) or 3, step=1)
for i in range(col_count):
    key = f"Option {chr(65+i)}"
    if key not in option_labels:
        option_labels[key] = key
    label = st.text_input(f"Label for {key}", value=option_labels[key], key=f"label_{key}")
    option_labels[key] = label
options = list(option_labels.keys())

# --- Add new criterion ---
new_criterion = st.text_input("➕ Add new criterion", "")
if new_criterion and new_criterion not in st.session_state.criteria_list:
    st.session_state.criteria_list.append(new_criterion)

persons = ["Maya", "Mike"]

# --- Load Comments ---
try:
    sheet_comments = client.open(SHEET_NAME).worksheet("comments")
    comment_data = sheet_comments.get_all_values()
    if comment_data:
        for row in comment_data[1:]:
            crit, opt_label, comment = row
            for opt_key, label in option_labels.items():
                if label == opt_label:
                    st.session_state[f"comment_{crit}_{opt_key}"] = comment
except:
    pass

# --- Input UI ---
st.subheader("📋 Evaluation per Land Option")
total_scores = {}
all_scores = []

for opt in options:
    label = option_labels[opt]
    with st.container():
        st.markdown(f"### 🏝️ {label}")
        df_rows = []
        st.markdown("**📝 Evaluation**")
        for crit in st.session_state.criteria_list:
            row = {"Criteria": crit}
            cols = st.columns([2, 2, 2])
            with cols[0]:
                st.markdown(f"**{crit}**")
            for i, person in enumerate(persons):
                slider_key = f"{person}_{opt}_{crit}"
                slider_val = st.session_state.get(slider_key, 3)
                with cols[i+1]:
                    slider_val = st.slider(f"{person}", 1, 5, slider_val, key=slider_key)
                row[person] = slider_val
                all_scores.append((crit, person, opt, slider_val))
            df_rows.append(row)

        st.markdown("**💬 Comments & Weighting**")
        for crit in st.session_state.criteria_list:
            c1, c2 = st.columns([4, 1])
            comment_key = f"comment_{crit}_{opt}"
            comment_val = st.session_state.get(comment_key, "")
            st.session_state[comment_key] = c1.text_input(f"Comment for {crit}", value=comment_val, key=f"comm_{opt}_{crit}")
            st.session_state[f"weight_{crit}"] = c2.number_input(f"Weight", min_value=0.0, max_value=5.0, step=0.1, value=st.session_state.get(f"weight_{crit}", 1.0), key=f"weight_{opt}_{crit}")

        df = pd.DataFrame(df_rows)
        if "Criteria" in df.columns:
            available_persons = [p for p in persons if p in df.columns]
            if available_persons:
                df["Average"] = df[available_persons].mean(axis=1)
            else:
                df["Average"] = 3
            df["Weight"] = df["Criteria"].map(lambda c: st.session_state.get(f"weight_{c}", 1.0))
            df["Weighted"] = df["Average"] * df["Weight"]
            total_scores[label] = df["Weighted"].sum()
        else:
            df = pd.DataFrame()
            df["Average"] = 3
            df["Weight"] = 1.0
            df["Weighted"] = df["Average"] * df["Weight"]
            total_scores[label] = 0

        st.success(f"✅ Total Score for {label}: {round(total_scores[label], 2)}")

# --- Save Options ---
try:
    sheet_opts = client.open(SHEET_NAME).worksheet("options")
    rows = [["Key", "Label"]] + [[k, v] for k, v in option_labels.items()]
    sheet_opts.clear()
    sheet_opts.update("A1", rows)
except:
    pass

# --- Save Criteria ---
try:
    sheet_setup = client.open(SHEET_NAME).worksheet("setup")
    rows = [["Criteria", "Weight"]] + [[crit, st.session_state.get(f"weight_{crit}", 1.0)] for crit in st.session_state.criteria_list]
    sheet_setup.clear()
    sheet_setup.update("A1", rows)
except:
    pass

# --- Save Comments ---
try:
    sheet_comm = client.open(SHEET_NAME).worksheet("comments")
    rows = [["Criteria", "Option", "Comment"]]
    for crit in st.session_state.criteria_list:
        for opt in options:
            comment = st.session_state.get(f"comment_{crit}_{opt}", "")
            if comment:
                rows.append([crit, option_labels[opt], comment])
    if len(rows) > 1:
        sheet_comm.clear()
        sheet_comm.update("A1", rows)
except:
    pass

# --- Save Overview ---
try:
    sheet_ov = client.open(SHEET_NAME).worksheet("Overview")
    header = ["Criteria"] + list(option_labels.values())
    rows = []
    for crit in st.session_state.criteria_list:
        row = [crit]
        for opt in options:
            values = [val for (c, p, o, val) in all_scores if c == crit and o == opt]
            avg = round(np.mean(values), 2) if values else ""
            row.append(avg)
        rows.append(row)
    sheet_ov.clear()
    sheet_ov.update("A1", [header] + rows)
except:
    pass

# --- Save Full Scores ---
try:
    sheet_full = client.open(SHEET_NAME).worksheet("Full Scores")
    rows = [["Criteria", "Person", "Option", "Score"]] + list(all_scores)
    sheet_full.clear()
    sheet_full.update("A1", rows)
except:
    pass

# --- Overview Display ---
st.subheader("📊 Comparison of All Land Options")
result_df = pd.DataFrame({"Option": list(total_scores.keys()), "Total Score": list(total_scores.values())}) if total_scores else pd.DataFrame(columns=["Option", "Total Score"])
result_df = result_df.sort_values("Total Score", ascending=False).reset_index(drop=True)
st.dataframe(result_df, use_container_width=True)

# --- PDF Export ---
class PDF(FPDF):
    def header(self):
        self.set_font("Arial", "B", 14)
        self.cell(0, 10, "Decision Matrix Summary", ln=True, align="C")
        self.ln(5)

    def table(self, data):
        self.set_font("Arial", "B", 12)
        self.cell(80, 10, "Option", 1)
        self.cell(40, 10, "Total Score", 1)
        self.ln()
        self.set_font("Arial", "", 12)
        for index, row in data.iterrows():
            self.cell(80, 10, str(row["Option"]), 1)
            self.cell(40, 10, str(round(row["Total Score"], 2)), 1)
            self.ln()

def generate_pdf(df):
    pdf = PDF()
    pdf.add_page()
    pdf.table(df)
    return pdf.output(dest="S").encode("latin-1", errors="ignore")

if not result_df.empty:
    pdf_bytes = generate_pdf(result_df)
    st.download_button("📄 Download Summary as PDF", data=pdf_bytes, file_name="decision_summary.pdf", mime="application/pdf")
