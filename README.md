# Enterprise Corrective Multimodal RAGOps Platform (GCP)

An enterprise-grade multimodal document intelligence platform built on **Google Cloud Platform (GCP)** leveraging **Document AI Layout Parser**, **Vertex AI Multimodal Embeddings**, **LangGraph Corrective RAG (CRAG)**, **Gemini 1.5/2.0 Flash Grounding**, and **Ragas Multimodal Evaluations**.

---

## Key Features

- **Document AI Layout-Aware Ingestion**: Preserves document structure, extracts high-fidelity Markdown tables from multi-column grids, and crops charts/figures using normalized bounding polygons.
- **Unified Vertex Multimodal Embeddings**: Joint 1408-dimensional vector space mapping text blocks, Markdown tables, and cropped chart images via `multimodalembedding@001`.
- **LangGraph Corrective RAG (CRAG)**:
  - Multimodal Hybrid Retrieval across text and visuals.
  - LLM Grader Node for factual relevance filtering.
  - Ambiguity Rewriter Node for query reformulation.
  - External Fallback Search for missing internal context.
  - Grounded Synthesis with Gemini Flash and inline visual citations.
- **RAGOps CI/CD Benchmarking**: Automated evaluation harness using Ragas (Faithfulness, Relevance, Context Precision) with latency and cost tracking.
- **Scale-to-Zero Serverless Deployment**: Cloud Run service configured with `--min-instances 0` and local file-backed vector stores for **$0.00 idle burn**, adhering strictly to the $300 GCP credit limit.

---

## System Architecture

```mermaid
flowchart LR
    Doc[PDF Document] --> DocAI[Document AI Parser]
    DocAI --> Text[Text Chunks]
    DocAI --> Table[Markdown Tables]
    DocAI --> Charts[Cropped Figures]
    
    Text & Table & Charts --> VertexEmbed[Vertex Multimodal Embeddings]
    VertexEmbed --> LocalStore[(Local Vector Store)]
    
    Query[User Query] --> CRAG[LangGraph CRAG Machine]
    LocalStore <--> CRAG
    CRAG --> Gemini[Gemini Grounded Synthesis]
    Gemini --> UI[Streamlit Cockpit & FastAPI]
```

---

## Project Structure

```
.
├── config/                  # Pydantic Settings & GCP YAML configs
│   ├── settings.py
│   ├── logging_config.py
│   └── gcp_config.yaml
├── src/
│   ├── ingestion/           # Document AI parsing, table & chart extraction
│   ├── vector_store/        # Vertex embeddings & local vector store
│   ├── crag/                # LangGraph CRAG nodes, edges, and state machine
│   │   └── nodes/           # Retriever, Grader, Rewriter, Fallback, Generator
│   ├── evals/               # Ragas evaluations & latency tracing
│   ├── api/                 # FastAPI REST application
│   └── ui/                  # Streamlit multimodal dashboard
├── tests/
│   ├── unit/                # Fast, isolated unit tests
│   └── integration/         # CRAG pipeline & Ragas integration tests
├── scripts/                 # Bootstrap & Cost-Guard shutdown scripts
├── data/                    # Local storage (raw, processed, vector_index)
├── Dockerfile               # Multi-stage container for Cloud Run
├── docker-compose.yml       # Local development composition
├── Makefile                 # Automation targets
├── IMPLEMENTATION_PLAN.md   # Master state tracker & roadmap
└── README.md
```

---

## Zero-Idle-Burn Cost Rules ($300 Budget Ceiling)

1. **Development Vector Search**: All active development uses the file-backed local vector store (NumPy cosine / ScaNN). **Never deploy Vertex AI Vector Search Index Endpoints**, which incur continuous hourly node charges ($150-$300+/month).
2. **Cloud Run Serverless Compute**: Deployments must specify `--min-instances 0`. Containers scale to 0 when idle.
3. **Session Shutdown Verification**: Always execute `scripts/cost_guard.ps1` (or `.sh`) before closing a development session.

---

## Quickstart & Environment Setup

### 1. Prerequisites
- Python 3.11+
- Google Cloud SDK (`gcloud`)
- Git

### 2. Setup Virtual Environment
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

### 3. Configure Credentials
Copy the `.env.example` template:
```powershell
cp .env.example .env
# Edit .env and supply your GCP_PROJECT_ID and credentials
```

### 4. Run Verification Tests
```powershell
pytest tests/unit/test_settings.py -v
```

---

## Master Implementation Plan
For step-by-step progress, open and review [IMPLEMENTATION_PLAN.md](file:///d:/Projects/GCP/IMPLEMENTATION_PLAN.md).
