"""
Main entry point for the FastAPI application.

This module initializes the FastAPI app, sets up lifespan events for database
initialization, and defines the core API endpoints by including modular routers.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter

# --- Application Service Imports ---
from .database.connection import create_db_and_tables
from .services.rag_retriever import rag_retriever
from .services.llm_provider import llm_provider  # Import the new LLM provider
from .api_models import ChatRequest, ChatResponse, RuleSnippet

# =============================================================================
# Constants
# =============================================================================

# This system prompt defines the persona and instructions for the LLM.
SYSTEM_PROMPT = """You are an expert Magic: The Gathering judge and deckbuilding assistant. Your persona is helpful, clear, and precise.

Your primary function is to answer user questions about MTG rules.

**Instructions:**
1.  Use the "RELEVANT RULES" provided below as the absolute source of truth. Do not use any prior knowledge.
2.  Answer the user's question directly and concisely based *only* on the provided rules.
3.  For every piece of information you provide, you **MUST** end the sentence with a citation of the exact rule number it came from.
4.  The citation format is a rule number in square brackets, like this: `[702.19b]`.
5.  If the provided rules do not contain enough information to answer the question, you must explicitly say: "Based on the provided rules, I cannot answer that question with certainty."
6.  Do not add any conversational fluff or introductory phrases like "According to the rules...". Answer the question directly.
"""

# =============================================================================
# Lifespan Management
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """An asynchronous context manager to handle application startup and shutdown events."""
    print("Application startup: Initializing database...")
    create_db_and_tables()
    print("Database initialization complete.")
    
    yield
    
    print("Application shutdown.")

# =============================================================================
# API Router Definition
# =============================================================================

router = APIRouter(
    prefix="/api/v1",
    tags=["Deckbuilding & Chat"]
)

@router.post("/chat", response_model=ChatResponse)
async def handle_chat(request: ChatRequest):
    """
    Handles an incoming chat message, generates a response using a RAG-enhanced LLM.

    This endpoint orchestrates the full RAG pipeline:
    1. Retrieves relevant rule documents from the ChromaDB vector store.
    2. Constructs a detailed prompt including the user's message and the retrieved context.
    3. Sends the prompt to a local LLM via the LLMProvider to generate a response.
    4. Returns the generated response along with the source rule snippets for citation.
    """
    print(f"Handling chat request. Message: '{request.message}'")

    # 1. Retrieve relevant rule documents.
    retrieved_docs = rag_retriever.query(query_text=request.message, top_k=5)
    
    # Extract the text from the retrieved documents for the LLM context.
    context_rules_text = [doc.text for doc in retrieved_docs]
    
    # 2. Generate a context-aware response from the LLM.
    assistant_response = llm_provider.generate_response(
        system_prompt=SYSTEM_PROMPT,
        user_message=request.message,
        context_rules=context_rules_text
    )

    # 3. Format the retrieved documents for the API response.
    rule_snippets = [
        RuleSnippet(rule_id=doc.rule_id, text=doc.text) for doc in retrieved_docs
    ]

    return ChatResponse(
        assistant_message=assistant_response,
        retrieved_rules=rule_snippets
    )

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
def health_check():
    """A simple health check endpoint."""
    return {"status": "ok"}