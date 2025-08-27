"""
Database connection and session management.

This module configures the application's database engine and provides a
function to initialize the database schema based on the defined SQLModels.
"""

from pathlib import Path
from sqlmodel import SQLModel, create_engine
from . import models  # noqa: F401 - Ensures models are registered with SQLModel metadata

# --- Database Configuration ---
# Construct an absolute path to the database file within the project's /data directory.
# This approach ensures the path is correct regardless of where the application is run from.
DB_FILE = Path(__file__).parent.parent.parent / "data" / "mtg_collection.db"
DATABASE_URL = f"sqlite:///{DB_FILE.resolve()}"
# --- End Configuration ---

# The database engine is the central access point to the database.
# - `echo=True` logs all generated SQL statements, which is useful for debugging.
#   This should be set to `False` in a production environment.
# - `connect_args` is required for SQLite to allow the database connection
#   to be shared across multiple threads, which is necessary for FastAPI.
engine = create_engine(DATABASE_URL, echo=True, connect_args={"check_same_thread": False})

def create_db_and_tables():
    """
    Initializes the database by creating all tables defined by SQLModel classes.

    This function is idempotent; it will not attempt to recreate tables that
    already exist in the database. It should be called once on application startup.
    """
    print(f"Initializing database at: {DATABASE_URL}")
    SQLModel.metadata.create_all(engine)
    print("Database tables created or verified successfully.")