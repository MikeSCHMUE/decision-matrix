# decision_matrix_with_gsheets.py (Frontend = Master, Sheets = Storage)

import streamlit as st
import pandas as pd
import numpy as np
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from fpdf import FPDF
import os, uuid, tempfile
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import time # Make sure time is imported

st.set_page_config(layout="wide")
st.title("🏝️ Land Decision Matrix – Frontend First")

# --- Google Sheets Setup ---
SHEET_NAME = "Decision Matrix Data"
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)

# --- Google Drive Setup ---
FOLDER_ID = "1i6W2CHXgnIn9g51tgs1WgAdZM_lK1HKP"
drive_service = build("drive", "v3", credentials=creds)

def upload_to_drive(file, opt_key):
    """
    Uploads a file to Google Drive and sets its permissions to be publicly readable.
    Handles temporary file creation and ensures its deletion.

    Args:
        file: The file object from Streamlit's st.file_uploader.
        opt_key: An identifier for the option (used for context, not directly in upload logic).

    Returns:
        str: The public URL of the uploaded file if successful, None otherwise.
    """
    tmp_path = None  # Initialize tmp_path to ensure it's defined for the finally block
    max_retries = 5  # Maximum number of attempts to delete the file
    initial_delay = 0.1 # Initial delay in seconds
    
    try:
        # Create a unique temporary file path
        # Using tempfile.gettempdir() ensures it's in the system's temp directory
        # uuid.uuid4() ensures a unique filename to avoid conflicts
        tmp_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}_{file.name}")
        
        # Write the content of the uploaded file to the temporary file
        with open(tmp_path, "wb") as f:
            f.write(file.getbuffer()) # getbuffer() is efficient for BytesIO objects
        
        # Define metadata for the file to be uploaded to Google Drive
        # 'name' is the filename, 'parents' specifies the folder ID
        file_metadata = {"name": file.name, "parents": [FOLDER_ID]}
        
        # Create a MediaFileUpload object for resumable uploads (good for larger files)
        media = MediaFileUpload(tmp_path, resumable=True)
        
        # Execute the file creation (upload) to Google Drive
        # 'fields="id"' requests only the ID of the uploaded file in the response
        uploaded = drive_service.files().create(body=file_metadata, media_body=media, fields="id").execute()
        
        # Set the permissions of the uploaded file to be publicly readable
        # 'role': 'reader' allows viewing, 'type': 'anyone' makes it public
        drive_service.permissions().create(fileId=uploaded["id"], body={"role": "reader", "type": "anyone"}).execute()
        
        # Construct and return the public download URL for the uploaded file
        return f"https://drive.google.com/uc?id={uploaded['id']}"
    
    except Exception as e:
        # Catch any exception that occurs during the try block
        # Print an error message to the console or Streamlit warning
        st.error(f"❌ Error uploading file to Google Drive: {e}")
        return None # Return None to indicate upload failure
    
    finally:
        # This block ensures that the temporary file is deleted,
        # regardless of whether the upload succeeded or failed.
        if tmp_path and os.path.exists(tmp_path):
            for attempt in range(max_retries):
                try:
                    os.remove(tmp_path)
                    # print(f"Temporary file '{tmp_path}' deleted successfully.") # Optional: for debugging
                    break  # Exit loop if deletion is successful
                except OSError as e:
                    # If deletion fails, print a warning and retry after a delay
                    # Exponential backoff: delay increases with each retry
                    delay = initial_delay * (2 ** attempt)
                    st.warning(f"Failed to delete temporary file '{tmp_path}': {e}. Retrying in {delay:.2f} seconds...")
                    time.sleep(delay)
            else:
                # This block executes if the loop completes without a successful deletion
                st.error(f"Failed to delete temporary file '{tmp_path}' after {max_retries} attempts. Manual cleanup may be required.")

# # --- Google Drive Setup ---
# FOLDER_ID = "1i6W2CHXgnIn9g51tgs1WgAdZM_lK1HKP"
# drive_service = build("drive", "v3", credentials=creds)

# def upload_to_drive(file, opt_key):
#     tmp_path = None
#     max_retries = 5  # Maximum number of attempts to delete the file
#     initial_delay = 0.1 # Initial delay in seconds
    
#     try:
#         tmp_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}_{file.name}")
        
#         with open(tmp_path, "wb") as f:
#             f.write(file.getbuffer()) 
        
#         file_metadata = {"name": file.name, "parents": [FOLDER_ID]}
#         media = MediaFileUpload(tmp_path, resumable=True)
        
#         uploaded = drive_service.files().create(body=file_metadata, media_body=media, fields="id").execute()
        
#         drive_service.permissions().create(fileId=uploaded["id"], body={"role": "reader", "type": "anyone"}).execute()
        
#         return f"https://drive.google.com/uc?id={uploaded['id']}"

# def upload_to_drive(file, opt_key):
#     tmp_path = None 
#     try:
#         tmp_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}_{file.name}")
        
#         with open(tmp_path, "wb") as f:
#             f.write(file.getbuffer()) 
        
#         file_metadata = {"name": file.name, "parents": [FOLDER_ID]}
#         media = MediaFileUpload(tmp_path, resumable=True)
        
#         uploaded = drive_service.files().create(body=file_metadata, media_body=media, fields="id").execute()
        
#         drive_service.permissions().create(fileId=uploaded["id"], body={"role": "reader", "type": "anyone"}).execute()
        
#         return f"https://drive.google.com/uc?id={uploaded['id']}"
    
#     except Exception as e:
#         raise e 
    
