"""
database.py - Async MySQL connection management with SQLAlchemy connection pooling.
Uses aiomysql for non-blocking I/O. Database schema is managed externally.
"""

import os
import logging
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncConnection
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("chatbot_api")


def _build_db_uri(include_db: bool = True) -> str:
    """Build the MySQL connection URI for async aiomysql."""
    user = os.getenv("DB_USER", "demo")
    password = os.getenv("DB_PASSWORD", "demo")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "3306")
    db_name = os.getenv("DB_NAME", "cleartermite_demo")
    if include_db:
        return f"mysql+aiomysql://{user}:{password}@{host}:{port}/{db_name}"
    return f"mysql+aiomysql://{user}:{password}@{host}:{port}"


def get_sync_db_uri() -> str:
    """Return the synchronous database URI (pymysql) for LangChain's SQLDatabase."""
    user = os.getenv("DB_USER", "demo")
    password = os.getenv("DB_PASSWORD", "demo")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "3306")
    db_name = os.getenv("DB_NAME", "cleartermite_demo")
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{db_name}"


# ======= Async Connection Pool (Singleton) =======
_async_engine: AsyncEngine = None


def get_engine() -> AsyncEngine:
    """Get or create the SQLAlchemy Async engine with connection pooling."""
    global _async_engine
    if _async_engine is None:
        _async_engine = create_async_engine(
            _build_db_uri(include_db=True),
            pool_size=5,
            max_overflow=10,
            pool_recycle=1800,
            pool_pre_ping=True,
            # Hard connection timeout (execution timeout handled via asyncio.wait_for in main.py)
            connect_args={"connect_timeout": 5},
            echo=False,
        )
        logger.info("SQLAlchemy Async connection pool initialized.")
    return _async_engine


@asynccontextmanager
async def get_db_connection() -> AsyncConnection:
    """
    Context manager that provides a pooled async database connection.
    Usage:
        async with get_db_connection() as conn:
            result = await conn.execute(text("SELECT ..."))
    """
    engine = get_engine()
    async with engine.connect() as conn:
        try:
            yield conn
        finally:
            await conn.close()
