from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class SessionState(str, Enum):
    ACTIVE = "active"
    NEGOTIATING = "negotiating"
    COMPLETED = "completed"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"


class ProtocolError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


Party = Literal["buyer", "merchant"]
ActKind = Literal["offer", "counteroffer", "accept", "reject", "withdraw"]


@dataclass
class GoodsTerms:
    sku: str
    quantity: int
    unit_price_cents: int
    currency: str
    deal_type: str = "goods"
    title: str | None = None
    warranty_months: int | None = None
    shipping_days: int | None = None
    returns_days: int | None = None


@dataclass
class NegotiationAct:
    kind: ActKind
    act_id: str
    session_id: str
    round: int
    sequence: int
    sender: Party
    in_reply_to: str | None = None
    terms: GoodsTerms | None = None


@dataclass
class NegotiationSession:
    """Minimal turn-taking state machine for bilateral goods negotiation."""

    session_id: str
    buyer_agent_id: str
    merchant_agent_id: str
    initiator: Party
    max_rounds: int = 10
    state: SessionState = SessionState.ACTIVE
    round: int = 0
    sequence: int = 0
    current_turn: Party | None = None
    latest_offer_act_id: str | None = None
    transcript: list[NegotiationAct] = field(default_factory=list)
    accepted_terms: GoodsTerms | None = None

    def apply(self, act: NegotiationAct) -> None:
        if self.state in {
            SessionState.COMPLETED,
            SessionState.REJECTED,
            SessionState.WITHDRAWN,
            SessionState.EXPIRED,
        }:
            raise ProtocolError("SESSION_TERMINAL", f"Session is {self.state.value}")

        expected_sequence = self.sequence + 1
        if act.sequence != expected_sequence:
            raise ProtocolError(
                "INVALID_SEQUENCE",
                f"Expected sequence {expected_sequence}, got {act.sequence}",
            )

        if act.kind == "withdraw":
            self._apply_withdraw(act)
            return

        if act.kind in {"offer", "counteroffer"}:
            self._apply_offer(act)
            return

        if act.kind == "accept":
            self._apply_accept(act)
            return

        if act.kind == "reject":
            self._apply_reject(act)
            return

        raise ProtocolError("UNKNOWN_ACT", f"Unknown act kind: {act.kind}")

    def _assert_turn(self, sender: Party) -> None:
        if self.current_turn is not None and sender != self.current_turn:
            raise ProtocolError(
                "NOT_YOUR_TURN",
                f"Expected turn holder {self.current_turn}, got {sender}",
            )

    def _apply_offer(self, act: NegotiationAct) -> None:
        if act.kind == "offer":
            if self.state != SessionState.ACTIVE:
                raise ProtocolError("SESSION_WRONG_STATE", "Offer only allowed in ACTIVE")
            if act.sender != self.initiator:
                raise ProtocolError("NOT_YOUR_TURN", "Only initiator may send opening offer")
            self.round = 1
            self.state = SessionState.NEGOTIATING
            receiver: Party = "merchant" if act.sender == "buyer" else "buyer"
            self.current_turn = receiver
        else:
            if self.state != SessionState.NEGOTIATING:
                raise ProtocolError("SESSION_WRONG_STATE", "Counteroffer requires NEGOTIATING")
            self._assert_turn(act.sender)
            if act.in_reply_to != self.latest_offer_act_id:
                raise ProtocolError("INVALID_REPLY", "inReplyTo must reference latest offer")
            self.round += 1
            if self.round > self.max_rounds:
                raise ProtocolError("MAX_ROUNDS", "Maximum negotiation rounds exceeded")
            receiver = "merchant" if act.sender == "buyer" else "buyer"
            self.current_turn = receiver

        if act.terms is None:
            raise ProtocolError("INVALID_ACT", "Offer acts require terms")

        self._commit(act)
        self.latest_offer_act_id = act.act_id

    def _apply_accept(self, act: NegotiationAct) -> None:
        if self.state != SessionState.NEGOTIATING:
            raise ProtocolError("SESSION_WRONG_STATE", "Accept requires NEGOTIATING")
        self._assert_turn(act.sender)
        if act.in_reply_to != self.latest_offer_act_id:
            raise ProtocolError("INVALID_REPLY", "Accept must reference latest offer")

        latest = self.transcript[-1]
        if latest.terms is None:
            raise ProtocolError("INVALID_ACT", "Cannot accept offer without terms")

        self._commit(act)
        self.accepted_terms = latest.terms
        self.state = SessionState.COMPLETED
        self.current_turn = None

    def _apply_reject(self, act: NegotiationAct) -> None:
        if self.state != SessionState.NEGOTIATING:
            raise ProtocolError("SESSION_WRONG_STATE", "Reject requires NEGOTIATING")
        self._assert_turn(act.sender)
        if act.in_reply_to != self.latest_offer_act_id:
            raise ProtocolError("INVALID_REPLY", "Reject must reference latest offer")

        self._commit(act)

        if self.round >= self.max_rounds:
            self.state = SessionState.REJECTED
            self.current_turn = None
        else:
            self.current_turn = act.sender

    def _apply_withdraw(self, act: NegotiationAct) -> None:
        self._commit(act)
        self.state = SessionState.WITHDRAWN
        self.current_turn = None

    def _commit(self, act: NegotiationAct) -> None:
        self.sequence = act.sequence
        self.transcript.append(act)
