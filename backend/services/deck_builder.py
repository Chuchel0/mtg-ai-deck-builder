"""
Service for the core deck-building logic.

This module contains the functions and heuristics for constructing a deck from a
user's collection based on a given set of specifications (format, colors, etc.).
"""

import random
import re
from collections import defaultdict
from typing import List, Dict, Set, Optional
from pydantic import BaseModel
from sqlmodel import Session, select

from ..database.connection import engine
from ..database.models import UserCard, ScryfallCardCache

# =============================================================================
# Data Models
# =============================================================================

class DeckSpec(BaseModel):
    """Defines the user's desired deck specifications (the 'blueprint')."""
    format: str = "commander"
    color_identity: Set[str] = {'W', 'B'}
    target_creatures: int = 25
    target_removal: int = 10
    target_ramp: int = 10
    target_draw: int = 8
    target_board_wipes: int = 2 # New target for our expanded roles
    target_lands: int = 37

class AnalyzedCard(BaseModel):
    """A richer representation of a card for deck building."""
    scryfall_id: str
    name: str
    quantity: int
    type_line: str
    oracle_text: Optional[str] = None
    mana_cost: Optional[str] = None
    color_identity: List[str]
    mana_value: float
    roles: List[str] = []

class Decklist(BaseModel):
    """Represents the final, constructed deck."""
    main_deck: Dict[str, int]
    sideboard: Dict[str, int]
    message: str

class DeckConstruction:
    """A stateful class to manage the deck building process."""
    def __init__(self, spec: DeckSpec, initial_pool: List[AnalyzedCard]):
        self.spec = spec
        self.main_deck: Dict[str, int] = {}
        self.available_pool: Dict[str, AnalyzedCard] = {c.name: c for c in initial_pool}
        self.role_counts: Dict[str, int] = defaultdict(int)
    
    @property
    def total_cards(self) -> int:
        return sum(self.main_deck.values())

    def add_card(self, card_name: str) -> bool:
        """Adds a card to the deck by its name, if possible, and updates state."""
        if card_name not in self.available_pool:
            return False
            
        card = self.available_pool[card_name]
        current_deck_qty = self.main_deck.get(card_name, 0)
        limit = 1 if self.spec.format == "commander" else 4
        
        if current_deck_qty >= limit or current_deck_qty >= card.quantity:
            return False

        self.main_deck[card_name] = current_deck_qty + 1
        for role in card.roles:
            self.role_counts[role] += 1
        return True

# =============================================================================
# Deck Building Pipeline
# =============================================================================

def _generate_basic_land_base(deck: DeckConstruction, pool: List[AnalyzedCard], lands_to_add: int) -> Dict[str, int]:
    """Generates a basic land base based on the color pips of spells in the deck."""
    pip_counts = defaultdict(int)
    card_map = {c.name: c for c in pool}
    
    for card_name, qty in deck.main_deck.items():
        card = card_map.get(card_name)
        if card and card.mana_cost:
            mana_symbols = re.findall(r'\{([WUBRG])\}', card.mana_cost, re.IGNORECASE)
            for symbol in mana_symbols:
                pip_counts[symbol.upper()] += qty

    total_pips = sum(pip_counts.values())
    if total_pips == 0:
        if deck.spec.color_identity:
             primary_color = list(deck.spec.color_identity)[0]
             land_map = {"W": "Plains", "U": "Island", "B": "Swamp", "R": "Mountain", "G": "Forest"}
             return {land_map[primary_color]: lands_to_add}
        return {"Wastes": lands_to_add}

    land_base = defaultdict(int)
    land_map = {"W": "Plains", "U": "Island", "B": "Swamp", "R": "Mountain", "G": "Forest"}
    
    temp_land_count = 0
    for color, count in pip_counts.items():
        ratio = count / total_pips
        num_lands = round(lands_to_add * ratio)
        land_name = land_map.get(color)
        if land_name:
            land_base[land_name] = num_lands
            temp_land_count += num_lands
            
    lands_diff = lands_to_add - temp_land_count
    while lands_diff != 0:
        if lands_diff > 0:
            most_needed_color = max(pip_counts, key=pip_counts.get)
            land_base[land_map[most_needed_color]] += 1
            lands_diff -= 1
        else:
            if any(land_base.values()): # Ensure we don't try to remove from an empty dict
                least_needed_color = min((c for c in pip_counts if land_base.get(land_map.get(c, ''), 0) > 0), key=pip_counts.get, default=None)
                if least_needed_color:
                    land_base[land_map[least_needed_color]] -= 1
                    lands_diff += 1
                else:
                    break # Break if no lands can be removed
            else:
                break
    
    return dict(land_base)

def score_card(card: AnalyzedCard, deck: DeckConstruction) -> float:
    """Calculates a heuristic score for a card based on the current deck state."""
    score = 1.0
    spec = deck.spec
    role_targets = {
        "removal": spec.target_removal, "ramp": spec.target_ramp,
        "draw": spec.target_draw, "threat": spec.target_creatures,
        "board_wipe": spec.target_board_wipes,
    }
    
    for role in card.roles:
        if role in role_targets:
            current_count = deck.role_counts[role]
            target_count = role_targets[role]
            if current_count < target_count:
                score += 10 * (1 - (current_count / target_count))
    
    if card.mana_value > 5:
        score -= (card.mana_value - 5) * 0.5
        
    return score

