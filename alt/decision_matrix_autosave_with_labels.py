import streamlit as st
import pandas as pd
import numpy as np
import json
import os
from io import BytesIO
from fpdf import FPDF
from PIL import Image

st.set_page_config(layout="wide")
st.title("🏝️ Land Decision Matrix – Autosave + Custom Labels")

DATA_FILE = "matrix_data.json"

# --- Load Existing Data ---
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        loaded = json.load(f)
else:
    loaded = {
        "criteria_list": [
            "Price per m²", "Land Size", "Beach Quality", "Orientation & View",
            "Access & Infrastructure", "Ownership Status", "Surrounding Environment",
            "Development Potential", "Natural Risks", "Emotional Impact"
        ],
        "weights": {},
        "comments": {},
        "scores": {},
        "option_labels": {}
    }

# --- Setup ---
if "criteria_list" not in st.session_state:
    st.session_state.criteria_list = loaded.get("criteria_list", [])

new_criterion = st.text_input("➕ Add new criterion", "")
if new_criterion and new_criterion not in st.session_state.criteria_list:
    st.session_state.criteria_list.append(new_criterion)
    st.rerun()

col_count = st.number_input("How many land options?", min_value=1, max_value=10, value=3, step=1)
options = [f"Option {chr(65+i)}" for i in range(col_count)]
persons = ["Maya", "Mike"]

# --- Option Label Handling ---
option_labels = {}
for opt in options:
    default = loaded.get("option_labels", {}).get(opt, opt)
    label = st.text_input(f"Label for {opt}", value=default, key=f"label_{opt}")
    option_labels[opt] = label

# --- Prepare matrix data ---
total_scores = {}
uploaded_images = {}

def autosave():
    save_data = {
        "criteria_list": st.session_state.criteria_list,
        "weights": {},
        "comments": {},
        "scores": {},
        "option_labels": option_labels
    }
    for crit in st.session_state.criteria_list:
        save_data["weights"][crit] = st.session_state.get(f"weight_{crit}", 1.0)
        save_data["comments"][crit] = st.session_state.get(f"comment_{crit}", "")
    for opt in options:
        save_data["scores"][opt] = {}
        for person in persons:
            save_data["scores"][opt][person] = {}
            for crit in st.session_state.criteria_list:
                key = f"{person}_{opt}_{crit}"
                save_data["scores"][opt][person][crit] = st.session_state.get(key, 3)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(save_data, f, indent=4)

# --- Input Sections ---
st.subheader("📋 Evaluation per Land Option")

for opt in options:
    label = option_labels[opt]
    st.markdown(f"### {label}")
    image = st.file_uploader(f"Upload image for {label}", type=["jpg", "png", "jpeg"], key=opt)
    if image:
        uploaded_images[opt] = image
        st.image(image, width=200)

    df_rows = []
    for crit in st.session_state.criteria_list:
        row = {"Criteria": crit}
        cols = st.columns([3, 1, 1])
        with cols[0]:
            st.markdown(f"**{crit}**")
        for i, person in enumerate(persons):
            default = loaded.get("scores", {}).get(opt, {}).get(person, {}).get(crit, 3)
            row[person] = cols[i+1].slider(f"{person}", 1, 5, default, key=f"{person}_{opt}_{crit}")
        df_rows.append(row)

    st.markdown("#### 💬 Comments & Weighting")
    for crit in st.session_state.criteria_list:
        c1, c2 = st.columns([4, 1])
        default_comment = loaded.get("comments", {}).get(crit, "")
        default_weight = loaded.get("weights", {}).get(crit, 1.0)
        st.session_state[f"comment_{crit}"] = c1.text_input(f"{crit} – Comment", value=default_comment, key=f"comm_{opt}_{crit}")
        st.session_state[f"weight_{crit}"] = c2.number_input(f"{crit} – Weight", min_value=0.0, max_value=5.0, step=0.1, value=default_weight, key=f"weight_{opt}_{crit}")

    df = pd.DataFrame(df_rows)
    df["Average"] = df[persons].mean(axis=1)
    df["Weight"] = df["Criteria"].map(lambda c: st.session_state.get(f"weight_{c}", 1.0))
    df["Weighted"] = df["Average"] * df["Weight"]
    total_scores[label] = df["Weighted"].sum()

    st.success(f"🏁 Total Score for {label}: {round(total_scores[label], 2)}")
    autosave()
    st.markdown("---")

# --- Final overview ---
st.subheader("📊 Comparison of All Land Options")
result_df = pd.DataFrame({
    "Option": list(total_scores.keys()),
    "Total Score": list(total_scores.values())
}).sort_values("Total Score", ascending=False).reset_index(drop=True)

def score_color(val, max_score):
    pct = val / max_score if max_score else 0
    if pct >= 0.8:
        return "background-color: #c6f5c6"
    elif pct >= 0.5:
        return "background-color: #fff7c2"
    else:
        return "background-color: #f5c6c6"

max_score = result_df["Total Score"].max()
styled_df = result_df.style.applymap(lambda v: score_color(v, max_score), subset=["Total Score"])
st.write(styled_df)

# --- PDF Export ---
class PrettyPDF(FPDF):
    def header(self):
        self.set_font("Arial", "B", 14)
        self.cell(0, 10, "Land Decision Matrix Summary", ln=True, align="C")
        self.ln(5)

    def table(self, data_dict):
        self.set_font("Arial", "B", 12)
        self.cell(80, 10, "Option", 1)
        self.cell(40, 10, "Total Score", 1)
        self.ln()
        self.set_font("Arial", "", 12)
        for k, v in data_dict.items():
            self.cell(80, 10, str(k), 1)
            self.cell(40, 10, str(round(v, 2)), 1)
            self.ln()

def export_pretty_pdf_clean(data_dict):
    pdf = PrettyPDF()
    pdf.add_page()
    pdf.table(data_dict)
    return pdf.output(dest='S').encode("latin-1", errors="ignore")

if st.button("📄 Export Summary as PDF"):
    pdf_bytes_clean = export_pretty_pdf_clean(total_scores)
    st.download_button("Download PDF", data=pdf_bytes_clean, file_name="decision_summary.pdf", mime="application/pdf")
