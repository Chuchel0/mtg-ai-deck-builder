"""
A service for retrieving relevant documents from the ChromaDB vector store.
"""

import sys
import re
from pathlib import Path
from typing import List, Dict
import chromadb
from chromadb.utils import embedding_functions
from pydantic import BaseModel, Field

# --- Configuration ---
PROJECT_ROOT = Path(__file__).parent.parent.parent
CHROMA_DB_PATH = PROJECT_ROOT / "data" / "chroma_db"
COLLECTION_NAME = "mtg_rules"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
# --- End Configuration ---

class QueryResult(BaseModel):
    """A Pydantic model for a single RAG query result."""
    rule_id: str
    text: str
    score: float

KNOWN_KEYWORDS = {"trample", "lifelink", "deathtouch", "flying", "haste", "indestructible", "stack", "commander", "vigilance", "reach"}

def extract_keywords(query_text: str) -> List[str]:
    """Extracts known MTG keywords from a query."""
    return [kw for kw in KNOWN_KEYWORDS if kw in query_text.lower()]

class RAGRetriever:
    """Handles querying the MTG rules vector database."""
    def __init__(self):
        """
        Initializes the retriever, connects to ChromaDB, and loads all rules
        into memory for contextual expansion.
        """
        if not CHROMA_DB_PATH.exists():
            print("FATAL: ChromaDB path not found. Please run 'scripts/build_rules_db.py'.", file=sys.stderr)
            sys.exit(1)

        print("Initializing RAGRetriever...")
        self.client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))
        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL_NAME)
        
        try:
            self.collection = self.client.get_collection(name=COLLECTION_NAME, embedding_function=self.embedding_function)
            print("Successfully connected to ChromaDB collection.")
        except Exception as e:
            print(f"FATAL: Could not get ChromaDB collection '{COLLECTION_NAME}'. Error: {e}", file=sys.stderr)
            sys.exit(1)

        # Load all rule chunks into memory for the expansion step.
        self.all_rules: Dict[str, str] = {}
        rules_file = PROJECT_ROOT / "data" / "rules.txt"
        try:
            # Re-use our parsing logic from the build script.
            from scripts.build_rules_db import parse_rules_file
            chunks = parse_rules_file(rules_file)
            self.all_rules = {chunk['rule_id']: chunk['text'] for chunk in chunks}
            print(f"Loaded {len(self.all_rules)} rule chunks into memory for context expansion.")
        except ImportError:
             print("Warning: Could not import 'parse_rules_file'. Context expansion will be limited.", file=sys.stderr)
        except Exception as e:
            print(f"Warning: Could not load rules for expansion: {e}", file=sys.stderr)

    def _query_collection(self, query_texts: List[str], n_results: int) -> List[QueryResult]:
        """Internal helper to perform a query and format results."""
        if not query_texts: return []
        
        results = self.collection.query(query_texts=query_texts, n_results=n_results)
        
        formatted_results = []
        for i in range(len(results['ids'])):
            if not results['ids'][i]: continue
            for j in range(len(results['ids'][i])):
                formatted_results.append(
                    QueryResult(
                        rule_id=results['metadatas'][i][j].get('rule_id', results['ids'][i][j]),
                        text=results['documents'][i][j],
                        score=results['distances'][i][j]
                    )
                )
        return formatted_results

    def query(self, query_text: str, top_k: int = 5) -> List[QueryResult]:
        """Performs a multi-query search to find the most relevant rules."""
        if not query_text: return []
        
        keywords = extract_keywords(query_text)
        all_queries = [query_text] + keywords
        print(f"Performing multi-query search with: {all_queries}")
        
        results_per_query = max(1, top_k // len(all_queries))
        
        all_results: Dict[str, QueryResult] = {}
        try:
            query_results = self._query_collection(query_texts=all_queries, n_results=results_per_query)
            
            for result in query_results:
                if result.rule_id not in all_results or result.score < all_results[result.rule_id].score:
                    all_results[result.rule_id] = result

            sorted_results = sorted(all_results.values(), key=lambda r: r.score)
            return sorted_results[:top_k]
        except Exception as e:
            print(f"Error during ChromaDB multi-query: {e}", file=sys.stderr)
            return []

# Singleton instance
rag_retriever = RAGRetriever()