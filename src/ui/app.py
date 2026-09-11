"""Streamlit Multimodal Cockpit for Enterprise Corrective RAG (CRAG)."""

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import requests
import streamlit as st
from PIL import Image

from config.settings import settings
from src.crag.graph import run_crag
from src.vector_store.local_store import LocalVectorStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("crag_cockpit")

# Page config
st.set_page_config(
    page_title="Enterprise Multimodal CRAGOps",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown(
    """
    <style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(90deg, #4285F4, #34A853, #FBBC05, #EA4335);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #80868B;
        margin-bottom: 1.5rem;
    }
    .crag-card {
        border-radius: 8px;
        padding: 16px;
        background-color: #1E1E2E;
        border: 1px solid #313244;
        margin-bottom: 12px;
    }
    .status-badge-relevant {
        background-color: #0F5132;
        color: #D1E7DD;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .status-badge-partially {
        background-color: #664D03;
        color: #FFF3CD;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .status-badge-fallback {
        background-color: #842029;
        color: #F8D7DA;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .metric-container {
        display: flex;
        gap: 16px;
        margin: 12px 0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# App Header
st.markdown('<div class="main-header">⚡ Enterprise Corrective Multimodal RAGOps</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">GCP Document AI Layout Parser • Vertex AI Multimodal Embeddings (1408-d) • LangGraph CRAG • Gemini Flash Grounding</div>',
    unsafe_allow_html=True,
)

# Sidebar
with st.sidebar:
    st.header("⚙️ Platform Controls")
    execution_mode = st.radio(
        "Execution Mode",
        ["Direct LangGraph Engine", "FastAPI Service (HTTP)"],
        index=0,
    )

    api_base_url = st.text_input("FastAPI Endpoint", value="http://localhost:8000")

    st.markdown("---")
    st.subheader("Cloud Architecture")
    st.info(
        f"**Project**: `{settings.gcp_project_id}`\n\n"
        f"**Region**: `{settings.gcp_region}`\n\n"
        f"**DocAI Processor**: `{settings.document_ai_processor_id}`\n\n"
        f"**Embedding Model**: `{settings.vertex_multimodal_embedding_model}`\n\n"
        f"**LLM**: `{settings.gemini_llm_model}`"
    )

    # Ingestion section
    st.markdown("---")
    st.subheader("📄 Document Ingestion")
    uploaded_file = st.file_uploader("Upload Financial / Enterprise PDF", type=["pdf"])
    if uploaded_file and st.button("Run Document AI Ingestion", use_container_width=True):
        with st.spinner("Processing PDF via Document AI Layout Parser..."):
            save_path = settings.raw_data_dir / uploaded_file.name
            settings.raw_data_dir.mkdir(parents=True, exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(uploaded_file.getvalue())

            try:
                from src.ingestion.pipeline import IngestionPipeline
                from src.vector_store.indexer import MultimodalIndexer

                pipeline = IngestionPipeline()
                doc = pipeline.ingest_document(save_path)
                indexer = MultimodalIndexer()
                indexer.index_chunks(doc.chunks)
                st.success(f"Indexed {len(doc.chunks)} chunks ({len(doc.tables)} tables, {len(doc.charts)} charts)!")
            except Exception as e:
                st.error(f"Ingestion failed: {e}")

# Sample queries
st.markdown("##### Quick Queries")
col1, col2, col3 = st.columns(3)
selected_query = None
with col1:
    if st.button("📊 Operating Revenue & Margin Breakdown", use_container_width=True):
        selected_query = "What was the operating revenue and margin breakdown for fiscal 2026?"
with col2:
    if st.button("📈 Capital Expenditure & Growth Forecast", use_container_width=True):
        selected_query = "Summarize the CapEx and growth outlook from the tables and charts."
with col3:
    if st.button("🔍 Fallback Web Trigger (Out of domain)", use_container_width=True):
        selected_query = "What were the latest SpaceX Starship flight milestones?"

# Main Query input
query_input = st.text_input(
    "Ask a question across multimodal documents (tables, charts, text):",
    value=selected_query or "What was the company's operating revenue in fiscal 2026?",
)

run_button = st.button("🚀 Execute Corrective RAG", type="primary", use_container_width=True)


def display_results(result_data: Dict[str, Any], latency_ms: float):
    grade = result_data.get("overall_grade") or result_data.get("crag_status") or "UNKNOWN"
    generation = result_data.get("final_response") or result_data.get("generation") or "No response"
    citations = result_data.get("citations", [])
    images = result_data.get("extracted_images") or result_data.get("images") or []
    trace = result_data.get("execution_trace") or result_data.get("trace") or []
    retries = result_data.get("retry_count") if "retry_count" in result_data else result_data.get("retries", 0)

    # Status Banner
    badge_class = "status-badge-relevant"
    if "PARTIAL" in str(grade).upper():
        badge_class = "status-badge-partially"
    elif "FALLBACK" in str(grade).upper() or "NOT_RELEVANT" in str(grade).upper():
        badge_class = "status-badge-fallback"

    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        st.metric("CRAG Decision", grade)
    with col_m2:
        st.metric("Latency", f"{latency_ms:.0f} ms")
    with col_m3:
        st.metric("Rewrites / Retries", f"{retries}")
    with col_m4:
        st.metric("Citations Grounded", f"{len(citations)}")

    # Answer Block
    st.markdown("### 💡 Grounded Answer")
    st.markdown(generation)

    # LangGraph Execution Trace
    if trace:
        with st.expander("🔄 LangGraph CRAG Execution Trace", expanded=False):
            st.markdown("State machine progression through conditional edges:")
            for i, step in enumerate(trace, 1):
                st.markdown(f"**Step {i}**: `{step}`")

    # Multimodal Visual Citations
    col_cit, col_vis = st.columns([3, 2])

    with col_cit:
        st.markdown("### 📚 Citations & Provenance")
        if not citations:
            st.info("No explicit document chunks cited.")
        for idx, c in enumerate(citations, 1):
            with st.expander(f"Citation #{idx}: {c.get('chunk_id') or c.get('source') or 'Source'}"):
                st.json(c)

    with col_vis:
        st.markdown("### 🖼️ Multimodal Evidence (Charts & Tables)")
        if not images:
            st.info("No visual chart evidence was cited for this query.")
        for img_path in images:
            if Path(img_path).exists():
                st.image(img_path, caption=f"Extracted Evidence: {Path(img_path).name}", use_column_width=True)


if run_button and query_input:
    start_t = time.perf_counter()
    with st.spinner("Executing CRAG State Graph (Retrieve ➔ Grade ➔ Correct ➔ Synthesize)..."):
        if execution_mode == "FastAPI Service (HTTP)":
            try:
                resp = requests.post(
                    f"{api_base_url}/v1/query",
                    json={"query": query_input, "include_trace": True},
                    timeout=60,
                )
                duration_ms = (time.perf_counter() - start_t) * 1000.0
                if resp.status_code == 200:
                    display_results(resp.json(), duration_ms)
                else:
                    st.error(f"API Error {resp.status_code}: {resp.text}")
            except Exception as e:
                st.error(f"Failed to connect to FastAPI endpoint at {api_base_url}: {e}")
        else:
            # Direct graph execution
            try:
                res = run_crag(query=query_input)
                duration_ms = (time.perf_counter() - start_t) * 1000.0
                display_results(res, duration_ms)
            except Exception as e:
                st.error(f"CRAG execution error: {e}")
