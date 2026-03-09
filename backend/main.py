import os
import json
import logging
import asyncio
from typing import Optional

# SlowAPI Rate Limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# LangChain imports
from langchain_community.utilities import SQLDatabase
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.chains import create_sql_query_chain
from langchain_core.messages import HumanMessage

from pydantic import BaseModel, Field
from sqlalchemy import text

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from database import get_db_connection, get_sync_db_uri
from auth import verify_token
from utils import validate_sql_query
from prompts import SQL_GENERATION_PROMPT, RESPONSE_FORMATTING_PROMPT, ALLOWED_TABLE_LIST
from cache import response_cache

# ======= Setup =======
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("chatbot_api")

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

app = FastAPI(title="Clear Termite Chatbot API")

# Rate Limiter setup
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

origins = [
    "http://localhost:5173",
    "http://localhost:5174",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# ======= Pydantic Models =======

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    message: str = Field(description="A friendly natural language response. Escrow-friendly tone.")
    type: str = Field(description="'text' (general), 'table' (list of items), or 'status' (single status).")
    data: Optional[list] = Field(default=None, description="Array of data objects, if applicable.")


# ======= LangChain Sync DB for Schema Reading =======
_langchain_db = None

def get_langchain_db():
    """LangChain's SQLDatabase with access restricted to ALLOWED_TABLES only."""
    global _langchain_db
    if _langchain_db is None:
        _langchain_db = SQLDatabase.from_uri(
            get_sync_db_uri(),
            include_tables=ALLOWED_TABLE_LIST,  # Only expose allowed tables to the LLM
        )
    return _langchain_db


# ======= Startup =======

@app.on_event("startup")
async def startup_event():
    logger.info("Clear Termite Chatbot API started. Database managed externally via Docker Compose.")


@app.get("/api/dev-token")
async def get_dev_token():
    """Generates a long-lived JWT for frontend local development testing."""
    from auth import create_access_token
    token = create_access_token(data={"sub": "1", "role": "realtor"})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": 1, "name": "John Realestate (Dev)", "role": "realtor"}
    }



# ======= Endpoints =======

@app.get("/api/user")
async def get_current_user_profile(user_id: int = Depends(verify_token)):
    """Return the authenticated user's profile from the database."""
    async with get_db_connection() as conn:
        result = await conn.execute(
            text("SELECT id, name, email, role FROM users WHERE id = :uid"),
            {"uid": user_id},
        )
        user = result.mappings().fetchone()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return dict(user)


@app.post("/api/chat", response_model=ChatResponse)
@limiter.limit("20/minute")
async def chat_endpoint(request: Request, body: ChatRequest, current_user_id: int = Depends(verify_token)):
    """
    Core AI Chat Endpoint.
    - Rate limited to 20 requests per minute per IP via SlowAPI.
    - Redis cached.
    - Async execution with asyncio.wait_for timeouts.
    - User isolation enforced via property_users table.
    """
    user_message = body.message
    logger.info(json.dumps({"event": "chat_request", "user_id": current_user_id, "message": user_message}))

    if not GEMINI_API_KEY:
        return ChatResponse(
            message="Please configure GEMINI_API_KEY to enable the chatbot.",
            type="text",
            data=None,
        )

    # --- 1. Check Redis Cache First ---
    cached = response_cache.get(current_user_id, user_message)
    if cached:
        return ChatResponse(**cached)

    try:
        # --- 2. SQL Generation via LangChain ---
        model_name = os.getenv("GEMINI_MODEL")
        if not model_name:
            raise ValueError("GEMINI_MODEL environment variable must be set.")
        llm = ChatGoogleGenerativeAI(model=model_name, temperature=0, google_api_key=GEMINI_API_KEY)
        db = get_langchain_db()

        sql_chain = create_sql_query_chain(llm, db)
        custom_prompt = SQL_GENERATION_PROMPT.format(
            user_message=user_message,
            user_id=current_user_id,
            allowed_tables=", ".join(ALLOWED_TABLE_LIST),
        )

        try:
            generated_sql = sql_chain.invoke({"question": custom_prompt})
            clean_sql = generated_sql.replace("```sql", "").replace("```", "").strip()

            # LangChain sometimes prefixes with "SQLQuery:"
            if clean_sql.startswith("SQLQuery:"):
                clean_sql = clean_sql[len("SQLQuery:"):].strip()

            # Security: Check if LLM flagged it as off-topic
            if clean_sql.upper() == "OFF_TOPIC":
                logger.info(json.dumps({"event": "off_topic_rejected", "user_id": current_user_id, "message": user_message}))
                return ChatResponse(
                    message="I am a virtual assistant for Clear Termite records. I can only assist you with looking up your property inspections, clearances, repairs, and payments.",
                    type="text",
                    data=None
                )

        except Exception as e:
            logger.error(json.dumps({"event": "sql_chain_error", "user_id": current_user_id, "error": str(e)}))
            return ChatResponse(message="I'm having trouble understanding your question. Could you please rephrase it?", type="text", data=None)

        # --- 3. Strict SQL Validation ---
        db_results = None
        if clean_sql.upper().startswith("SELECT"):
            try:
                validated_sql = validate_sql_query(clean_sql, expected_user_id=current_user_id)
            except ValueError as e:
                logger.warning(json.dumps({
                    "event": "sql_validation_rejected",
                    "user_id": current_user_id,
                    "generated_sql": clean_sql,
                    "reason": str(e),
                }))
                return ChatResponse(
                    message="I wasn't able to find the information you're looking for. Could you please rephrase your question?",
                    type="text",
                    data=None,
                )

            # --- 4. Async Execution with Timeouts ---
            logger.info(json.dumps({"event": "sql_execution", "user_id": current_user_id, "sql": validated_sql}))
            async with get_db_connection() as conn:
                try:
                    result = await asyncio.wait_for(conn.execute(text(validated_sql)), timeout=5.0)
                    rows = result.mappings().all()
                    db_results = [dict(row) for row in rows]
                except asyncio.TimeoutError:
                    raise Exception("Database query timed out after 5 seconds.")

        # --- 5. Format Response ---
        final_prompt = RESPONSE_FORMATTING_PROMPT.format(
            user_message=user_message,
            db_results=json.dumps(db_results, default=str),
        )

        raw_response = llm.invoke([HumanMessage(content=final_prompt + """

Respond ONLY with a valid JSON object with these exact keys:
{
  "message": "your friendly response here",
  "type": "text" or "table" or "status",
  "data": null or [list of objects]
}
Do not wrap in markdown. Only return the raw JSON object.""")])

        # Parse the JSON from the LLM text response
        response_text = raw_response.content.strip()
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()

        parsed = json.loads(response_text)
        final_result = ChatResponse(
            message=parsed.get("message", "I retrieved your information."),
            type=parsed.get("type", "text"),
            data=parsed.get("data", None),
        )

        # --- 6. Set Redis Cache ---
        response_cache.set(current_user_id, user_message, final_result.model_dump())

        return final_result

    except Exception as e:
        logger.error(json.dumps({"event": "chat_endpoint_error", "user_id": current_user_id, "error": str(e)}))
        raise HTTPException(status_code=500, detail="Internal server error executing chat flow.")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
