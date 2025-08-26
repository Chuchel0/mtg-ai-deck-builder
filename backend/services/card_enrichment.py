import uuid
from typing import Optional

from sqlmodel import Session, select

from ..database.connection import engine
from ..database.models import ScryfallCardCache
from .scryfall_client import scryfall_client, ScryfallCard

# ======================================================================================
# Card Enrichment Service
# This service is responsible for fetching card data, using a database cache
# to avoid redundant API calls to Scryfall.
# ======================================================================================

def get_or_create_scryfall_card(
    card_name: str, 
    set_code: Optional[str] = None, 
    db_session: Session = None
) -> Optional[ScryfallCardCache]:
    """
    Retrieves a card's Scryfall data, first checking our local cache.
    If not in the cache, it fetches from the Scryfall API and saves the result.

    Args:
        card_name: The name of the card.
        set_code: (Optional) The specific set code for the card.
        db_session: The database session to use for the transaction.

    Returns:
        A ScryfallCardCache ORM object if the card is found, otherwise None.
    """
    
    # This pattern allows the function to be used with or without an existing session
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
    """The core logic, requiring an active session."""

    # 1. --- CACHE CHECK (The "Get" part) ---
    statement = select(ScryfallCardCache).where(ScryfallCardCache.name == card_name)
    if set_code:
        statement = statement.where(ScryfallCardCache.set_code == set_code)
    
    cached_card = session.exec(statement).first()

    if cached_card:
        print(f"CACHE HIT: Found '{card_name}' in the local database.")
        return cached_card

    # 2. --- API FETCH (The "Create" part) ---
    print(f"CACHE MISS: Searching Scryfall for '{card_name}'.")
    scryfall_card_data = scryfall_client.get_card_by_name(card_name, set_code)

    if not scryfall_card_data:
        # The card was not found by the Scryfall API
        return None

    # 3. --- DATABASE SAVE ---
    # Convert the Pydantic model from the client into SQLModel for the database.
    db_card = _convert_scryfall_to_db_model(scryfall_card_data)
    
    session.add(db_card)
    session.commit()
    session.refresh(db_card)
    
    print(f"SUCCESS: Saved '{db_card.name}' from set '{db_card.set_code.upper()}' to the cache.")
    return db_card


def _convert_scryfall_to_db_model(scryfall_card: ScryfallCard) -> ScryfallCardCache:
    """Helper function to map Scryfall API data to our database schema."""

    # Convert image URIs from Pydantic's HttpUrl to simple strings for JSON storage
    image_uris_dict = None
    if scryfall_card.image_uris:
        image_uris_dict = {k: str(v) for k, v in scryfall_card.image_uris.items()}

    # Create the database model instance
    return ScryfallCardCache(
        id=uuid.UUID(scryfall_card.id),  # Convert Scryfall's string UUID to a Python UUID object
        name=scryfall_card.name,
        oracle_text=scryfall_card.oracle_text,
        type_line=scryfall_card.type_line,
        mana_cost=scryfall_card.mana_cost,
        cmc=scryfall_card.cmc,
        rarity=scryfall_card.rarity,
        layout=scryfall_card.layout,
        colors=scryfall_card.colors,
        color_identity=scryfall_card.color_identity,
        keywords=scryfall_card.keywords,
        legalities=scryfall_card.legalities,
        image_uris=image_uris_dict,
        set_code=scryfall_card.set, # Map the 'set' field from Scryfall to 'set_code'
        collector_number=scryfall_card.collector_number,
    )