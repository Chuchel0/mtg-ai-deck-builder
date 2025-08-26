import streamlit as st

st.set_page_config(
    page_title="MTG AI Deck Builder",
    layout="wide"
)

st.title("MTG AI Deck Builder  ")
st.write("Welcome! The frontend is up and running.")

# Placeholder for future functionality
st.info("Upload your ManaBox CSV to get started.")
uploaded_file = st.file_uploader("Choose a CSV file", type="csv")
if uploaded_file is not None:
    st.success("File uploaded successfully! (Processing logic coming soon)")