def build_deck(collection_id: str, spec: DeckSpec) -> Decklist:
    """The main entry point for the deck building pipeline."""
    with Session(engine) as session:
        buildable_pool = get_buildable_cards(collection_id, spec, db_session=session)
        if not buildable_pool:
            return Decklist(main_deck={}, sideboard={}, message="No buildable cards found.")

        deck = DeckConstruction(spec, buildable_pool)
        target_deck_size = 100 if spec.format == "commander" else 60
        non_land_target = target_deck_size - spec.target_lands

        while deck.total_cards < non_land_target:
            best_card_name = None
            best_score = -1.0
            
            for card_name, card in deck.available_pool.items():
                current_deck_qty = deck.main_deck.get(card_name, 0)
                limit = 1 if spec.format == "commander" else 4
                if current_deck_qty < card.quantity and current_deck_qty < limit:
                    if "land" not in card.roles:
                        current_score = score_card(card, deck)
                        if current_score > best_score:
                            best_score = current_score
                            best_card_name = card_name
            
            if best_card_name:
                deck.add_card(best_card_name)
            else:
                break
        
        lands_in_deck = {}
        for card in buildable_pool:
            if "land" in card.roles and card.name not in deck.main_deck:
                is_basic = any(lt in card.type_line.lower() for lt in ["plains", "island", "swamp", "mountain", "forest"])
                if not is_basic:
                    if sum(lands_in_deck.values()) < (spec.target_lands * 0.5):
                        deck.add_card(card.name)
                        lands_in_deck[card.name] = 1

        remaining_lands = spec.target_lands - len(lands_in_deck)
        if remaining_lands > 0:
            basic_land_base = _generate_basic_land_base(deck, buildable_pool, remaining_lands)
            deck.main_deck.update(basic_land_base)
        
        message = f"Deck built successfully with {deck.total_cards} cards!"
        if deck.total_cards != target_deck_size:
            message += f" WARNING: Final deck count is {deck.total_cards}, which is incorrect for the '{spec.format}' format."

        return Decklist(
            main_deck=deck.main_deck,
            sideboard={},
            message=message
        )

# =============================================================================
# Card Analysis and Filtering
# =============================================================================

def analyze_card_roles(card: AnalyzedCard) -> List[str]:
    """Assigns functional roles to a card based on its type and oracle text."""
    roles = set()
    type_line = card.type_line.lower()
    oracle_text = (card.oracle_text or "").lower()
    
    if "add" in oracle_text and ("{" in oracle_text or "mana" in oracle_text): roles.add("ramp")
    if "search your library for a basic land card" in oracle_text: roles.add("ramp")
    if re.search(r"\bdraw(s)?\b.*\bcard(s)?\b", oracle_text): roles.add("draw")
    if "search your library for a card" in oracle_text and "put it into your hand" in oracle_text: roles.add("tutor")
    
    if re.search(r"\bdestroy all creatures\b", oracle_text) or re.search(r"\bexile all creatures\b", oracle_text):
        roles.add("board_wipe")
        roles.add("removal")

    removal_patterns = [r"\bdestroy(s)?\b.*\btarget\b", r"\bexile(s)?\b.*\btarget\b", r"\bdeal(s)?\b.*\bdamage\b.*\bto any target\b", r"\bdeal(s)?\b.*\bdamage\b.*\btarget creature\b", r"\bfight(s)?\b.*\banother target creature\b"]
    if any(re.search(p, oracle_text) for p in removal_patterns): roles.add("removal")
    
    disruption_patterns = [r"\bcounter(s)?\b.*\btarget\b.*\bspell\b", r"target player.*discards"]
    if any(re.search(p, oracle_text) for p in disruption_patterns): roles.add("disruption")

    if re.search(r"\bgain(s)? hexproof\b", oracle_text) or re.search(r"\bgain(s)? indestructible\b", oracle_text):
        roles.add("protection")
        
    if re.search(r"creatures you control get \+\d+/\+\d+", oracle_text):
        roles.add("anthem")
    
    if "creature" in type_line: roles.add("threat")
    if "land" in type_line: roles.add("land")
    if not roles: roles.add("synergy")
    
    return sorted(list(roles))

def get_buildable_cards(collection_id: str, spec: DeckSpec, db_session: Session) -> List[AnalyzedCard]:
    """Filters a user's collection and analyzes each card for its roles."""
    statement = (select(UserCard, ScryfallCardCache).join(ScryfallCardCache).where(UserCard.collection_id == collection_id))
    results = db_session.exec(statement).all()
    
    buildable_pool: List[AnalyzedCard] = []
    spec_color_set = set(spec.color_identity)

    for user_card, scryfall_card in results:
        legality = scryfall_card.legalities.get(spec.format)
        if legality not in ["legal", "restricted"]: continue
        
        card_color_set = set(scryfall_card.color_identity)
        if not card_color_set.issubset(spec_color_set): continue

        temp_card_data = AnalyzedCard(
            scryfall_id=str(scryfall_card.id), name=scryfall_card.name, quantity=user_card.quantity,
            type_line=scryfall_card.type_line, oracle_text=scryfall_card.oracle_text, mana_cost=scryfall_card.mana_cost,
            color_identity=scryfall_card.color_identity, mana_value=scryfall_card.cmc,
        )
        card_roles = analyze_card_roles(temp_card_data)
        
        analyzed_card = AnalyzedCard(
            scryfall_id=str(scryfall_card.id), name=scryfall_card.name, quantity=user_card.quantity,
            type_line=scryfall_card.type_line, oracle_text=scryfall_card.oracle_text, mana_cost=scryfall_card.mana_cost,
            color_identity=scryfall_card.color_identity, mana_value=scryfall_card.cmc, roles=card_roles
        )
        buildable_pool.append(analyzed_card)
        
    print(f"Found and analyzed {len(buildable_pool)} unique buildable cards in the collection.")
    return buildable_pool