#     finally:
#         if tmp_path and os.path.exists(tmp_path):
#             # Introduce a small delay before attempting to delete the file
#             # 0.1 to 0.5 seconds is usually sufficient on Windows
#             time.sleep(0.2) 
#             try:
#                 os.remove(tmp_path)
#             except OSError as e:
#                 # This warning means the file was still locked for deletion, but the upload succeeded.
#                 st.warning(f"Failed to delete temporary file {tmp_path}: {e}")

# # --- Google Drive Setup ---
# FOLDER_ID = "1i6W2CHXgnIn9g51tgs1WgAdZM_lK1HKP"
# drive_service = build("drive", "v3", credentials=creds)

# def upload_to_drive(file, opt_key):
#     tmp_path = None # Initialize tmp_path to ensure it's defined for the finally block
#     try:
#         # Create a temporary file path
#         # Using tempfile.gettempdir() for path and uuid for uniqueness
#         tmp_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}_{file.name}")
        
#         # Write the uploaded file content to the temporary file
#         with open(tmp_path, "wb") as f:
#             f.write(file.getbuffer()) # Use getbuffer() for efficiency with BytesIO
        
#         # At this point, the temporary file is closed by the 'with' statement.
#         # Now, prepare the MediaFileUpload object
#         file_metadata = {"name": file.name, "parents": [FOLDER_ID]}
#         media = MediaFileUpload(tmp_path, resumable=True)
        
#         # Execute the upload
#         uploaded = drive_service.files().create(body=file_metadata, media_body=media, fields="id").execute()
        
#         # Set permissions
#         drive_service.permissions().create(fileId=uploaded["id"], body={"role": "reader", "type": "anyone"}).execute()
        
#         return f"https://drive.google.com/uc?id={uploaded['id']}"
    
#     except Exception as e:
#         # Re-raise the exception after cleanup, so Streamlit can display it
#         raise e 
    
#     finally:
#         # Ensure the temporary file is deleted
#         if tmp_path and os.path.exists(tmp_path):
#             try:
#                 os.remove(tmp_path)
#             except OSError as e:
#                 # Log or display a warning if deletion itself fails, but don't block the app
#                 st.warning(f"Failed to delete temporary file {tmp_path}: {e}")

# # --- Google Drive Setup ---
# FOLDER_ID = "1i6W2CHXgnIn9g51tgs1WgAdZM_lK1HKP"
# drive_service = build("drive", "v3", credentials=creds)

# def upload_to_drive(file, opt_key):
#     tmp_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}_{file.name}")
#     with open(tmp_path, "wb") as tmp:
#         tmp.write(file.getbuffer())

#     file_metadata = {"name": file.name, "parents": [FOLDER_ID]}
#     media = MediaFileUpload(tmp_path, resumable=True)
#     uploaded = drive_service.files().create(body=file_metadata, media_body=media, fields="id").execute()

#     os.remove(tmp_path)

#     drive_service.permissions().create(fileId=uploaded["id"], body={"role": "reader", "type": "anyone"}).execute()
#     return f"https://drive.google.com/uc?id={uploaded['id']}"


# def upload_to_drive(file, opt_key):
#     # Create a temporary file
#     with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp") as tmp:
#         tmp.write(file.getbuffer())
#         # Ensure all data is written to disk
#         tmp.flush()
#         os.fsync(tmp.fileno())
#         tmp_path = tmp.name

#     file_metadata = {"name": file.name, "parents": [FOLDER_ID]}
    
#     # MediaFileUpload will read from this path.
#     # The file handle for 'tmp' is already closed because we've exited the 'with' block.
#     media = MediaFileUpload(tmp_path, resumable=True)
    
#     try:
#         uploaded = drive_service.files().create(body=file_metadata, media_body=media, fields="id").execute()
#     finally:
#         # Ensure the temporary file is deleted even if the upload fails
#         os.remove(tmp_path)

#     drive_service.permissions().create(fileId=uploaded["id"], body={"role": "reader", "type": "anyone"}).execute()
#     return f"https://drive.google.com/uc?id={uploaded['id']}"

# def upload_to_drive(file, opt_key):
#     with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp") as tmp:
#         tmp.write(file.getbuffer())
#         tmp.flush()
#         os.fsync(tmp.fileno())
#         tmp_path = tmp.name

#     file_metadata = {"name": file.name, "parents": [FOLDER_ID]}
#     media = MediaFileUpload(tmp_path, resumable=True)
#     uploaded = drive_service.files().create(body=file_metadata, media_body=media, fields="id").execute()


#     os.remove(tmp_path)

#     drive_service.permissions().create(fileId=uploaded["id"], body={"role": "reader", "type": "anyone"}).execute()
#     return f"https://drive.google.com/uc?id={uploaded['id']}"

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
    existing_urls = dict(zip(opt_data["Key"], opt_data.get("Image URLs", [""] * len(opt_data))))
    options = list(option_labels.keys())
except:
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

# --- Add new criterion ---
new_criterion = st.text_input("➕ Add new criterion", "")
if new_criterion and new_criterion not in st.session_state.criteria_list:
    st.session_state.criteria_list.append(new_criterion)

persons = ["Maya", "Mike"]
total_scores = {}
all_scores = []
image_urls = {}

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

        st.markdown("**🖼 Upload Images**")
        uploaded = st.file_uploader(f"Upload image(s) for {label}", type=["jpg", "jpeg", "png"], accept_multiple_files=True, key=f"img_{opt}")
        urls = []
        for file in uploaded:
            try:
                link = upload_to_drive(file, opt)
                urls.append(link)
                st.image(file, width=150)
            except Exception as e:
                st.warning(f"❌ Upload failed: {e}")
        image_urls[opt] = ", ".join(urls) if urls else existing_urls.get(opt, "")

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
    rows = [["Key", "Label", "Image URLs"]] + [[k, v, image_urls.get(k, "")] for k, v in option_labels.items()]
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