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
from .api_models import ChatRequest, ChatResponse, RuleSnippet

# =============================================================================
# Lifespan Management
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    An asynchronous context manager to handle application startup and shutdown events.-
    """
    print("Application startup: Initializing database...")
    create_db_and_tables()
    print("Database initialization complete.")
    
    yield
    
    print("Application shutdown.")

# =============================================================================
# API Router Definition
# =============================================================================

# Using an APIRouter helps organize endpoints, especially as the application grows.
# All endpoints defined on this router will be prefixed with `/api/v1`.
router = APIRouter(
    prefix="/api/v1",
    tags=["Deckbuilding & Chat"]
)

@router.post("/chat", response_model=ChatResponse)
async def handle_chat(request: ChatRequest):
    """
    Handles an incoming chat message.

    This endpoint performs a RAG query to find relevant rules based on the user's
    message and returns them. The actual LLM-based response generation is a
    placeholder for now.
    """
    print(f"Handling chat request. Message: '{request.message}'")

    # 1. Retrieve relevant rules from the vector database.
    retrieved_docs = rag_retriever.query(query_text=request.message, top_k=5)

    # 2. Format the retrieved documents into the API response model.
    rule_snippets = [
        RuleSnippet(rule_id=doc.rule_id, text=doc.text) for doc in retrieved_docs
    ]

    # 3. Create a placeholder response. The LLM integration will replace this.
    placeholder_response = (
        "I am a rule-lookup assistant. I am not yet connected to a large language model. "
        "Based on your query, I found the following potentially relevant rules:"
    )

    return ChatResponse(
        assistant_message=placeholder_response,
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

# Include the defined router in the main application.
app.include_router(router)

@app.get("/health", tags=["Status"])
def health_check():
    """A simple health check endpoint."""
    return {"status": "ok"}