"""
Main entry point for the FastAPI application.
"""
import re
from contextlib import asynccontextmanager
from typing import List
from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse

# --- Application Service Imports ---
from .database.connection import create_db_and_tables
from .services.rag_retriever import rag_retriever
from .services.llm_provider import llm_provider
from .services.collection_ingestor import process_collection_csv
from .services.deck_builder import build_deck # New import
from .api_models import (
    ChatRequest, ChatResponse, RuleSnippet, CollectionResponse,
    DeckSpec, Decklist, BuildDeckRequest, GenerateSpecRequest # New imports
)

# ... (SYSTEM_PROMPT and lifespan are the same as the last version) ...
SYSTEM_PROMPT = """You are JudgeBot, an expert Magic: The Gathering judge and AI assistant. Your goal is to provide comprehensive, accurate, and easy-to-understand answers to player questions.
**Your Persona:** You are a helpful and knowledgeable judge. You should be conversational but precise.
**Your Process:**
1.  **Analyze the User's Question:** Deeply understand the user's intent.
2.  **Formulate a Comprehensive Answer:** Start with a direct answer. Then, explain the reasoning by synthesizing information from the RELEVANT RULES provided in the context.
3.  **Grounding and Citation:** Your entire answer **MUST** be based *only* on the information in the provided rules. At the end of your entire response, list the primary rule numbers you used under a "Relevant Rules:" heading. Example: `Relevant Rules: [702.19b], [702.12b]`.
**Crucial Constraint:** If the rules don't contain enough information, you **MUST** state: "Based on the rules I have, I can't answer that with certainty." Do not invent information.
"""

DECK_SPEC_PROMPT = """You are a master deckbuilder AI. Your task is to analyze a user's conversation and their high-level deck request, and translate it into a precise JSON DeckSpec object.

**Constraints:**
- The format must be one of: "commander", "modern", "standard", "pioneer".
- The color_identity must be a list of color codes: "W", "U", "B", "R", "G".
- Base the target counts on established deck-building principles for the given format and strategy. Aggressive decks have more creatures and a lower land count. Control decks have fewer creatures, more draw/removal, and more lands.
- The output MUST be a valid JSON object that conforms to the DeckSpec model. Do not include any other text, explanation, or markdown formatting.

**Example:**
- **User prompt:** "build me an aggressive Selesnya +1/+1 counters deck for Modern"
- **Your JSON Output:**
{
  "format": "modern",
  "color_identity": ["W", "G"],
  "target_creatures": 28,
  "target_removal": 8,
  "target_ramp": 4,
  "target_draw": 2,
  "target_board_wipes": 0,
  "target_lands": 22
}
"""

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Application startup...")
    create_db_and_tables()
    print("Initialization complete.")
    yield
    print("Application shutdown.")

# =============================================================================
# API Router Definition
# =============================================================================
router = APIRouter(prefix="/api/v1")

# --- Endpoints ---

@router.post("/collections/upload", response_model=CollectionResponse, tags=["Collection Management"])
async def handle_collection_upload(file: UploadFile = File(...)):
    # ... (This endpoint is unchanged) ...
    if not file.filename or not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Please upload a CSV file.")
    try:
        result = process_collection_csv(file.file)
        if result.failed_rows > 0 and result.successful_rows == 0:
            raise HTTPException(status_code=422, detail=f"Failed to process CSV. First error: {result.failures[0]}")
        return CollectionResponse(collection_id=result.collection_id, message=f"Ingested {result.successful_rows}/{result.total_rows} rows.", total_rows=result.total_rows, successful_rows=result.successful_rows)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/chat", tags=["AI Assistant"])
async def handle_chat(request: ChatRequest):
    # ... (This endpoint is unchanged) ...
    initial_results = rag_retriever.query(query_text=request.message, top_k=7)
    # ... (rest of the implementation is the same) ...

# --- NEW: Deck Building Endpoint ---
@router.post("/decks/build", response_model=Decklist, tags=["Deck Builder"])
async def handle_build_deck(request: BuildDeckRequest):
    """
    Takes a collection ID and a deck specification and builds a deck using the
    heuristic algorithm.
    """
    print(f"Received deck build request for collection: {request.collection_id}")
    try:
        # Call the core deck building logic from our service.
        decklist = build_deck(collection_id=request.collection_id, spec=request.spec)
        return decklist
    except Exception as e:
        print(f"ERROR during deck construction: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred while building the deck.")

@router.post("/decks/generate-spec", response_model=DeckSpec, tags=["Deck Builder"])
async def handle_generate_spec(request: GenerateSpecRequest):
    """
    Uses the LLM to parse a conversation and generate a structured DeckSpec.
    """
    # We will format the chat history for the LLM
    conversation = "\n".join([f"{msg['role']}: {msg['content']}" for msg in request.chat_history])
    user_prompt = f"Here is our conversation about the deck I want to build:\n\n{conversation}\n\nPlease generate the JSON DeckSpec for this deck."

    # Use the non-streaming provider for a single JSON response
    # We will need to add a non-streaming method to our LLMProvider
    json_response = llm_provider.generate_json_response(DECK_SPEC_PROMPT, user_prompt)
    
    # Validate the response with Pydantic
    try:
        spec = DeckSpec.parse_raw(json_response)
        return spec
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI failed to generate a valid DeckSpec JSON. Error: {e}")

# =============================================================================
# Main FastAPI Application
# =============================================================================
app = FastAPI(
    title="MTG AI Deck Builder API",
    description="API for ingesting MTG collections, managing card data, and building decks.",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(router)
@app.get("/health", tags=["Status"])
def health_check(): return {"status": "ok"}