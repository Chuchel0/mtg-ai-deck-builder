"""
A command-line utility for processing the MTG Comprehensive Rules text file and
building a persistent vector database for Retrieval-Augmented Generation (RAG).

This script performs the following steps:
1. Parses the raw text file into discrete, semantically meaningful rule chunks.
2. Initializes a sentence-transformer model to generate vector embeddings for each chunk.
3. Initializes a persistent ChromaDB client.
4. Creates or updates a ChromaDB collection with the rule chunks, their embeddings,
   and associated metadata (rule IDs).

This script is idempotent and can be re-run to rebuild the database from the
latest rules.txt file.
"""

import re
import sys
from pathlib import Path
from typing import List, Dict, Any

import chromadb
from chromadb.utils import embedding_functions

# --- Configuration ---
PROJECT_ROOT = Path(__file__).parent.parent
INPUT_FILE = PROJECT_ROOT / "data" / "rules.txt"
CHROMA_DB_PATH = PROJECT_ROOT / "data" / "chroma_db"
COLLECTION_NAME = "mtg_rules"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
# --- End Configuration ---

def parse_rules_file(file_path: Path) -> List[Dict[str, Any]]:
    """
    Parses the MTG Comprehensive Rules text file into a list of structured chunks.

    Each chunk corresponds to a distinct rule, glossary entry, or section. The parsing
    identifies rule boundaries using regular expressions that match standard rule numbering
    (e.g., "101.1.") and section headers (e.g., "Glossary").

    Args:
        file_path (Path): The path to the rules.txt file.

    Returns:
        A list of dictionaries, each representing a rule chunk with 'rule_id' and 'text'.
    """
    if not file_path.exists():
        print(f"Error: Rules file not found at {file_path.resolve()}", file=sys.stderr)
        print("Please run 'scripts/download_rules.py' first.", file=sys.stderr)
        return []

    print(f"Parsing rules from: {file_path.resolve()}")
    content = file_path.read_text(encoding='utf-8')

    # Regex to identify the start of a rule or major section.
    rule_pattern = re.compile(r"^(?P<id>\d{3}\.\d+[a-z]?\.?|Glossary|Credits)\s", re.MULTILINE)
    matches = list(rule_pattern.finditer(content))
    
    if not matches:
        print("Error: No rule patterns found. The file format may have changed.", file=sys.stderr)
        return []
        
    chunks = []
    for i, match in enumerate(matches):
        start_pos = match.end()
        end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        
        rule_id = match.group('id').strip().rstrip('.')
        rule_text = content[start_pos:end_pos].strip()
        cleaned_text = re.sub(r'\n\s*\n', '\n', rule_text)

        if cleaned_text:
            chunks.append({"rule_id": rule_id, "text": cleaned_text})

    print(f"Successfully parsed {len(chunks)} rule chunks.")
    return chunks

def build_and_persist_chroma_collection(chunks: List[Dict[str, Any]]):
    """
    Generates embeddings for rule chunks and persists them in a ChromaDB collection.

    This function sets up a persistent ChromaDB client, initializes the embedding model,
    and populates a collection. It handles de-duplication of IDs to ensure database
    integrity.

    Args:
        chunks (List[Dict[str, Any]]): The list of parsed rule chunks to be embedded.
    """
    print("Initializing ChromaDB client...")
    client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))

    print(f"Initializing embedding function with model: {EMBEDDING_MODEL_NAME}")
    embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL_NAME)

    print(f"Getting or creating ChromaDB collection: '{COLLECTION_NAME}'")
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_function,
        metadata={"hnsw:space": "cosine"}
    )

    print("Preparing documents, metadatas, and unique IDs for ChromaDB...")
    documents = [chunk["text"] for chunk in chunks]
    metadatas = [{"rule_id": chunk["rule_id"]} for chunk in chunks]
    
    # Ensure all ChromaDB document IDs are unique.
    ids = []
    id_counts = {}
    for chunk in chunks:
        base_id = chunk["rule_id"]
        if base_id in id_counts:
            id_counts[base_id] += 1
            unique_id = f"{base_id}-{id_counts[base_id]}"
        else:
            id_counts[base_id] = 1
            unique_id = base_id
        ids.append(unique_id)

    print(f"Populating collection with {len(documents)} documents. This may take some time...")
    # To ensure idempotency, delete existing entries with the same IDs before adding.
    collection.delete(ids=ids)
    collection.add(documents=documents, metadatas=metadatas, ids=ids)

    print("Successfully built and persisted the ChromaDB collection.")
    print(f"Vector database is stored at: {CHROMA_DB_PATH.resolve()}")

def main():
    """Main execution function for the script."""
    CHROMA_DB_PATH.mkdir(exist_ok=True)
    chunks = parse_rules_file(INPUT_FILE)
    
    if chunks:
        build_and_persist_chroma_collection(chunks)
    else:
        sys.exit(1) # Exit with an error code if parsing failed.

if __name__ == "__main__":
    main()