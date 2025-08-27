"""
Defines the database schema using SQLModel.

This module contains the table definitions for the application, including the
cache for Scryfall card data and the user's personal card collection.
"""

import uuid
from typing import List, Optional, Dict
from sqlalchemy.dialects.sqlite import JSON
from sqlmodel import Field, Relationship, SQLModel, Column

class ScryfallCardCache(SQLModel, table=True):
    """
    Represents the local cache of enriched card data fetched from the Scryfall API.
    
    This table acts as the source of truth for all canonical card information,
    preventing redundant API calls. Each row corresponds to a unique printing
    of a Magic: The Gathering card.
    """
    # Scryfall's unique identifier for a specific card printing.
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    name: str = Field(index=True)
    oracle_text: Optional[str] = None
    type_line: Optional[str] = None
    mana_cost: Optional[str] = None
    cmc: float = Field(default=0.0) # Converted Mana Cost / Mana Value
    rarity: str
    layout: str

    # Back-populates the relationship to UserCard, allowing access to all user
    # collection entries that reference this specific Scryfall printing.
    user_cards: List["UserCard"] = Relationship(back_populates="scryfall_card")

    # Complex, variable-structure data is stored in JSON columns for flexibility.
    # `sa_column=Column(JSON)` ensures compatibility with SQLAlchemy's JSON type.
    colors: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))
    color_identity: List[str] = Field(sa_column=Column(JSON))
    keywords: List[str] = Field(sa_column=Column(JSON))
    legalities: Dict[str, str] = Field(sa_column=Column(JSON))
    image_uris: Optional[Dict[str, str]] = Field(default=None, sa_column=Column(JSON))
    
    # Card versioning information.
    set_code: str
    collector_number: str

class UserCard(SQLModel, table=True):
    """
    Represents a card within a user's uploaded collection.
    
    Each row corresponds to a line item from the user's CSV file, linking a
    quantity of a specific card printing to their collection.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    quantity: int
    is_foil: bool = Field(default=False)
    
    # A unique identifier for a single upload session, grouping all cards from one file.
    collection_id: str = Field(index=True)

    # Foreign key establishing a many-to-one relationship with the ScryfallCardCache table.
    scryfall_card_id: uuid.UUID = Field(foreign_key="scryfallcardcache.id")
    
    # Defines the Python-level relationship, allowing easy access to the full
    # card details via `user_card.scryfall_card`.
    scryfall_card: ScryfallCardCache = Relationship(back_populates="user_cards")

    # Optional fields imported from the user's CSV.
    condition: Optional[str] = None
    language: Optional[str] = None