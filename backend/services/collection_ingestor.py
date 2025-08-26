import csv
import io
import uuid
from typing import Dict, List

from pydantic import BaseModel
from sqlmodel import Session

from ..database.connection import engine
from ..database.models import UserCard
from .card_enrichment import get_or_create_scryfall_card

# ======================================================================================
# 1. Pydantic Model for Ingestion Results
#    This provides a structured way to report the outcome of the CSV processing.
# ======================================================================================

class IngestionResult(BaseModel):
    collection_id: str
    total_rows: int
    successful_rows: int
    failed_rows: int
    failures: List[str]

# ======================================================================================
# 2. The Main Ingestion Service
# ======================================================================================

def process_collection_csv(csv_file: io.BytesIO) -> IngestionResult:
    """
    Processes a user-uploaded CSV file of their MTG collection.

    - Reads the CSV data.
    - For each row, enriches the card data via Scryfall (using our cache).
    - Populates the `UserCard` table for the collection.
    - All cards in a single upload are grouped by a unique `collection_id`.

    Args:
        csv_file: A file-like object containing the CSV data (e.g., from a FastAPI UploadFile).

    Returns:
        An IngestionResult object summarizing the outcome.
    """
    # Decode the bytes file into a text stream that the csv module can read.
    # 'utf-8-sig' is used to handle the potential BOM (Byte Order Mark) in some CSVs.
    try:
        csv_text = csv_file.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(csv_text))
        rows = list(reader)
    except Exception as e:
        return IngestionResult(
            collection_id="", total_rows=0, successful_rows=0, failed_rows=0,
            failures=[f"Failed to read or parse CSV file: {e}"]
        )

    collection_id = str(uuid.uuid4())
    cards_to_add: List[UserCard] = []
    failures = []

    # Use a single database session for the entire ingestion process for efficiency.
    with Session(engine) as session:
        for i, row in enumerate(rows):
            row_num = i + 2  # Account for header row and 0-indexing for user feedback

            try:
                # 1. Parse and validate the data from the current CSV row.
                parsed_row = _parse_csv_row(row)

                # 2. Get the canonical Scryfall card data (from cache or API).
                #    Pass the existing session to avoid creating new ones for each card.
                scryfall_card = get_or_create_scryfall_card(
                    card_name=parsed_row["name"],
                    set_code=parsed_row["set_code"],
                    db_session=session
                )

                if not scryfall_card:
                    failures.append(f"Row {row_num}: Card '{parsed_row['name']}' not found on Scryfall.")
                    continue

                # 3. Create the UserCard object, linking it to the enriched Scryfall data.
                user_card = UserCard(
                    quantity=parsed_row["quantity"],
                    is_foil=parsed_row["is_foil"],
                    collection_id=collection_id,
                    scryfall_card_id=scryfall_card.id,
                    condition=parsed_row.get("condition"),
                    language=parsed_row.get("language"),
                )
                cards_to_add.append(user_card)

            except ValueError as e:
                failures.append(f"Row {row_num}: {e}")
            except Exception as e:
                failures.append(f"Row {row_num}: An unexpected error occurred: {e}")
        
        # 4. After processing all rows, add all new cards to the database in a single transaction.
        if cards_to_add:
            session.add_all(cards_to_add)
            session.commit()
            print(f"Successfully committed {len(cards_to_add)} card rows for collection '{collection_id}'.")

    return IngestionResult(
        collection_id=collection_id,
        total_rows=len(rows),
        successful_rows=len(cards_to_add),
        failed_rows=len(failures),
        failures=failures,
    )

def _parse_csv_row(row: Dict[str, str]) -> Dict:
    """
    Parses a single row from the CSV, handling case-insensitivity and data type conversion.
    Raises ValueError for missing or invalid required data.
    """
    # Normalize column headers (lowercase, strip whitespace) to handle variations.
    row = {str(k).strip().lower(): v for k, v in row.items()}
    
    card_name = row.get("name")
    if not card_name:
        raise ValueError("Missing required column 'Name'.")

    try:
        # Default to a quantity of 1 if the column is missing or empty.
        quantity = int(row.get("quantity") or 1)
    except (ValueError, TypeError):
        raise ValueError(f"Invalid quantity '{row.get('quantity')}' for card '{card_name}'. Must be a whole number.")

    # Get the set code and normalize it to lowercase to ensure consistent cache lookups.
    set_code = row.get("set code")
    if set_code:
        set_code = set_code.strip().lower()

    return {
        "name": card_name,
        "set_code": set_code, # Use the normalized set code
        "quantity": quantity,
        "is_foil": row.get("foil", "").lower() in ["foil", "true"],
        "condition": row.get("condition"),
        "language": row.get("language", "en"),
    }