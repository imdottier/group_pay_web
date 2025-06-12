# from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from dotenv import load_dotenv
import os
from typing import Annotated, AsyncGenerator
from fastapi import Depends, HTTPException, status

# Load environment variables
load_dotenv()

# Get database configuration from environment variables
ASYNC_SQLALCHEMY_DATABASE_URL = os.getenv("ASYNC_SQLALCHEMY_DATABASE_URL")
if not ASYNC_SQLALCHEMY_DATABASE_URL:
    raise ValueError("ASYNC_SQLALCHEMY_DATABASE_URL environment variable is not set")

print(ASYNC_SQLALCHEMY_DATABASE_URL)

# Engine for asynchronous operations
try:
    engine = create_async_engine(
        ASYNC_SQLALCHEMY_DATABASE_URL,
        echo=False,  # Set to True for SQL query logging
        pool_pre_ping=True,  # Enable connection health checks
        pool_size=5,  # Adjust based on your needs
        max_overflow=10
    )
except Exception as e:
    raise ValueError(f"Failed to create database engine: {str(e)}")

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Base class for SQLAlchemy models
Base = declarative_base()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except HTTPException: # If it's already an HTTPException, let it pass through
            raise
        except Exception as e:
            # For other exceptions, rollback and raise a generic DB error
            # Consider adding: import logging; logger = logging.getLogger(__name__); logger.error(f"Unhandled DB session error: {e}", exc_info=True)
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="A database session error occurred." # Updated detail message
            ) from e
        finally:
            await session.close()

# Typed dependency for use in route functions
DbSessionDep = Annotated[AsyncSession, Depends(get_db)]