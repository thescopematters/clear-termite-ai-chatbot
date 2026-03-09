# Clear Termite Customer Portal Chatbot

A lean, local-first prototype of a customer portal chatbot for "Clear Termite", built with React (Vite) and FastAPI. The app uses an LLM (Google Gemini) to parse natural language questions into SQL queries, executes them against a local SQLite database, and returns formatted conversational answers to the UI.

## Overview & Tech Stack

- **Frontend:** React with TypeScript, Vite, Vanilla CSS. Features a clean interface with suggested questions. 
- **Backend:** FastAPI (Python), `google-generativeai`. Serves API endpoints and manages the LLM workflows.
- **Database:** SQLite (file-based). Setup happens automatically on first run.
- **LLM:** Google Gemini API (gemini-2.5-flash).

## Quick Setup Instructions

### 1. Backend Setup

1. Open a terminal and navigate to exactly the `backend/` directory:
   ```bash
   cd backend
   ```
2. Set up a virtual environment (recommended):
   ```bash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On Mac/Linux:
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Create a `.env` file in the `backend/` directory and add your Gemini API key:
   ```env
   GEMINI_API_KEY=your_actual_studio_key_here
   ```
5. Run the FastAPI development server:
   ```bash
   uvicorn main:app --reload
   ```
   *(The server will start at `http://localhost:8000` and `database.py` logic will automatically initialize the `cleartermite_demo.db` with sample data).*

### 2. Frontend Setup

1. Open *another* terminal window and navigate to the `frontend/` directory:
   ```bash
   cd frontend
   ```
2. Install the node modules:
   ```bash
   npm install
   ```
3. Start the Vite development server:
   ```bash
   npm run dev
   ```
4. Open the link provided in the terminal (usually `http://localhost:5173`) in your browser to view the app!

## How the Data Flow Works

1. **User Input:** The user clicks a suggested chip or types a question (e.g., "Check status of my payment").
2. **Frontend Request:** The React app sends a `POST` request to `/api/chat` with the message and the current `user_id` (mocked to user 1 for the demo).
3. **Intent Extraction (Gemini Call 1):** The FastAPI backend queries Gemini with the DB Schema + user request to figure out the intent and optionally generate a safe SQL query restricted to the current user's records.
4. **Database Execution:** The backend runs the SQL against the local SQLite file.
5. **Response Generation (Gemini Call 2):** The retrieved data is sent *back* to Gemini with instructions to format a friendly, professional response and categorize it as "text", "table", or "status".
6. **UI Display:** The frontend receives the formatted string and outputs it, rendering any markdown tables or basic badges appropriately.

## SQLite Schema + Sample Data SQL (Reference)

If you'd like to inspect the database creation logic, open `backend/database.py`. The initialization script runs this SQL:

```sql
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    role TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS properties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    address TEXT NOT NULL,
    city TEXT NOT NULL,
    zip TEXT NOT NULL,
    transaction_status TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS inspections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER,
    scheduled_date TEXT,
    completed_date TEXT,
    status TEXT,
    findings_summary TEXT,
    report_notes TEXT,
    FOREIGN KEY (property_id) REFERENCES properties (id)
);

CREATE TABLE IF NOT EXISTS repairs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inspection_id INTEGER,
    description TEXT,
    cost_estimate REAL,
    approved BOOLEAN,
    completed BOOLEAN,
    FOREIGN KEY (inspection_id) REFERENCES inspections (id)
);

CREATE TABLE IF NOT EXISTS clearances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER,
    issued_date TEXT,
    status TEXT,
    certificate_notes TEXT,
    FOREIGN KEY (property_id) REFERENCES properties (id)
);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER,
    amount REAL,
    status TEXT,
    paid_date TEXT,
    FOREIGN KEY (property_id) REFERENCES properties (id)
);

-- Insert sample dat
INSERT INTO users (id, name, email, role) VALUES 
(1, 'John Realestate', 'john@example.com', 'realtor'),
(2, 'Sarah Homeowner', 'sarah@example.com', 'homeowner');

INSERT INTO properties (id, user_id, address, city, zip, transaction_status) VALUES
(1, 1, '123 Ocean View Dr', 'San Diego', '92109', 'in_escrow'),
(2, 2, '456 Normal St', 'San Diego', '92103', 'active');

-- (Plus corresponding details for inspections, repairs, payments on property 1 and 2)
```

## Example Questions & What Happens

1. **"Show my latest inspection report"**
   - *Flow:* Gemini queries the `inspections` table for `property_id` matching `user_id = 1`. Returns finding summary. 
   - *Result:* "Here is the summary of your recent inspection ... Section 1 damage found in eaves."

2. **"What repairs are recommended for my property?"**
   - *Flow:* Gemini queries the `repairs` table joined with inspections and properties. 
   - *Result:* A markdown table rendering the repairs, cost estimates, and approval status.

3. **"Has my termite clearance been issued?"**
   - *Flow:* Queries the `clearances` table.
   - *Result:* Friendly response with the status noting that it's "pending" and "Awaiting completion of eaves repair."

4. **"Check status of my payment/invoice"**
   - *Flow:* Queries `payments` table.
   - *Result:* Lets you know it is pending for the amount of $3750.00.
