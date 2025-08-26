import uuid
from typing import List, Optional, Dict

from sqlmodel import Field, Relationship, SQLModel, Column
from sqlalchemy.dialects.sqlite import JSON

# ======================================================================================
# 1. Scryfall Card Cache Table
#    This table stores a local copy of all the rich card data that are fetch from Scryfall.
#    This is "source of truth" for card information.
#    The primary key is the Scryfall ID (a UUID) for a specific printing of a card.
# ======================================================================================

class ScryfallCardCache(SQLModel, table=True):
    # The unique Scryfall ID for this card printing
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)

    # Core card details
    name: str = Field(index=True)
    oracle_text: Optional[str] = None
    type_line: Optional[str] = None
    mana_cost: Optional[str] = None
    cmc: float = Field(default=0.0) # Converted Mana Cost / Mana Value
    rarity: str
    layout: str # e.g., 'normal', 'split', 'transform'

    # Relational link: one Scryfall card can be in many user collections
    user_cards: List["UserCard"] = Relationship(back_populates="scryfall_card")

    # JSON fields for storing complex, variable data from Scryfall
    colors: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))
    color_identity: List[str] = Field(sa_column=Column(JSON))
    keywords: List[str] = Field(sa_column=Column(JSON))
    legalities: Dict[str, str] = Field(sa_column=Column(JSON))
    image_uris: Optional[Dict[str, str]] = Field(default=None, sa_column=Column(JSON))
    
    # Reprint/versioning info
    set_code: str
    collector_number: str

# NOTE: A potential future improvement is to create a CardSet table.
# class CardSet(SQLModel, table=True):
#     code: str = Field(primary_key=True)
#     name: str
#     icon_svg_uri: str


# ======================================================================================
# 2. User Card Table
#    This table represents the actual cards a user owns, based on their CSV upload.
#    It links to the ScryfallCardCache table via a foreign key.
#    A `collection_id` groups all cards from a single upload session.
# ======================================================================================

class UserCard(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    quantity: int
    is_foil: bool = Field(default=False)
    
    # Session identifier for a given user's upload
    collection_id: str = Field(index=True)

    # Foreign key to the Scryfall data
    scryfall_card_id: uuid.UUID = Field(foreign_key="scryfallcardcache.id")
    
    # Relational link: a user card is one specific printing of a Scryfall card
    scryfall_card: ScryfallCardCache = Relationship(back_populates="user_cards")

    # Optional data from the user's CSV that (might want to keep)
    condition: Optional[str] = None
    language: Optional[str] = None
    purchase_price: Optional[float] = None
    purchase_price_currency: Optional[str] = None