# EnviroWealth Carbon Market Eligibility Chatbot

This document provides setup instructions for running the EnviorWealth Chatbot locally on Windows.

## 1. Prerequisites
- **PostgreSQL**: Must be running with the `pgvector` and `postgis` extensions available.
- **Python 3.13**: Required for the backend.
- **Node.js**: Required for the Next.js frontend.

## 2. Environment Variables
Ensure you have a `.env` file located in the `web` folder (`web/.env`). This file configures the database connection, API keys, and admin authentication secrets.
You can copy `.env.example` to `.env` and fill in the required values.

---

## 3. Backend Setup

The backend is a FastAPI application that serves the API, orchestrates the LLM agent, and hosts the Admin Panel.

1. **Navigate to the backend directory:**
   ```cmd
   cd backend
   ```

2. **Activate the virtual environment:**
   *(Assuming it's already created at `backend/venv`)*
   ```cmd
   venv\Scripts\activate
   ```

3. **Initialize the database (first time only):**
   ```cmd
   python init_db.py
   ```

4. **Start the backend server:**
   To avoid issues with Windows subprocesses and the virtual environment when reloading, it's recommended to call the virtual environment Python directly:
   ```cmd
   venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
   ```
   *The backend will now be running at `http://localhost:8000`.*

---

## 4. Frontend Setup

The frontend is a modern Next.js application that provides the user-facing chat interface.

1. **Navigate to the frontend directory:**
   ```cmd
   cd frontend
   ```

2. **Install dependencies (first time only):**
   ```cmd
   npm install
   ```

3. **Start the development server:**
   ```cmd
   npm run dev
   ```
   *The frontend will now be running at `http://localhost:3000`.*

---

## 5. Using the Application

### 🌐 The Chatbot (User Interface)
Once the Next.js frontend server is running, you can access the chatbot interface by opening:
**👉 [http://localhost:3000](http://localhost:3000)**

### ⚙️ The Admin Panel
The Admin Panel is a static dashboard served directly by the backend to manage LLM configurations and the RAG Document Corpus.
Once the backend server is running, you can access it by opening:
**👉 [http://localhost:8000/admin/index.html](http://localhost:8000/admin/index.html)**

**Default Credentials:**
- **Username:** `admin`
- **Password:** `password`
