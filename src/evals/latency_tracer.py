"""Latency, token consumption, and cost tracing for RAGOps."""

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class StepTrace:
    """Telemetry record for a single pipeline step."""
    step_name: str
    duration_ms: float
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0


@dataclass
class ExecutionTraceSummary:
    """Full execution trace telemetry report."""
    total_duration_ms: float
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    steps: List[StepTrace] = field(default_factory=list)


class LatencyTracer:
    """Instruments and benchmarks execution latency and cloud API costs."""

    # Pricing per million tokens (Gemini 1.5 Flash baseline)
    INPUT_COST_PER_MILLION: float = 0.075
    OUTPUT_COST_PER_MILLION: float = 0.300

    def __init__(self):
        self.steps: List[StepTrace] = []
        self._start_time: float = time.perf_counter()

    @contextmanager
    def trace_step(
        self,
        step_name: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ):
        """Context manager measuring execution duration of a block."""
        t0 = time.perf_counter()
        try:
            yield
        finally:
            duration_ms = (time.perf_counter() - t0) * 1000.0
            cost = (
                (input_tokens / 1_000_000.0) * self.INPUT_COST_PER_MILLION
                + (output_tokens / 1_000_000.0) * self.OUTPUT_COST_PER_MILLION
            )
            self.steps.append(
                StepTrace(
                    step_name=step_name,
                    duration_ms=round(duration_ms, 2),
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    estimated_cost_usd=round(cost, 6),
                )
            )

    def get_summary(self) -> ExecutionTraceSummary:
        """Computes aggregate execution metrics."""
        total_duration = (time.perf_counter() - self._start_time) * 1000.0
        total_in = sum(s.input_tokens for s in self.steps)
        total_out = sum(s.output_tokens for s in self.steps)
        total_cost = sum(s.estimated_cost_usd for s in self.steps)

        return ExecutionTraceSummary(
            total_duration_ms=round(total_duration, 2),
            total_input_tokens=total_in,
            total_output_tokens=total_out,
            total_cost_usd=round(total_cost, 6),
            steps=self.steps,
        )
