import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import random
import zipfile
import tempfile
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
print(sys.executable)
from src.main import validate_invoices_in_directory

UPLOAD_DIR = "uploaded_pdfs"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# --- Dummy Data and Processing ---
def generate_dummy_data():
    data = {
        "HSN": ["997314", "0101", "0202", "0303", "0404"],
        "IGST": [random.randint(0, 50) for _ in range(5)],
        "CGST": [random.randint(0, 25) for _ in range(5)],
        "SGST": [random.randint(0, 25) for _ in range(5)],
    }
    return pd.DataFrame(data)

def generate_gst_plot(df):
    fig, ax = plt.subplots()
    df[["IGST", "CGST", "SGST"]].plot(kind="bar", ax=ax)
    ax.set_xticklabels(df["HSN"], rotation=0)
    ax.set_ylabel("GST Rate (%)")
    ax.set_title("GST Distribution by HSN")
    st.pyplot(fig)

def plot_pie_chart(data_dict, title="Pie Chart"):
    """
    Plots a pie chart from a dictionary of values.
    
    Args:
        data_dict (dict): keys are labels, values are numeric counts.
        title (str): chart title
    """
    labels = list(data_dict.keys())
    sizes = list(data_dict.values())
    
    # Optional: explode largest slice
    explode = [0.05 if s == max(sizes) else 0 for s in sizes]
    
    # Optional: colors
    colors = plt.cm.tab20.colors  # automatic palette
    
    # Create figure
    fig, ax = plt.subplots(figsize=(6,6))
    ax.pie(
        sizes,
        labels=labels,
        autopct="%1.1f%%",
        startangle=90,
        explode=explode,
        colors=colors[:len(labels)]
    )
    ax.set_title(title)
    
    # Display in Streamlit
    st.pyplot(fig)

def plot_pass_fail(title, passed, total):
    fail = total - passed
    pass_percent = (passed / total) * 100
    fail_percent = 100 - pass_percent

    fig, ax = plt.subplots(figsize=(3,3))  # smaller figure
    ax.pie(
        [pass_percent, fail_percent],
        labels=['Pass', 'Fail'],
        autopct='%1.1f%%',
        startangle=90,
        colors=['#4CAF50', '#F44336'],
        explode=(0.05, 0)
    )
    ax.set_title(title, fontsize=10)
    return fig

def detect_anomalies(df):
    anomalies = df[df["IGST"] > 30]
    anomalies["Note"] = "High IGST"
    return anomalies[["HSN", "IGST", "Note"]]

def extract_zip(zip_file):
    temp_dir = tempfile.mkdtemp()
    with zipfile.ZipFile(zip_file, "r") as zip_ref:
        zip_ref.extractall(temp_dir)
    return [os.path.join(temp_dir, f) for f in os.listdir(temp_dir)]

# --- Initialize Session State ---
for key in ["page", "uploaded_files", "chat_history"]:
    if key not in st.session_state:
        st.session_state[key] = None if key != "chat_history" else []

if st.session_state.page is None:
    st.session_state.page = "upload"

# --- Navigation Functions ---
def go_to(page):
    st.session_state.page = page
    st.rerun()

# --- Page: Upload ---
if st.session_state.page == "upload":
    st.title("📂 Upload Files or ZIP Folder")

    upload_type = st.radio("Choose upload type:", ["File(s)", "ZIP Folder"], horizontal=True)

    if upload_type == "File(s)":
        files = st.file_uploader("Upload one or more files", accept_multiple_files=True)
        if files:
            st.session_state.uploaded_files = files

        saved_paths = []

        if files:
            for pdf in files:
                save_path = os.path.join(UPLOAD_DIR, pdf.name)
                with open(save_path, "wb") as f:
                    f.write(pdf.read())
                saved_paths.append(save_path)
            st.success(f"Saved {len(saved_paths)} PDF(s) to {UPLOAD_DIR}")
    else:
        zip_file = st.file_uploader("Upload a ZIP file", type=["zip"])
        if zip_file:
            extracted = extract_zip(zip_file)
            st.session_state.uploaded_files = extracted

    if st.button("➡️ Go to Dashboard"):
        if st.session_state.uploaded_files:
            go_to("dashboard")
        else:
            st.warning("Please upload at least one file or folder.")

# --- Page: Dashboard ---
elif st.session_state.page == "dashboard":
    st.title("📊 Dashboard")

    # --- Floating Chat Button (fixed and visible) ---
    st.markdown(
    """
    <style>
    div.stButton > button:first-child {
        background-color: #4CAF50;
        color: white;
        border-radius: 50%;
        width: 60px;
        height: 60px;
        font-size: 28px;
        text-align: center;
        line-height: 60px;
        position: fixed;
        bottom: 25px;
        right: 25px;
        box-shadow: 2px 2px 6px rgba(0,0,0,0.3);
        cursor: pointer;
        transition: all 0.3s ease;
    }
    div.stButton > button:first-child:hover {
        background-color: #45a049;
        transform: scale(1.1);
    }
    </style>
    """,
    unsafe_allow_html=True
)

    # Native Streamlit button triggers navigation
    if st.button("💬"):
        st.session_state.page = "chat"
        st.rerun()


    if st.session_state.uploaded_files:
        st.success("Files successfully uploaded!")
        summary_data = validate_invoices_in_directory()
        total = summary_data['total_files']
        # plot_validition_pie_charts(file_statuses)
        # plot_pie_chart(data_summary, title="Invoice Validation Summary")
        st.header("Files Passed")
        col1, col2, col3 = st.columns(3)

        # Row 1
        with col1:
            st.pyplot(plot_pass_fail("Files Passed", summary_data['files_passed'], total))
        with col2:
            st.pyplot(plot_pass_fail("Grand Total Passed", summary_data['grand_total_passed'], total))
        with col3:
            st.pyplot(plot_pass_fail("Subtotal Passed", summary_data['subtotal_passed'], total))

        # Row 2
        col4, col5, col6 = st.columns(3)
        with col4:
            st.pyplot(plot_pass_fail("Tax Total Passed", summary_data['tax_total_passed'], total))
        with col5:
            st.pyplot(plot_pass_fail("Data Extraction Passed", summary_data['data_extraction_passed'], total))
        with col6:
            st.write("")
        # df = generate_dummy_data()
        # generate_gst_plot(df)

        st.subheader("🔍 Anomalies Detected")
        # st.dataframe(detect_anomalies(df))
    else:
        st.warning("No file uploaded yet. Please go back and upload a file.")
        if st.button("⬅️ Back to Upload"):
            go_to("upload")

# --- Page: Chat ---
elif st.session_state.page == "chat":
    st.title("💬 Chat Assistant")

    if st.button("⬅️ Back to Dashboard"):
        go_to("dashboard")

    st.markdown("---")
    st.subheader("Chat with the assistant")

    # Display existing chat history
    for entry in st.session_state.chat_history:
        role = entry["role"]
        msg = entry["message"]
        if role == "user":
            st.markdown(f"🧑 **You:** {msg}")
        else:
            st.markdown(f"🤖 **Bot:** {msg}")

    # Input box for message
    user_input = st.text_input("Type your message here...")
    if st.button("Send") or (user_input != "" and st.session_state.get("user_input_last","") != user_input):
        if user_input.strip():
            st.session_state.chat_history.append({"role":"user","message":user_input})
            st.session_state.chat_history.append({"role":"bot","message":f"Echo: {user_input}"})
            st.session_state.user_input = ""   # clears the input
            st.session_state.user_input_last = ""
    st.session_state.user_input_last = user_input


