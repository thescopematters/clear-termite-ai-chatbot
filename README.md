# Clear Termite AI Chatbot

A production-ready customer portal chatbot backend for "Clear Termite". It translates natural language user questions into secure, validated queries against a live database, returning friendly conversational answers and structured data.

## Architecture Overview

This backend has been heavily hardened for production use:
- **Framework:** Asynchronous API endpoints.
- **Database:** Relational database integration with connection pooling.
- **Cache & Rate Limiting:** Memory-backed caching for response optimization and IP rate limiting to prevent abuse.
- **Authentication:** JWT architecture. The chatbot seamlessly verifies existing JWT tokens from the main ClearTermite application.
- **AI Engine:** Advanced LLM orchestrated via an agentic Text-to-SQL logic block.
- **Security Validation:** Multi-layered security using AST parsing. Enforces row-level user data isolation, prevents data modification operations, and checks authorization before any query execution.

## Setup Instructions

### Prerequisites
- Docker & Docker Compose
- Python 3.10+
- Node.js

### 1. Environment Configuration

Create a `.env` file in the codebase. You will need to configure variables for your AI API keys, database connection strings, JWT secret key, and your cache URL. Contact the lead developer for the expected environment variables or check the sample environment variables provided in the repository if available.

### 2. Infrastructure Setup
Use Docker Compose to spin up the required local instances:
```bash
docker-compose up -d
```

### 3. Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a Virtual Environment:
   ```bash
   python -m venv venv
   # Windows:
   .\venv\Scripts\activate
   # Mac/Linux:
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Start the server:
   ```bash
   uvicorn main:app --reload
   ```

### 4. Frontend Setup

1. Open another terminal and enter the `frontend` directory.
2. Install dependencies and start the UI:
   ```bash
   npm install
   npm run dev
   ```

## Security Guardrails

The natural language processing runs entirely through strict validation funnels before interacting with the database:

1. **Schema Obfuscation:** The AI's context is strictly limited to relevant business tables. Sensitive system tables are completely invisible to it.
2. **Abstract Syntax Tree (AST) Parsing:** The code parses the AI's data retrieval output into a structural tree. If the query attempts to modify data or retrieve unauthorized information, it is explicitly blocked.
3. **Implicit User Isolation:** Every query generated must heavily rely on the appropriate relationship tables to filter specifically by the authenticated user's ID. Queries without an isolation point are rejected.
4. **Prompt Enforcement:** The AI is explicitly trained to reject non-business conversation, returning an "OFF_TOPIC" flag.
