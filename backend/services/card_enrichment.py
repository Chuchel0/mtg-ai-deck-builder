"""
Service layer for enriching card data with a database caching mechanism.

This service acts as an intermediary between the application and the Scryfall
client. It implements a read-through cache: before making an API call, it first
checks if the requested card data is already stored in the local database. If so,
it returns the cached data; otherwise, it fetches from the API, stores the result,
and then returns it.
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
    """
    Retrieves a card's data, utilizing a read-through database cache.

    This function can be called with an existing database session or it will create
    its own, making it flexible for use in different contexts.

    Args:
        card_name: The name of the card.
        set_code: The optional set code for a specific printing.
        db_session: An optional existing SQLModel Session to use.

    Returns:
        A `ScryfallCardCache` ORM instance if the card is found, else `None`.
    """
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
    # 1. Read from cache
    statement = select(ScryfallCardCache).where(ScryfallCardCache.name == card_name)
    if set_code:
        statement = statement.where(ScryfallCardCache.set_code == set_code)
    
    cached_card = session.exec(statement).first()
    if cached_card:
        print(f"CACHE HIT: Found '{card_name}' in local database.")
        return cached_card

    # 2. Fetch from API on cache miss
    print(f"CACHE MISS: Querying Scryfall API for '{card_name}'.")
    scryfall_card_data = scryfall_client.get_card_by_name(card_name, set_code)
    if not scryfall_card_data:
        return None

    # 3. Write to cache and return
    db_card = _convert_scryfall_to_db_model(scryfall_card_data)
    
    session.add(db_card)
    session.commit()
    session.refresh(db_card)
    
    print(f"CACHE WRITE: Saved '{db_card.name}' ({db_card.set_code.upper()}) to cache.")
    return db_card

def _convert_scryfall_to_db_model(scryfall_card: ScryfallCard) -> ScryfallCardCache:
    """Maps a ScryfallCard Pydantic model to a ScryfallCardCache SQLModel."""
    image_uris_dict = {k: str(v) for k, v in scryfall_card.image_uris.items()} if scryfall_card.image_uris else None

    return ScryfallCardCache(
        id=uuid.UUID(scryfall_card.id),
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
        set_code=scryfall_card.set,
        collector_number=scryfall_card.collector_number,
    )