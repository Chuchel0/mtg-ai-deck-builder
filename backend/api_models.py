"""
Pydantic models for API request and response validation.

This module defines the data structures used to validate the incoming request
bodies and to serialize the outgoing responses for the FastAPI endpoints.
Using Pydantic models ensures type safety, provides automatic data validation,
and is used by FastAPI to generate OpenAPI documentation.
"""

from typing import List, Optional
from pydantic import BaseModel, Field

# --- Chat Endpoint Models ---

class ChatRequest(BaseModel):
    """Defines the structure for a request to the /chat endpoint."""
    collection_id: Optional[str] = Field(
        None,
        description="The unique ID of the user's collection, if available.",
        examples=["a1b2c3d4-e5f6-7890-1234-567890abcdef"]
    )
    message: str = Field(
        ...,
        description="The user's message or query.",
        min_length=1,
        examples=["what is haste?"]
    )
    # This field will be expanded later to include conversation history.
    # history: List[Dict[str, str]] = []

class RuleSnippet(BaseModel):
    """Represents a single, relevant rule snippet returned by the RAG system."""
    rule_id: str = Field(..., description="The ID of the rule, e.g., '702.10a'.")
    text: str = Field(..., description="The text of the rule.")

class ChatResponse(BaseModel):
    """Defines the structure for a response from the /chat endpoint."""
    assistant_message: str = Field(
        ...,
        description="The text response from the AI assistant."
    )
    retrieved_rules: List[RuleSnippet] = Field(
        ...,
        description="A list of relevant rule snippets retrieved by the RAG system."
    )

# --- Collection Endpoint Models ---
# The models can be pre-define for the upcoming CSV upload endpoint.

class CollectionResponse(BaseModel):
    """Defines the response structure after a collection has been uploaded and processed."""
    collection_id: str = Field(..., description="The newly created unique ID for the collection.")
    message: str = Field(..., description="A summary message of the ingestion result.")
    total_rows: int
    successful_rows: int