import pytest

from agent_bazaar import (
    GoodsTerms,
    NegotiationAct,
    NegotiationSession,
    ProtocolError,
    SessionState,
)


def _terms(price: int = 8999) -> GoodsTerms:
    return GoodsTerms(
        sku="WH-1000XM5",
        quantity=1,
        unit_price_cents=price,
        currency="USD",
        warranty_months=12,
    )


def _offer(session: NegotiationSession, seq: int, price: int, kind: str = "offer") -> NegotiationAct:
    return NegotiationAct(
        kind=kind,
        act_id=f"act-{seq}",
        session_id=session.session_id,
        round=session.round if kind != "offer" else 1,
        sequence=seq,
        sender="buyer",
        in_reply_to=None if kind == "offer" else session.latest_offer_act_id,
        terms=_terms(price),
    )


def test_happy_path_offer_counter_accept() -> None:
    session = NegotiationSession(
        session_id="sess-1",
        buyer_agent_id="buyer",
        merchant_agent_id="merchant",
        initiator="buyer",
    )

    offer = _offer(session, 1, 8500)
    session.apply(offer)
    assert session.state == SessionState.NEGOTIATING
    assert session.current_turn == "merchant"

    counter = NegotiationAct(
        kind="counteroffer",
        act_id="act-2",
        session_id="sess-1",
        round=2,
        sequence=2,
        sender="merchant",
        in_reply_to="act-1",
        terms=_terms(8200),
    )
    session.apply(counter)
    assert session.current_turn == "buyer"

    accept = NegotiationAct(
        kind="accept",
        act_id="act-3",
        session_id="sess-1",
        round=2,
        sequence=3,
        sender="buyer",
        in_reply_to="act-2",
    )
    session.apply(accept)
    assert session.state == SessionState.COMPLETED
    assert session.accepted_terms is not None
    assert session.accepted_terms.unit_price_cents == 8200


def test_not_your_turn() -> None:
    session = NegotiationSession(
        session_id="sess-1",
        buyer_agent_id="buyer",
        merchant_agent_id="merchant",
        initiator="buyer",
    )
    session.apply(_offer(session, 1, 8500))

    bad_counter = NegotiationAct(
        kind="counteroffer",
        act_id="act-2",
        session_id="sess-1",
        round=2,
        sequence=2,
        sender="buyer",
        in_reply_to="act-1",
        terms=_terms(8000),
    )
    with pytest.raises(ProtocolError) as exc:
        session.apply(bad_counter)
    assert exc.value.code == "NOT_YOUR_TURN"
