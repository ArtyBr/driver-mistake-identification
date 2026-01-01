from sqlmodel import SQLModel, create_engine, Session
from ..core.config import DB_PATH

# SQLite URL
sqlite_url = f"sqlite:///{DB_PATH}"

# Create Engine
# check_same_thread=False is needed for SQLite with FastAPI (multiple threads)
engine = create_engine(sqlite_url, echo=False, connect_args={"check_same_thread": False})

def init_db():
    """Initializes the database tables."""
    SQLModel.metadata.create_all(engine)

def get_session():
    """Dependency that provides a database session."""
    with Session(engine) as session:
        yield session