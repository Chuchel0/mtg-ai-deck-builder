from pathlib import Path
from sqlmodel import SQLModel, create_engine

# Import the models file so that SQLModel knows about the tables.
from . import models  # noqa: F401

# Define the path for the SQLite database file.
# It is placed in the `data` directory at the project root.
# Path(__file__) is the path to this connection.py file.
DB_FILE = Path(__file__).parent.parent.parent / "data" / "mtg_collection.db"
DB_FILE.parent.mkdir(exist_ok=True) # Ensure the 'data' directory exists

# The database URL for SQLite.
# The format is 'sqlite:///path/to/your/database.db'
DATABASE_URL = f"sqlite:///{DB_FILE.resolve()}"

# The engine is the core interface to the database.
# This engine is used in other parts of application to interact with the DB.
# connect_args is specific to SQLite to allow multiple threads to access it,
# which is necessary for FastAPI's asynchronous nature.
engine = create_engine(DATABASE_URL, echo=True, connect_args={"check_same_thread": False})


def create_db_and_tables():
    """
    Initializes the database and creates all tables.
    This function should be called once when the application starts.
    """
    print("Initializing database...")
    print(f"Database will be created at: {DATABASE_URL}")
    
    # SQLModel.metadata.create_all() inspects all the classes that inherit from
    # SQLModel and creates the corresponding tables in the database.
    # It will not recreate tables that already exist.
    SQLModel.metadata.create_all(engine)
    
    print("Database initialization complete.")