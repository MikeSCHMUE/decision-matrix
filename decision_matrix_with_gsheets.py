# decision_matrix_with_gsheets.py (Frontend = Master, Sheets = Storage)

import streamlit as st
import pandas as pd
import numpy as np
from oauth2client.service_account import ServiceAccountCredentials
from fpdf import FPDF
import os, uuid, tempfile
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import time
import json
import gspread
import traceback
import hashlib
import logging

# --- 🔒 Hash-basierte Speicherlogik & Logging Setup ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def get_data_hash(data):
    """
    Erzeugt einen konsistenten Hash für verschachtelte Datenstrukturen (z.B. Listen von Listen).
    Nutzt JSON-Serialisierung mit Sortierung der Schlüssel und SHA256-Hash.
    """
    data_str = json.dumps(data, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(data_str.encode('utf-8')).hexdigest()

def safe_update(ws, new_rows, label):
    """Speichert Daten nur, wenn sie sich gegenüber dem letzten Hash geändert haben."""
    key = f"{label}_hash"
    new_hash = get_data_hash(new_rows)

    if st.session_state.get(key) != new_hash:
        try:
            ws.update("A1", new_rows)
            st.session_state[key] = new_hash
            logging.info(f"✅ {label} updated successfully.")
        except Exception as e:
            st.error(f"❌ Failed to update {label}")
            st.text(str(e))
            traceback.print_exc()
    else:
        logging.info(f"⏭️ {label} unchanged – skipping update.")

# --- 📄 App Layout & Titel ---
st.set_page_config(layout="wide")
st.title("🏝️ Land Decision Matrix")

# --- 🧠 Initialisierung von Session State ---
if "criteria_list" not in st.session_state:
    st.session_state.criteria_list = []

# --- Google Sheets Setup ---
SHEET_NAME = "Decision Matrix Data"
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# 🔐 Secrets aus Streamlit einlesen (aus [google]-Block)
creds_json = dict(st.secrets["google"])
credentials = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
client = gspread.authorize(credentials)

# --- 📄 Globaler Zugriff auf alle Worksheets (nur 1× öffnen, abgesichert) ---
try:
    spreadsheet = client.open(SHEET_NAME)
    ws_options = spreadsheet.worksheet("options")
    ws_setup = spreadsheet.worksheet("setup")
    ws_comments = spreadsheet.worksheet("comments")
    ws_overview = spreadsheet.worksheet("Overview")
    ws_scores = spreadsheet.worksheet("Full Scores")
except Exception as e:
    st.error(f"❌ Fehler beim Öffnen des Google Sheets: {e}")
    traceback.print_exc()
    st.stop()

# --- Google Drive Setup ---
FOLDER_ID = "1i6W2CHXgnIn9g51tgs1WgAdZM_lK1HKP"
drive_service = build("drive", "v3", credentials=credentials)

def upload_to_drive(file, opt_key):
    tmp_file = None
    tmp_path = None
    max_retries = 5
    initial_delay = 0.1

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{uuid.uuid4()}_{file.name}", mode="wb") as tmp_file:
            tmp_file.write(file.getbuffer())
            tmp_file.flush()
            tmp_path = tmp_file.name  # wichtig: Name sichern

        file_metadata = {"name": file.name, "parents": [FOLDER_ID]}
        media = MediaFileUpload(tmp_path, resumable=False)
        uploaded = drive_service.files().create(body=file_metadata, media_body=media, fields="id").execute()

        drive_service.permissions().create(fileId=uploaded["id"], body={"role": "reader", "type": "anyone"}).execute()
        return f"https://drive.google.com/uc?id={uploaded['id']}"

    except Exception as e:
        logging.error("❌ Upload to Google Drive failed", exc_info=True)
        st.error(f"❌ Upload failed for '{file.name}': {e}")
        return None

    finally:
        if tmp_path and os.path.exists(tmp_path):
            for attempt in range(max_retries):
                try:
                    os.remove(tmp_path)
                    break
                except OSError as oe:
                    delay = initial_delay * (2 ** attempt)
                    logging.warning(f"⚠️ Attempt {attempt+1}: Failed to delete temp file '{tmp_path}': {oe}")
                    time.sleep(delay)

# --- Setup-Daten laden ---
@st.cache_data(ttl=600, show_spinner=False)
def load_setup_data(ws_setup):
    try:
        return pd.DataFrame(ws_setup.get_all_records())
    except Exception as e:
        st.warning("⚠️ Fehler beim Laden der Setup-Daten.")
        st.text(str(e))
        return pd.DataFrame()

# --- Options-Daten laden ---
@st.cache_data(ttl=600, show_spinner=False)
def load_options_data(ws_options):
    try:
        return pd.DataFrame(ws_options.get_all_records())
    except Exception as e:
        st.warning("⚠️ Fehler beim Laden der Options-Daten.")
        st.text(str(e))
        return pd.DataFrame()

# --- Kommentare laden ---
@st.cache_data(ttl=600, show_spinner=False)
def load_comment_data(ws_comments):
    try:
        return ws_comments.get_all_values()
    except Exception as e:
        st.warning("⚠️ Fehler beim Laden der Kommentare.")
        st.text(str(e))
        return []

# --- Initial Load from Sheets ---
try:
    setup_data = load_setup_data(ws_setup)
    if "Criteria" in setup_data.columns and "Weight" in setup_data.columns:
        st.session_state.criteria_list = setup_data["Criteria"].tolist()
        for i, row in setup_data.iterrows():
            st.session_state[f"weight_{row['Criteria']}"] = float(row["Weight"])
except Exception as e:
    st.warning(f"Could not load setup data from Google Sheets: {e}")

try:
    opt_data = load_options_data(ws_options)
    option_labels = dict(zip(opt_data["Key"], opt_data["Label"]))
    existing_urls = dict(zip(opt_data["Key"], opt_data.get("Image URLs", [""] * len(opt_data))))
    options = list(option_labels.keys())
    options.sort()
except Exception as e:
    st.warning(f"Could not load options data from Google Sheets: {e}")
    option_labels = {}
    existing_urls = {}
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
options.sort()

# --- Add new criterion ---
new_criterion = st.text_input("➕ Add new criterion", "")
if new_criterion and new_criterion not in st.session_state.criteria_list:
    st.session_state.criteria_list.append(new_criterion)

persons = ["Maya", "Mike"]
total_scores = {}
all_scores = []
image_urls = {}

try:
    comment_data = load_comment_data(ws_comments)
    if comment_data:
        for row in comment_data[1:]:
            crit, opt_label, comment = row
            for opt_key, label in option_labels.items():
                if label == opt_label:
                    st.session_state[f"comment_{crit}_{opt_key}"] = comment
except Exception as e:
    st.warning(f"Could not load comments from Google Sheets: {e}")

# --- Global Criteria Weighting ---
st.markdown("### ⚖️ Global Criteria Weighting")

for crit in st.session_state.criteria_list:
    st.session_state[f"weight_{crit}"] = st.number_input(
        f"Weight for '{crit}'",
        min_value=0.0,
        max_value=5.0,
        step=0.1,
        value=st.session_state.get(f"weight_{crit}", 1.0),
        key=f"weight_input_{crit}"
    )

# --- Input UI ---
st.subheader("📋 Evaluation per Land Option")

for opt in options:
    label = option_labels[opt]
    with st.container():
        st.markdown(f"### 🏝️ {label}")  # Option A+B+C+D etc.

        # --- Moved Image Upload Section ---
        st.markdown("**🖼 Upload Images**")

        # Feste Bildmaße für alle iFrames (zentral definieren)
        image_iframe_height = 170
        image_width_opt = 200
        n_cols = 3  # Anzahl der Bildspalten in der Anzeige

        # Bestehende Bild-URLs holen
        existing_links = existing_urls.get(opt, "").split(", ") if existing_urls.get(opt) else []

        # Upload-Widget
        uploaded = st.file_uploader(
            f"Upload image(s) for {label}",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=True,
            key=f"img_{opt}"
        )

        # Alle Bild-URLs sammeln (bestehend + neu)
        urls = existing_links.copy()

        # Alle neuen Bilder einmalig hochladen und Links sammeln
        if uploaded:
            for file in uploaded:
                # Prüfen, ob Datei (nach Name) schon in einem vorhandenen Link enthalten ist
                if not any(file.name in link for link in urls):
                    try:
                        link = upload_to_drive(file, opt)
                        if link:
                            urls.append(link)
                    except Exception as e:
                        st.warning(f"❌ An unexpected error occurred during image processing: {e}")
                else:
                    logging.info(f"⏭️ Upload skipped – file '{file.name}' already exists in links.")

        for idx, url in enumerate(urls):
            with cols[idx % n_cols]:
                if "drive.google.com" in url and "id=" in url:
                    file_id = url.split("id=")[-1].strip()
                    embed_url = f"https://drive.google.com/file/d/{file_id}/preview"
                    st.components.v1.iframe(
                        embed_url,
                        height=image_iframe_height,
                        width=image_width_opt,
                        key=f"img_iframe_{opt}_{idx}"  # <--- Hier der neue Key
                    )
                else:
                    st.warning("⚠️ Invalid image URL.")

        # Aktualisierte URLs zurück speichern
        image_urls[opt] = ", ".join(sorted(list(set(urls))))

        # --- Weiter mit dem Bewertungsblock oder anderem Content ---
        st.markdown("**📝 Evaluation**")
        df_rows = []
        for crit in st.session_state.criteria_list:
            row = {"Criteria": crit}
            cols = st.columns([2, 2, 2])
            with cols[0]:
                st.markdown(f"**{crit}**")
            for i, person in enumerate(persons):
                slider_key = f"{person}_{opt}_{crit}"
                slider_val = st.session_state.get(slider_key, 3)
                with cols[i + 1]:
                    slider_val = st.slider(f"{person}", 1, 5, slider_val, key=slider_key)
                row[person] = slider_val
                all_scores.append((crit, person, opt, slider_val))
            df_rows.append(row)

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
            total_scores[label] = 0

        st.success(f"✅ Total Score for {label}: {round(total_scores[label], 2)}")

# --- Smart Save Block with Hash Check (no Google Sheets read) ---
# Optionen
rows_options = [["Key", "Label", "Image URLs"]] + [[k, v, image_urls.get(k, "")] for k, v in option_labels.items()]
safe_update(ws_options, rows_options, "Options")

# Kriterien
rows_criteria = [["Criteria", "Weight"]] + [[crit, st.session_state.get(f"weight_{crit}", 1.0)] for crit in st.session_state.criteria_list]
safe_update(ws_setup, rows_criteria, "Criteria")

# Kommentare
rows_comments = [["Criteria", "Option", "Comment"]]
for crit in st.session_state.criteria_list:
    for opt in options:
        comment = st.session_state.get(f"comment_{crit}_{opt}", "")
        if comment:
            rows_comments.append([crit, option_labels[opt], comment])
if len(rows_comments) > 1:
    safe_update(ws_comments, rows_comments, "Comments")
else:
    logging.info("⏭️ No comments to save.")

# Übersicht
header_overview = ["Criteria"] + list(option_labels.values())
rows_overview = []
for crit in st.session_state.criteria_list:
    row = [crit]
    for opt in options:
        values = [val for (c, p, o, val) in all_scores if c == crit and o == opt]
        avg = round(np.mean(values), 2) if values else ""
        row.append(avg)
    rows_overview.append(row)
if rows_overview:
    safe_update(ws_overview, [header_overview] + rows_overview, "Overview")

# Einzelbewertungen
rows_scores = [["Criteria", "Person", "Option", "Score"]] + [
    [crit, person, option_labels.get(opt, opt), score]
    for (crit, person, opt, score) in all_scores
]
if len(rows_scores) > 1:
    safe_update(ws_scores, rows_scores, "Full Scores")
else:
    logging.info("⏭️ No full scores to save.")

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
        self.cell(140, 10, "Option", 1)
        self.cell(40, 10, "Total Score", 1)
        self.ln()
        self.set_font("Arial", "", 12)
        for index, row in data.iterrows():
            self.cell(140, 10, str(row["Option"]), 1)
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
