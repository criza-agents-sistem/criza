"""Acumulador de tokens por agente. Sin dependencias externas.

Uso estándar en run_agent():

    tracker = TokenTracker(agent=_AGENTE, oportunidad_id=oportunidad_id or "test", model=model)
    # dentro del loop agéntico, después de cada messages.create():
    tracker.add(response.usage)
    # al final del agente:
    tracker.log(verbose)
    # write-back al KM (merge: no sobreescribe datos de otros agentes):
    if oportunidad_id:
        existing = oportunidad_dict.get("props", {}).get("token_usage", {}) or {}
        existing[tracker.agent] = tracker.to_dict()
        await motor_api.actualizar_props(oportunidad_id, {"token_usage": existing}, tenant=_TENANT)
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class TokenTracker:
    agent: str
    oportunidad_id: str
    model: str
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    _started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def add(self, usage) -> None:
        self.calls += 1
        self.input_tokens += usage.input_tokens
        self.output_tokens += usage.output_tokens

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens

    def to_dict(self) -> dict:
        return {
            "agent": self.agent,
            "model": self.model,
            "calls": self.calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total,
            "started_at": self._started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }

    def log(self, verbose: bool = True) -> None:
        if verbose:
            print(
                f"\n[TOKENS] {self.agent} | {self.calls} llamadas | "
                f"in: {self.input_tokens:,} | out: {self.output_tokens:,} | "
                f"total: {self.total:,} | modelo: {self.model}"
            )
