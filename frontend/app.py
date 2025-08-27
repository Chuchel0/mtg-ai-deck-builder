"""
The main entry point for the Streamlit web user interface.

This script initializes the Streamlit application, defines the page layout,
and creates the UI components for user interaction, such as the file uploader
and chat interface.
"""

import streamlit as st

# Configure the page settings for a better user experience.
st.set_page_config(
    page_title="MTG AI Deck Builder",
    page_icon="🤖",
    layout="wide"
)

# --- Main UI Layout ---

st.title("MTG AI Deck Builder 🤖 🃏")
st.write("Welcome! Upload a CSV of your collection to get started.")

# Placeholder for the file uploader component.
uploaded_file = st.file_uploader(
    "Choose a collection CSV file",
    type="csv",
    help="Export your collection from a tool like ManaBox and upload it here."
)

if uploaded_file is not None:
    # This block will execute when a file has been uploaded.
    # The logic to send the file to the backend API will be implemented here.
    st.success("File uploaded successfully! (Processing logic coming soon)")