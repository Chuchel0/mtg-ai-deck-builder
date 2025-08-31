"""
Pydantic models for API request and response validation.
"""
from typing import List, Optional, Set, Dict
from pydantic import BaseModel, Field

# =============================================================================
# API-facing Deck Building Models
# =============================================================================

class DeckSpec(BaseModel):
    """
    Defines the user's desired deck specifications (the 'blueprint').
    This is the input for the deck building engine.
    """
    format: str = Field("commander", examples=["commander", "modern", "standard"])
    color_identity: Set[str] = Field(..., examples=[{"W", "B"}, {"G"}])
    target_creatures: int = Field(25, ge=0)
    target_removal: int = Field(10, ge=0)
    target_ramp: int = Field(10, ge=0)
    target_draw: int = Field(8, ge=0)
    target_board_wipes: int = Field(2, ge=0)
    target_lands: int = Field(37, ge=0)

class Decklist(BaseModel):
    """

    Represents the final, constructed deck.
    This is the output of the deck building engine.
    """
    main_deck: Dict[str, int] # Card Name -> Quantity
    sideboard: Dict[str, int]
    message: str

class BuildDeckRequest(BaseModel):
    """Defines the structure for a request to the /decks/build endpoint."""
    collection_id: str
    spec: DeckSpec

class GenerateSpecRequest(BaseModel):
    """Defines the structure for a request to generate a deck spec."""
    chat_history: List[Dict[str, str]] # e.g., [{"role": "user", "content": "..."}, ...]
    collection_id: str

# =============================================================================
# AI and Collection Models
# =============================================================================

class ChatRequest(BaseModel):
    """Defines the structure for a rule search request."""
    collection_id: Optional[str] = None
    message: str = Field(..., min_length=1)

class RuleSnippet(BaseModel):
    """Represents a single, relevant rule snippet."""
    rule_id: str
    text: str

class ChatResponse(BaseModel):
    """Defines the structure for a response that includes an AI message."""
    assistant_message: str
    retrieved_rules: List[RuleSnippet]

class CollectionResponse(BaseModel):
    """Defines the response structure after a collection has been uploaded."""
    collection_id: str
    message: str
    total_rows: int
    successful_rows: int