"""
Service for processing user-uploaded card collection CSV files.

This module orchestrates the entire ingestion pipeline:
1. Reads and parses the CSV file.
2. For each row, normalizes the data.
3. Uses the `card_enrichment` service to get canonical card data.
4. Creates `UserCard` records in the database.
5. Groups all cards from one upload under a unique `collection_id`.
6. Reports a summary of the ingestion process, including any failures.
"""

import csv
import io
import uuid
from typing import Dict, List, Any
from pydantic import BaseModel
from sqlmodel import Session
from ..database.connection import engine
from ..database.models import UserCard
from .card_enrichment import get_or_create_scryfall_card

class IngestionResult(BaseModel):
    """A data structure to hold the results of a CSV ingestion process."""
    collection_id: str
    total_rows: int
    successful_rows: int
    failed_rows: int
    failures: List[str]

def process_collection_csv(csv_file: io.BytesIO) -> IngestionResult:
    """
    Processes a user-uploaded CSV file of their MTG collection.

    This function is transactional: all successful card entries are committed
    to the database at the end in a single operation. If an error occurs,
    failed rows are skipped, and the process continues.

    Args:
        csv_file: A file-like object (in bytes) containing the CSV data.

    Returns:
        An `IngestionResult` instance summarizing the outcome.
    """
    try:
        # The 'utf-8-sig' encoding handles CSVs that may have a Byte Order Mark (BOM).
        csv_text = csv_file.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(csv_text))
        rows = list(reader)
    except Exception as e:
        return IngestionResult(collection_id="", total_rows=0, successful_rows=0, failed_rows=0,
                               failures=[f"Fatal error reading CSV file: {e}"])

    collection_id = str(uuid.uuid4())
    cards_to_add: List[UserCard] = []
    failures = []

    with Session(engine) as session:
        for i, row in enumerate(rows):
            try:
                parsed_row = _parse_csv_row(row)
                scryfall_card = get_or_create_scryfall_card(
                    card_name=parsed_row["name"],
                    set_code=parsed_row["set_code"],
                    db_session=session
                )

                if not scryfall_card:
                    failures.append(f"Row {i+2}: Card '{parsed_row['name']}' not found on Scryfall.")
                    continue

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
                failures.append(f"Row {i+2}: {e}")
            except Exception as e:
                # Catch unexpected errors to prevent the entire process from crashing.
                failures.append(f"Row {i+2}: An unexpected error occurred: {e}")
        
        if cards_to_add:
            session.add_all(cards_to_add)
            session.commit()
            print(f"Committed {len(cards_to_add)} card rows for collection '{collection_id}'.")

    return IngestionResult(
        collection_id=collection_id,
        total_rows=len(rows),
        successful_rows=len(cards_to_add),
        failed_rows=len(failures),
        failures=failures,
    )

def _parse_csv_row(row: Dict[str, str]) -> Dict[str, Any]:
    """
    Normalizes and validates a single row from the CSV data.

    This function makes the parser resilient to common CSV issues like
    inconsistent header casing, whitespace, and missing optional values.

    Args:
        row: A dictionary representing one row from the CSV.

    Raises:
        ValueError: If required data is missing or in an invalid format.

    Returns:
        A cleaned dictionary with appropriate data types.
    """
    row = {str(k).strip().lower(): v.strip() for k, v in row.items()}
    
    card_name = row.get("name")
    if not card_name:
        raise ValueError("Missing required column 'Name'.")

    try:
        quantity = int(row.get("quantity") or 1)
    except (ValueError, TypeError):
        raise ValueError(f"Invalid quantity '{row.get('quantity')}'; must be a whole number.")

    set_code = row.get("set code") or row.get("set") # Handle both 'set code' and 'set'
    if set_code:
        set_code = set_code.lower()

    return {
        "name": card_name,
        "set_code": set_code,
        "quantity": quantity,
        "is_foil": row.get("foil", "").lower() in ["foil", "true"],
        "condition": row.get("condition"),
        "language": row.get("language", "en"),
    }