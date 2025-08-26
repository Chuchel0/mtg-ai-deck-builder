import time
import requests
from typing import List, Dict, Optional
from pydantic import BaseModel, Field, HttpUrl
from tenacity import retry, stop_after_attempt, wait_exponential

# ======================================================================================
# 1. Constants and Configuration
# ======================================================================================

SCRYFALL_API_BASE_URL = "https://api.scryfall.com"
SCRYFALL_REQUEST_DELAY_SECONDS = 0.1

# ======================================================================================
# 2. Pydantic Models for Scryfall API Response
#    These models help validate and type-hint the complex JSON from Scryfall.
# ======================================================================================

class ScryfallCardFace(BaseModel):
    """Represents a single face of a multi-faced card."""
    name: str
    mana_cost: str
    type_line: str
    oracle_text: Optional[str] = None
    colors: Optional[List[str]] = None

class ScryfallCard(BaseModel):
    """Represents the main structure of a card object from the Scryfall API."""
    id: str  # This is a UUID string from Scryfall
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
    set: str = Field(..., alias="set") # 'set' is the set code
    collector_number: str
    layout: str
    image_uris: Optional[Dict[str, HttpUrl]] = None
    card_faces: Optional[List[ScryfallCardFace]] = None # For multi-faced cards


# ======================================================================================
# 3. The Scryfall API Client Class
# ======================================================================================

class ScryfallClient:
    """A client for interacting with the Scryfall API with built-in retries and delays."""

    def __init__(self, base_url: str = SCRYFALL_API_BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Internal method to make a request to the Scryfall API.
        Includes error handling, retries, and the mandatory delay.
        """
        time.sleep(SCRYFALL_REQUEST_DELAY_SECONDS)
        
        try:
            response = self.session.get(f"{self.base_url}/{endpoint}", params=params)
            response.raise_for_status()  # Raises an HTTPError for bad responses (4xx or 5xx)
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                print(f"Scryfall API: Card not found for params {params}")
                return None
            print(f"Scryfall API: HTTP error occurred: {e}")
            raise # Re-raise the exception for other HTTP errors to trigger a retry
        except requests.exceptions.RequestException as e:
            print(f"Scryfall API: A request error occurred: {e}")
            raise # Re-raise to trigger a retry

    def get_card_by_name(self, card_name: str, set_code: Optional[str] = None) -> Optional[ScryfallCard]:
        """
        Fetches a single card from Scryfall by its name using fuzzy search.
        
        Args:
            card_name: The name of the card to search for.
            set_code: (Optional) A specific set code to narrow the search.
        
        Returns:
            A ScryfallCard Pydantic model if the card is found, otherwise None.
        """
        params = {"fuzzy": card_name}
        if set_code:
            params["set"] = set_code
            
        print(f"Querying Scryfall for card: {card_name} (Set: {set_code or 'Any'})")
        
        card_data = self._make_request("cards/named", params=params)
        
        if card_data:
            return ScryfallCard.parse_obj(card_data)
        
        return None

# A global instance of the client for use in other modules
scryfall_client = ScryfallClient()