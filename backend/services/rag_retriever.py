"""
A service for retrieving relevant documents from the ChromaDB vector store.

This module provides a singleton retriever class that encapsulates the logic for
connecting to the pre-existing ChromaDB collection and performing similarity
searches based on a user's query.
"""

import sys
from pathlib import Path
from typing import List
import chromadb
from chromadb.utils import embedding_functions
from pydantic import BaseModel, Field

# --- Configuration ---
# These constants must match the ones used in the 'scripts/build_rules_db.py' script.
PROJECT_ROOT = Path(__file__).parent.parent.parent
CHROMA_DB_PATH = PROJECT_ROOT / "data" / "chroma_db"
COLLECTION_NAME = "mtg_rules"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
# --- End Configuration ---

class QueryResult(BaseModel):
    """A Pydantic model for a single RAG query result."""
    rule_id: str = Field(..., description="The unique identifier of the rule (e.g., '100.1a').")
    text: str = Field(..., description="The full text content of the rule.")
    score: float = Field(..., description="The similarity score (distance) of the result.")

class RAGRetriever:
    """Handles querying the MTG rules vector database."""

    def __init__(self):
        """
        Initializes the retriever by connecting to the persistent ChromaDB client
        and loading the MTG rules collection.
        """
        if not CHROMA_DB_PATH.exists():
            print(f"FATAL: ChromaDB path not found at '{CHROMA_DB_PATH.resolve()}'.", file=sys.stderr)
            print("Please run 'scripts/build_rules_db.py' to create the vector database.", file=sys.stderr)
            sys.exit(1)

        print("Initializing RAGRetriever...")
        self.client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))
        
        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL_NAME
        )
        
        try:
            self.collection = self.client.get_collection(
                name=COLLECTION_NAME,
                embedding_function=self.embedding_function
            )
            print("Successfully connected to ChromaDB collection.")
        except Exception as e:
            print(f"FATAL: Could not get ChromaDB collection '{COLLECTION_NAME}'. Error: {e}", file=sys.stderr)
            print("Please ensure the collection exists and the database is not corrupted.", file=sys.stderr)
            sys.exit(1)

    def query(self, query_text: str, top_k: int = 5) -> List[QueryResult]:
        """
        Performs a similarity search on the vector database.

        Args:
            query_text (str): The user's query to search for.
            top_k (int): The number of top results to retrieve.

        Returns:
            A list of QueryResult objects, sorted by relevance.
        """
        if not query_text:
            return []
            
        try:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=top_k
            )
            
            # The query result structure is a dictionary of lists of lists.
            # It needs to be unpacked for a single query.
            if not results or not results.get('ids') or not results['ids'][0]:
                return []

            ids = results['ids'][0]
            documents = results['documents'][0]
            distances = results['distances'][0]
            metadatas = results['metadatas'][0]

            query_results = [
                QueryResult(
                    rule_id=metadata.get('rule_id', ids[i]),
                    text=documents[i],
                    score=distances[i]
                )
                for i, (metadata) in enumerate(metadatas)
            ]
            
            return query_results

        except Exception as e:
            print(f"Error during ChromaDB query: {e}", file=sys.stderr)
            return []

# A singleton instance to be used by the rest of the application.
# This is efficient as the client and model are loaded only once.
rag_retriever = RAGRetriever()