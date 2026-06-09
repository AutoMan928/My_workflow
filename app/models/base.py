import os
from sqlalchemy import create_engine, text as _sql_text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///data/news.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def _init_fts() -> None:
    with engine.begin() as conn:
        conn.execute(_sql_text("""
            CREATE VIRTUAL TABLE IF NOT EXISTS items_fts USING fts5(
                title, content='items', content_rowid='id'
            )
        """))
        conn.execute(_sql_text("""
            CREATE TRIGGER IF NOT EXISTS items_ai AFTER INSERT ON items BEGIN
                INSERT INTO items_fts(rowid, title)
                VALUES (new.id, new.title);
            END
        """))
        conn.execute(_sql_text("""
            INSERT OR IGNORE INTO items_fts(rowid, title)
            SELECT id, title FROM items
        """))


def init_db() -> None:
    from app.models import item, push_log, run_log, source  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _init_fts()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
