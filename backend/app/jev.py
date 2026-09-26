"""Official TypeSafe SDK adapter for Jev typed intent decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from typesafe_sdk import Choice, TypeSafeClient

ChatIntent = Literal["question", "change_request", "other"]


@dataclass(frozen=True)
class IntentDecision:
    intent: ChatIntent
    confidence: float
    probabilities: dict[str, float]
    raw_response: dict


class JevClient:
    def __init__(self, *, api_key: str, model: str, timeout_seconds: float = 10.0) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds

    def classify_chat_intent(self, message: str) -> IntentDecision:
        with TypeSafeClient(api_key=self._api_key, model=self._model, timeout=self._timeout_seconds) as client:
            result = client.system_one(
                state={"message": message},
                questions={
                    "intent": Choice(
                        instructions="Classify `message` for a purchase-order assistant.",
                        criteria={
                            "question": "The user requests information about the current or historical purchase order.",
                            "change_request": "The user asks to change a purchase-order field or line item.",
                            "other": "The message is neither an order question nor a request to change an order.",
                        },
                    )
                },
            )
        answer = result.choices["intent"]
        if answer.choice not in {"question", "change_request", "other"}:
            raise ValueError("TypeSafe returned an unsupported chat intent")
        raw_response = result.model_dump(mode="json") if hasattr(result, "model_dump") else {"model": self._model}
        return IntentDecision(
            intent=answer.choice,
            confidence=float(answer.confidence),
            probabilities={key: float(value) for key, value in answer.probabilities.items()},
            raw_response=raw_response,
        )