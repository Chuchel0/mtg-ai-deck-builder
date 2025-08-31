"""
Service layer for enriching card data with a database caching mechanism.
"""
import uuid
from typing import Optional
from sqlmodel import Session, select
from ..database.connection import engine
from ..database.models import ScryfallCardCache
from .scryfall_client import scryfall_client, ScryfallCard

def get_or_create_scryfall_card(
    card_name: str, 
    set_code: Optional[str] = None, 
    db_session: Optional[Session] = None
) -> Optional[ScryfallCardCache]:
    """Retrieves a card's data, utilizing a read-through database cache."""
    if db_session:
        return _get_or_create(card_name, set_code, db_session)
    else:
        with Session(engine) as session:
            return _get_or_create(card_name, set_code, session)

def _get_or_create(
    card_name: str, 
    set_code: Optional[str], 
    session: Session
) -> Optional[ScryfallCardCache]:
    """Core caching logic that requires an active database session."""
    statement = select(ScryfallCardCache).where(ScryfallCardCache.name == card_name)
    if set_code:
        statement = statement.where(ScryfallCardCache.set_code == set_code)
    
    cached_card = session.exec(statement).first()
    if cached_card:
        # --- NEW: Check if the cached card has our new quality data ---
        # If not, we'll proceed to fetch it. This allows for graceful upgrades.
        if cached_card.edhrec_rank is not None:
            print(f"CACHE HIT: Found '{card_name}' in local database.")
            return cached_card
        print(f"CACHE UPDATE: Found '{card_name}' but missing quality metrics. Refetching.")

    scryfall_card_data = scryfall_client.get_card_by_name(card_name, set_code)
    if not scryfall_card_data:
        return None

    # If we are updating an existing entry, use the one we found.
    # Otherwise, create a new one.
    db_card = cached_card or _convert_scryfall_to_db_model(scryfall_card_data)
    
    # Update the fields with the latest data
    _update_db_model_from_scryfall(db_card, scryfall_card_data)
    
    session.add(db_card)
    session.commit()
    session.refresh(db_card)
    
    print(f"CACHE WRITE/UPDATE: Saved '{db_card.name}' ({db_card.set_code.upper()}) to cache.")
    return db_card

def _convert_scryfall_to_db_model(scryfall_card: ScryfallCard) -> ScryfallCardCache:
    """Helper function to map Scryfall API data to our database schema for a new card."""
    return ScryfallCardCache(id=uuid.UUID(scryfall_card.id))

def _update_db_model_from_scryfall(db_card: ScryfallCardCache, scryfall_card: ScryfallCard):
    """Updates a ScryfallCardCache instance with fresh data from a ScryfallCard model."""
    image_uris_dict = {k: str(v) for k, v in scryfall_card.image_uris.items()} if scryfall_card.image_uris else None
    
    db_card.name = scryfall_card.name
    db_card.oracle_text = scryfall_card.oracle_text
    db_card.type_line = scryfall_card.type_line
    db_card.mana_cost = scryfall_card.mana_cost
    db_card.cmc = scryfall_card.cmc
    db_card.rarity = scryfall_card.rarity
    db_card.layout = scryfall_card.layout
    db_card.colors = scryfall_card.colors
    db_card.color_identity = scryfall_card.color_identity
    db_card.keywords = scryfall_card.keywords
    db_card.legalities = scryfall_card.legalities
    db_card.image_uris = image_uris_dict
    db_card.set_code = scryfall_card.set
    db_card.collector_number = scryfall_card.collector_number
    
    # --- NEW: Populate card quality metrics ---
    db_card.edhrec_rank = scryfall_card.edhrec_rank
    db_card.price_usd = scryfall_card.prices.get("usd") if scryfall_card.prices else None