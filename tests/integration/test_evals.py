"""Integration test suite for RAGOps CI/CD Benchmarking Harness."""

import time
from pathlib import Path

import numpy as np
import pytest

from src.evals.benchmark_runner import BenchmarkRunner
from src.evals.latency_tracer import LatencyTracer
from src.evals.ragas_eval import EvaluationSample, RagasEvaluator
from src.ingestion.docai_parser import DocumentChunk
from src.vector_store.embeddings import VertexMultimodalEmbedder
from src.vector_store.local_store import LocalVectorStore


def test_latency_tracer_telemetry():
    """Verify latency tracer records step durations and estimated token costs."""
    tracer = LatencyTracer()

    with tracer.trace_step("retriever_test", input_tokens=1000, output_tokens=0):
        time.sleep(0.01)

    with tracer.trace_step("generator_test", input_tokens=500, output_tokens=200):
        time.sleep(0.01)

    summary = tracer.get_summary()

    assert summary.total_duration_ms >= 20.0
    assert summary.total_input_tokens == 1500
    assert summary.total_output_tokens == 200
    assert summary.total_cost_usd > 0.0
    assert len(summary.steps) == 2


def test_ragas_evaluator_metrics():
    """Verify RagasEvaluator computes faithfulness, relevance, and precision."""
    evaluator = RagasEvaluator(min_faithfulness=0.80, min_relevance=0.75)

    sample = EvaluationSample(
        question="What was Q3 revenue?",
        contexts=["Q3 revenue expanded 18% YoY to reach $142.1 million in fiscal 2026."],
        answer="Q3 revenue was $142.1 million with 18% YoY growth.",
    )

    scores = evaluator.evaluate_sample(sample)

    assert scores["faithfulness"] >= 0.80
    assert scores["answer_relevance"] >= 0.75
    assert scores["context_precision"] == 1.0


@pytest.mark.ragops_benchmark
def test_benchmark_runner_gate(tmp_path: Path):
    """Verify automated CI/CD benchmark runner executes and generates markdown report."""
    store = LocalVectorStore(index_dir=tmp_path / "eval_index")
    embedder = VertexMultimodalEmbedder()

    chunks = [
        DocumentChunk(
            chunk_id="chunk_sec_1",
            doc_id="sec_report",
            page_number=1,
            content_type="text",
            content="Total operating revenue for the enterprise in fiscal 2026 was $142.1 million, an 18.2% expansion YoY.",
            metadata={"topic": "revenue"},
        ),
        DocumentChunk(
            chunk_id="chunk_sec_2",
            doc_id="sec_report",
            page_number=2,
            content_type="table",
            content="| Segment | Operating Margin |\n| Cloud | 28% |\n| Hardware | 14% |",
            metadata={"topic": "margins"},
        ),
    ]

    embeddings = np.vstack([embedder.embed_text(c.content) for c in chunks])
    store.add_chunks(chunks, embeddings)

    runner = BenchmarkRunner(vector_store=store)
    report_file = tmp_path / "eval_report.md"

    report = runner.run_benchmark(
        test_prompts=[
            {
                "question": "What was the total operating revenue for the enterprise in fiscal 2026?",
                "ground_truth": "Operating revenue was $142.1 million.",
            }
        ],
        report_path=report_file,
    )

    assert report.total_samples == 1
    assert report.faithfulness >= 0.70
    assert report_file.exists()

    report_content = report_file.read_text(encoding="utf-8")
    assert "# RAGOps CI/CD Benchmark Report" in report_content
    assert "Faithfulness" in report_content
