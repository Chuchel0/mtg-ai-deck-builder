"""
A robust client for interacting with the Scryfall API.

This module provides a class-based client for fetching card data from Scryfall.
It includes features such as automatic retries for transient network errors,
adherence to Scryfall's requested API rate limits, and data validation using
Pydantic models to ensure the received data conforms to expectations.
"""

import time
import requests
from typing import List, Dict, Optional
from pydantic import BaseModel, Field, HttpUrl
from tenacity import retry, stop_after_attempt, wait_exponential

# --- Constants ---
SCRYFALL_API_BASE_URL = "https://api.scryfall.com"
# Scryfall's API guidelines request a 50-100ms delay between requests.
SCRYFALL_REQUEST_DELAY_SECONDS = 0.1
# --- End Constants ---

# --- Pydantic Models for API Response Validation ---

class ScryfallCardFace(BaseModel):
    """Represents a single face of a multi-faced card (e.g., MDFC, Transform)."""
    name: str
    mana_cost: str
    type_line: str
    oracle_text: Optional[str] = None
    colors: Optional[List[str]] = None

class ScryfallCard(BaseModel):
    """A Pydantic model to validate and structure card data from Scryfall API responses."""
    id: str
    name: str
    lang: str
    oracle_text: Optional[str] = None
    mana_cost: Optional[str] = None
    cmc: float
    type_line: str
    colors: Optional[List[str]] = None
    color_identity: List[str]
    keywords: List[str]
    legalities: Dict[str, str]
    rarity: str
    set: str
    collector_number: str
    layout: str
    image_uris: Optional[Dict[str, HttpUrl]] = None
    card_faces: Optional[List[ScryfallCardFace]] = None
    edhrec_rank: Optional[int] = None
    prices: Optional[Dict[str, Optional[str]]] = None

# --- API Client ---

class ScryfallClient:
    """A client for the Scryfall API with built-in retries and rate limiting."""

    def __init__(self, base_url: str = SCRYFALL_API_BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Internal method to execute a GET request with resilience.
        
        This method automatically retries on transient errors and respects the
        API rate limit. It returns None for 404 Not Found errors and raises
        exceptions for other HTTP errors to trigger the retry logic.
        """
        time.sleep(SCRYFALL_REQUEST_DELAY_SECONDS)
        
        try:
            response = self.session.get(f"{self.base_url}/{endpoint}", params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                print(f"Scryfall API: Resource not found for endpoint '{endpoint}' with params {params}")
                return None
            print(f"Scryfall API: HTTP error occurred: {e}")
            raise
        except requests.exceptions.RequestException as e:
            print(f"Scryfall API: A request error occurred: {e}")
            raise

    def get_card_by_name(self, card_name: str, set_code: Optional[str] = None) -> Optional[ScryfallCard]:
        """
        Fetches a single card from Scryfall using their fuzzy name search endpoint.

        Args:
            card_name: The name of the card to search for.
            set_code: An optional set code to narrow the search to a specific printing.

        Returns:
            A validated `ScryfallCard` model instance if found, otherwise `None`.
        """
        params = {"fuzzy": card_name}
        if set_code:
            params["set"] = set_code
            
        print(f"Querying Scryfall API for card: '{card_name}' (Set: {set_code or 'Any'})")
        
        card_data = self._make_request("cards/named", params=params)
        return ScryfallCard.parse_obj(card_data) if card_data else None

# A singleton instance of the client for convenient access across the application.
scryfall_client = ScryfallClient()