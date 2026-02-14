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
<<<<<<< HEAD

![Workflow Diagram](./mermaid-diagram-2026-02-14-232205.svg)
=======
   - [![](https://mermaid.ink/img/pako:eNqVVm1v4jgQ_iuWK626EuQSQiDkw0kttCvu6JYrZXW65rQyyQRyBZtzQluu6n_fsWNCeDu0_VDs8TPPvHqcdxqJGGhA6_V6yCPBk3QahJyQOVuLVR6QmE0lhFwfJ3PxGs2YzMngATHZajKVbDkjtzdPIb2VgufAY_IV3nLrnyykfyseQuJUQpSngpPH60Ki_sb9S1QaZyBJH_VkwiJAlc9bxNWw_707T4HnT4jEHSl2ZJBOEKnZ0V7Vkeub74hD9DWLnpUvSmvA1iDPePOAsYK8LMwUm5B-Pm5h9BJVLHSFBDIC-ZJGcC7mPp9ClhuCYqMgRrtU1g5dfTE4XB1FDGfAhcHodb5ewh5yz_keyxmi1Q8ZgszSDAtWoT3u9Z3gU9G7fsLsmCWmpuLI7VV_NFKnekG-IYWQZIT_YBc47N1m7-8hHYiIzfUupB8fR_y8-fMR3bx5wypwRGJNzmW2O-x3L9EF9avwaLjSSYPBnTq8XwIvaqsku5Axz3K5inKF26xXEmIrFRtg4aRuXVKvk5A6lqloSFHwa6VhC9x2T-oWGd6PHskvqVYgFsJNm_Ft_2mWbZOQT5s2wFVZ7kKhgkJfujOInrX2pkJHQLeQRzMN0qk_ghgymYFGbFJgAjY7FcZvo_uv2v2t6jEqXf5zHt0sJhBrkG6dQ4iFPCxfZeT-95Mps8gDYKn41rNK3j-dKcp4GbMctBXQuuP-bo0bFvljBXL9EyX-V-EP3TWVVLkBJk0lKnFXAF-Ag1QeKYhqVW66WBm54tkrqPslgS0KM4XmHo3KS7YUPIPzqTOc1tkIe2m2xJdBUa_m-dGMuRYpx9FPZG1ZjrB9b8vO153Oohmc6vcd5CB9ATIQ4nm11Eg1GgqYHhJFflQQZd_sXbEKW9kohXnrfwxXotfz9iCc3eAfcKpg5rtMxmU2zVQa94MgSMyramRb5cOzwgjKJ8XTZMTb-4RHmXkeePWROZCX4RycmKhRjulgRqibeFekJsyuRCUdJWCGupFiTx8KN-Pm4CSasyzrQUI2kZMknc-DC7ChnSQ11BLPEFw0k2YLPLOtv6ZxPgsay7daJOZCBhdu27WZW5NvgVeT68Db4zbZM9RxlETQLqmdFnOb7CS10_TcRnyS2uTSUEdRMkmcktqOO03fP03teOB1TlKrTBveBJJO5Ja8EfOZ3TzJ63vN2AbFaytee493U4ANt5s0k9Y20xPPa7mH3EYQswy_FiVbB8QjXhlJ0ui4bWXR0SYdm9boVKYxDbDsUKMLkAumtvRdeRPSfAYLnCUBLmNIGF7akIb8A9WWjP8lxGKjKcVqOqNBwuYZ7lb6zvZS_IJlW4i-cF2x4jkNWl5bc9Dgnb7RwHF8q9VouE7L8Xyv46jTNQ06DavjN2xHNU6r7bn-R43-p63aVst3_ZbtN_0W_rpNr0YhTvHtuyu-qvXH9ccPvZmDjA?type=png)](https://mermaid.ai/live/edit#pako:eNqVVm1v4jgQ_iuWK626EuQSQiDkw0kttCvu6JYrZXW65rQyyQRyBZtzQluu6n_fsWNCeDu0_VDs8TPPvHqcdxqJGGhA6_V6yCPBk3QahJyQOVuLVR6QmE0lhFwfJ3PxGs2YzMngATHZajKVbDkjtzdPIb2VgufAY_IV3nLrnyykfyseQuJUQpSngpPH60Ki_sb9S1QaZyBJH_VkwiJAlc9bxNWw_707T4HnT4jEHSl2ZJBOEKnZ0V7Vkeub74hD9DWLnpUvSmvA1iDPePOAsYK8LMwUm5B-Pm5h9BJVLHSFBDIC-ZJGcC7mPp9ClhuCYqMgRrtU1g5dfTE4XB1FDGfAhcHodb5ewh5yz_keyxmi1Q8ZgszSDAtWoT3u9Z3gU9G7fsLsmCWmpuLI7VV_NFKnekG-IYWQZIT_YBc47N1m7-8hHYiIzfUupB8fR_y8-fMR3bx5wypwRGJNzmW2O-x3L9EF9avwaLjSSYPBnTq8XwIvaqsku5Axz3K5inKF26xXEmIrFRtg4aRuXVKvk5A6lqloSFHwa6VhC9x2T-oWGd6PHskvqVYgFsJNm_Ft_2mWbZOQT5s2wFVZ7kKhgkJfujOInrX2pkJHQLeQRzMN0qk_ghgymYFGbFJgAjY7FcZvo_uv2v2t6jEqXf5zHt0sJhBrkG6dQ4iFPCxfZeT-95Mps8gDYKn41rNK3j-dKcp4GbMctBXQuuP-bo0bFvljBXL9EyX-V-EP3TWVVLkBJk0lKnFXAF-Ag1QeKYhqVW66WBm54tkrqPslgS0KM4XmHo3KS7YUPIPzqTOc1tkIe2m2xJdBUa_m-dGMuRYpx9FPZG1ZjrB9b8vO153Oohmc6vcd5CB9ATIQ4nm11Eg1GgqYHhJFflQQZd_sXbEKW9kohXnrfwxXotfz9iCc3eAfcKpg5rtMxmU2zVQa94MgSMyramRb5cOzwgjKJ8XTZMTb-4RHmXkeePWROZCX4RycmKhRjulgRqibeFekJsyuRCUdJWCGupFiTx8KN-Pm4CSasyzrQUI2kZMknc-DC7ChnSQ11BLPEFw0k2YLPLOtv6ZxPgsay7daJOZCBhdu27WZW5NvgVeT68Db4zbZM9RxlETQLqmdFnOb7CS10_TcRnyS2uTSUEdRMkmcktqOO03fP03teOB1TlKrTBveBJJO5Ja8EfOZ3TzJ63vN2AbFaytee493U4ANt5s0k9Y20xPPa7mH3EYQswy_FiVbB8QjXhlJ0ui4bWXR0SYdm9boVKYxDbDsUKMLkAumtvRdeRPSfAYLnCUBLmNIGF7akIb8A9WWjP8lxGKjKcVqOqNBwuYZ7lb6zvZS_IJlW4i-cF2x4jkNWl5bc9Dgnb7RwHF8q9VouE7L8Xyv46jTNQ06DavjN2xHNU6r7bn-R43-p63aVst3_ZbtN_0W_rpNr0YhTvHtuyu-qvXH9ccPvZmDjA)
   - 
>>>>>>> 1e3f658e7f2854f960a02930684cb071e7286a24
