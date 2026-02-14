# CPIC-RAG

A sophisticated Agency RAG (Retrieval-Augmented Generation) system for Pharmacogenomics. This tool automates the ingestion, parsing, and querying of CPIC (Clinical Pharmacogenetics Implementation Consortium) guidelines to provide evidence-based gene-drug interaction recommendations.

## Features

- **Agentic Ingestion Pipeline**:
  - Automatically fetches CPIC guideline PDFs based on gene-drug pairs.
  - Uses **Unstructured.io API** for high-fidelity PDF parsing (tables, sections).
  - Stores structured data in **MongoDB** and vector embeddings in **FAISS**.

- **Intelligent RAG Querying**:
  - Semantic search using `sentence-transformers/all-MiniLM-L6-v2`.
  - Context-aware answers powered by **OpenRouter (GPT-OSS-20b)**.
  - Returns confidence scores and precise source citations.

- **Live Phenotype Resolver**:
  - Direct integration with the **CPIC REST API** (`api.cpicpgx.org`).
  - Resolves Diplotypes (e.g., `*1/*2`) to Phenotypes (e.g., `Normal Metabolizer`).
  - Provides activity scores, EHR priority, and clinical consultation text.

- **Modern Stack**:
  - **Backend**: Python 3.10+, FastAPI, LangChain, Motor (MongoDB), Unstructured Client.
  - **Frontend**: Next.js 14 (App Router), TypeScript, Tailwind CSS, Shadcn UI.
  - **Database**: MongoDB (Metadata/JSON storage) + FAISS (Vector Store).

## Getting Started

### Prerequisites

- **Python 3.10+**
- **Node.js 18+**
- **MongoDB** (running locally on `localhost:27017`)
- **API Keys**: OpenRouter (LLM), Unstructured.io (PDF Parsing)

### 1. Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create a virtual environment and activate it:
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
   pip install pymongo unstructured-client langchain-openai langchain-community faiss-cpu sentence-transformers
   ```

4. Configure Environment Variables:
   Create a `agent/.env` file (shared by backend/agent) with:
   ```env
   OPENROUTER_API_KEY=sk-or-...
   UNSTRUCTURED_API_KEY=...
   UNSTRUCTURED_URL=https://platform.unstructuredapp.io/api/v1
   MONGODB_URI=mongodb://localhost:27017
   MONGODB_DB_NAME=cpic_rag
   ```

5. Run the server:
   ```bash
   uvicorn main:app --reload --port 8000
   ```
   API Docs available at: http://localhost:8000/docs

### 2. Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Run the development server:
   ```bash
   npm run dev
   ```

4. Open [http://localhost:3000](http://localhost:3000) in your browser.

## Project Structure

```
├── agent/                  # Autonomous agent logic
│   ├── tools/              # Tools for fetching PDFs (requests + html.parser)
│   └── .env                # Shared environment variables
├── backend/
│   ├── main.py             # FastAPI entry point
│   ├── config.py           # Configuration & Settings
│   ├── routers/            # API Endpoints (query, ingest, phenotype)
│   ├── services/
│   │   ├── ingestion.py    # Full ingestion pipeline
│   │   ├── mongodb.py      # MongoDB connection & CRUD
│   │   ├── phenotype.py    # CPIC API integration
│   │   ├── rag.py          # RAG Chain logic
│   │   └── unstructured_parser.py # Unstructured.io integration
│   └── data/               # Local data storage (FAISS index)
└── frontend/               # Next.js Application
    ├── src/app/            # App Router pages
    └── src/components/     # UI Components (Shadcn)
```

## Usage

1. **Ingest a Guideline**:
   - Go to the "Ingest" tab.
   - Enter a Gene (e.g., `CYP2D6`) and Drug (e.g., `Amitriptyline`).
   - The system will fetch the PDF, parse it, and index it.

2. **Query the Knowledge Base**:
   - Go to "Query".
   - Ask a question: *"What is the dosing recommendation for a PM?"*
   - Get an answer with source citations and confidence score.

3. **Check Phenotype**:
   - Go to "Phenotype".
   - Select Gene and Diplotype (e.g., `CYP2C19 *2/*2`).
   - See the clinical phenotype, activity score, and recommendations.
![Workflow Diagram](./image.png)