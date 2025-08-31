"""
The main entry point for the Streamlit web user interface.
"""
import streamlit as st
import requests
from collections import defaultdict

# --- Configuration ---
BACKEND_URL = "http://localhost:8000/api/v1"
# Pre-defined colors for UI consistency
COLORS = {"W": "White", "U": "Blue", "B": "Black", "R": "Red", "G": "Green"}

FORMAT_DEFAULTS = {
    "commander": {"lands": (30, 50, 37), "creatures": (15, 40, 25)},
    "modern": {"lands": (18, 28, 24), "creatures": (10, 35, 20)},
    "standard": {"lands": (20, 28, 25), "creatures": (10, 35, 22)},
    "pioneer": {"lands": (20, 28, 24), "creatures": (10, 35, 22)},
}

# --- Page Setup ---
st.set_page_config(
    page_title="MTG AI Deck Builder",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Session State Initialization ---
if 'collection_id' not in st.session_state: st.session_state.collection_id = None
if 'upload_summary' not in st.session_state: st.session_state.upload_summary = ""
if 'upload_error' not in st.session_state: st.session_state.upload_error = ""
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Welcome! Ask me any MTG rules question, or upload your collection to start building a deck."}
    ]
# NEW: Session state to hold the generated decklist
if "decklist" not in st.session_state:
    st.session_state.decklist = None

# =============================================================================
# UI Components
# =============================================================================

# --- Sidebar ---
with st.sidebar:
    st.header("Your Collection")
    st.write("Upload your collection to enable the deck builder.")
    with st.form("upload_form", clear_on_submit=True):
        uploaded_file = st.file_uploader("Upload collection CSV", type="csv", label_visibility="collapsed")
        submitted = st.form_submit_button("Process Collection")
        if submitted and uploaded_file is not None:
            with st.spinner("Processing your collection..."):
                files = {"file": (uploaded_file.name, uploaded_file, "text/csv")}
                try:
                    res = requests.post(f"{BACKEND_URL}/collections/upload", files=files, timeout=600)
                    if res.status_code == 200:
                        data = res.json()
                        st.session_state.collection_id = data.get("collection_id")
                        st.session_state.upload_summary = data.get("message")
                        st.session_state.upload_error = ""
                        st.session_state.messages = [{"role": "assistant", "content": f"Collection loaded! {st.session_state.upload_summary} Let's build a deck! What are you thinking of?"}]
                        st.session_state.decklist = None # Clear old decklist on new upload
                    else:
                        st.session_state.upload_error = f"Error: {res.status_code} - {res.text}"
                except requests.exceptions.RequestException as e:
                    st.session_state.upload_error = f"Connection Error: {e}"
    
    if st.session_state.upload_summary:
        st.success(st.session_state.upload_summary)
        st.info(f"Active Collection ID: `{st.session_state.collection_id}`")
    if st.session_state.upload_error:
        st.error(st.session_state.upload_error)

# --- Main Content Area ---
st.title("MTG AI Deck Builder 🤖 🃏")

# The Chat is always visible at the top.
st.header("Chat with JudgeBot")
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ask a rules question or describe your deck..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        def stream_response():
            try:
                with requests.post(
                    f"{BACKEND_URL}/chat", 
                    json={"message": prompt, "collection_id": st.session_state.collection_id}, 
                    stream=True, timeout=120
                ) as r:
                    r.raise_for_status()
                    for chunk in r.iter_content(chunk_size=None, decode_unicode=True):
                        yield chunk
            except requests.exceptions.RequestException as e:
                yield f"Error contacting the backend: {e}"
        
        response_text = st.write_stream(stream_response)
        st.session_state.messages.append({"role": "assistant", "content": response_text})

st.divider()
st.header("Deck Builder")

if st.session_state.collection_id:
    st.write("Use the controls below to define your deck, or describe it in the chat and let the AI fill them out for you (coming soon!).")
    
    # --- Deck Specification Controls ---
    with st.form("deck_spec_form"):
        st.subheader("Deck Blueprint")
        
        col1, col2 = st.columns(2)
        with col1:
            format = st.selectbox("Format", ["commander", "modern", "standard", "pioneer"], index=0)
            color_identity = st.multiselect(
                "Color Identity",
                options=COLORS.keys(),
                format_func=lambda x: COLORS[x],
                default=["W", "B"]
            )

        defaults = FORMAT_DEFAULTS.get(format, FORMAT_DEFAULTS["modern"])
        land_min, land_max, land_default = defaults["lands"]
        creature_min, creature_max, creature_default = defaults["creatures"]
        
        with col2:
            target_lands = st.slider("Number of Lands", land_min, land_max, land_default)
            target_creatures = st.slider("Number of Creatures", creature_min, creature_max, creature_default)
        
        st.write("Fine-tune role targets:")
        col3, col4, col5 = st.columns(3)
        with col3:
            target_ramp = st.slider("Ramp Spells", 0, 20, 10)
        with col4:
            target_removal = st.slider("Removal Spells", 0, 20, 10)
        with col5:
            target_draw = st.slider("Card Draw Spells", 0, 20, 8)

        build_button = st.form_submit_button("Build Deck", use_container_width=True)

    if build_button:
        # --- API Call to Build Deck ---
        spec = {
            "format": format,
            "color_identity": color_identity,
            "target_lands": target_lands,
            "target_creatures": target_creatures,
            "target_ramp": target_ramp,
            "target_removal": target_removal,
            "target_draw": target_draw,
            "target_board_wipes": 2 # Hardcoded for now, can be a slider later
        }
        
        payload = {
            "collection_id": st.session_state.collection_id,
            "spec": spec
        }
        
        with st.spinner("Building your deck... The algorithm is at work!"):
            try:
                res = requests.post(f"{BACKEND_URL}/decks/build", json=payload, timeout=120)
                if res.status_code == 200:
                    st.session_state.decklist = res.json()
                else:
                    st.error(f"Error building deck: {res.status_code} - {res.text}")
            except requests.exceptions.RequestException as e:
                st.error(f"Connection Error: {e}")

    # --- Decklist Display ---
    if st.session_state.decklist:
        st.divider()
        st.subheader("Generated Decklist")
        
        deck = st.session_state.decklist["main_deck"]
        total_cards = sum(deck.values())
        
        st.info(st.session_state.decklist["message"])

        # Group cards for display
        lands = {n: q for n, q in deck.items() if n in ["Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes", "Command Tower"]}
        spells = {n: q for n, q in deck.items() if n not in lands}
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric(label="Total Cards", value=total_cards)
            st.write("**Spells**")
            # Convert to a list for nice display
            spell_list = [f"{qty}x {name}" for name, qty in sorted(spells.items())]
            st.text("\n".join(spell_list))
        with col2:
            st.metric(label="Total Lands", value=sum(lands.values()))
            st.write("**Lands**")
            land_list = [f"{qty}x {name}" for name, qty in sorted(lands.items())]
            st.text("\n".join(land_list))

else:
    st.info("Upload your collection in the sidebar to activate the deck builder.")