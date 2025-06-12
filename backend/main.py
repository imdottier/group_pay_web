from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from contextlib import asynccontextmanager
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv
import os
import logging
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
import google.generativeai as genai
from backend.config import settings

# Load environment variables from .env file at the very beginning
load_dotenv()

# Import your database objects if needed globally or for lifespan/startup events
# from database import Base, engine

# Import your routers
from backend.routers import (
    users, auth, groups, bills, payments, 
    transactions, categories, balance, notifications, activities,
    friends, invitations, statistics, bill_categories, receipt_parser
)

from backend.database import engine, Base

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
# Quieten down noisy libraries
logging.getLogger("python_multipart").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.INFO)

logger = logging.getLogger(__name__)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# --- Lifespan Context Manager ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles application startup and shutdown events.
    """
    logger.info("--- Starting up application ---")
    
    # Configure Google Generative AI
    app.state.google_ai_configured = False
    if settings.GOOGLE_API_KEY:
        logger.info("Configuring Google Generative AI client...")
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        app.state.google_ai_configured = True
        logger.info("Google Generative AI client configured successfully.")
    else:
        logger.warning("GOOGLE_API_KEY not found. Receipt parsing feature will be unavailable.")
    
    # Initialize FastAPI Cache
    FastAPICache.init(InMemoryBackend(), prefix="fastapi-cache")
    logger.info("FastAPI cache initialized.")
    
    yield
    
    logger.info("--- Shutting down application ---")


# Create the main FastAPI instance
app = FastAPI(
    title="Group Payment API",
    version="0.1.0",
    description="A secure API for managing group payments and expenses",
    lifespan=lifespan
)

# --- CORS Middleware Configuration ---
origins = [
    settings.FRONTEND_URL,
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add Session Middleware for OAuth state management
# IMPORTANT: This secret_key should be the same as your JWT secret
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY 
)
# -----------------------------------

# Add rate limiter to the application
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Rate limit dependencies
@limiter.limit(os.getenv("RATE_LIMIT_AUTH", "5/minute"))
async def rate_limit_auth(request: Request):
    pass

@limiter.limit(os.getenv("RATE_LIMIT_FINANCIAL", "60/minute"))
async def rate_limit_financial(request: Request):
    pass

@limiter.limit(os.getenv("RATE_LIMIT_GENERAL", "200/minute"))
async def rate_limit_general(request: Request):
    pass

# --- Include Routers with specific rate limits ---
app.include_router(
    auth.router,
    tags=["Authentication"],
    dependencies=[Depends(rate_limit_auth)]
)

# Financial endpoints with stricter rate limiting
app.include_router(bills.router, dependencies=[Depends(rate_limit_financial)])
app.include_router(payments.router, dependencies=[Depends(rate_limit_financial)])
app.include_router(transactions.router, dependencies=[Depends(rate_limit_financial)])

# Other routers with default rate limiting
app.include_router(users.router, dependencies=[Depends(rate_limit_general)])
app.include_router(groups.router, dependencies=[Depends(rate_limit_general)])
app.include_router(categories.router, dependencies=[Depends(rate_limit_general)])
app.include_router(balance.router, dependencies=[Depends(rate_limit_general)])
app.include_router(notifications.router, dependencies=[Depends(rate_limit_general)])
app.include_router(activities.router, dependencies=[Depends(rate_limit_general)])
app.include_router(statistics.router, dependencies=[Depends(rate_limit_general)])
app.include_router(bill_categories.router, dependencies=[Depends(rate_limit_general)])
app.include_router(receipt_parser.router, dependencies=[Depends(rate_limit_general)])

# Include the new routers for friendships and invitations
app.include_router(friends.router)
app.include_router(invitations.router)

# --- Basic Root Endpoint ---
# Good for a basic health check or welcome message
@app.get("/", tags=["Health Check"])
async def root(request: Request, _=Depends(rate_limit_general)):
    """API health check endpoint"""
    return {"status": "healthy", "version": app.version}
