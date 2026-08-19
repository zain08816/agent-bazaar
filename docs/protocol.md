# Bazaar Negotiation Protocol v1

Extension URI: `https://agent-bazaar.dev/extensions/negotiate/v1`

Schema URN prefix: `urn:agent-bazaar:negotiation:v1`

## Design principles

1. **Structured acts are binding.** Text parts are commentary.
2. **Turn-taking is enforced in code**, not by prompt.
3. **Integer cents** for all money fields.
4. **One currency per session**, fixed at first offer.
5. **A2A Task = session.** Same `taskId` until terminal.

## Envelope

Every negotiation act is a JSON object in an A2A Message `data` part:

```json
{
  "schema": "urn:agent-bazaar:negotiation:v1:offer",
  "actId": "550e8400-e29b-41d4-a716-446655440000",
  "sessionId": "task-id-from-a2a",
  "inReplyTo": null,
  "round": 1,
  "sequence": 1,
  "timestamp": "2026-08-19T05:00:00Z",
  "expiresAt": "2026-08-19T06:00:00Z",
  "payload": { }
}
```

| Field | Required | Description |
| --- | --- | --- |
| `schema` | yes | Act type URN |
| `actId` | yes | UUID for this act |
| `sessionId` | yes | A2A task ID |
| `inReplyTo` | no | `actId` of prior offer (required for counter/accept/reject) |
| `round` | yes | Increments on each counteroffer |
| `sequence` | yes | Monotonic per session, all message types |
| `timestamp` | yes | ISO 8601 UTC |
| `expiresAt` | yes | Offer invalid after this time |
| `payload` | yes | Act-specific body |

## Act types

| Schema suffix | Sender | Effect |
| --- | --- | --- |
| `:offer` | Initiator only (round 1) | Opens negotiation |
| `:counteroffer` | Turn holder | Rejects prior implicitly; new terms |
| `:accept` | Turn holder | Terminal — agree to prior offer |
| `:reject` | Turn holder | Decline prior; turn stays with rejector for new offer |
| `:withdraw` | Either party | Terminal — no deal |

## Goods terms (`payload.terms`)

```json
{
  "dealType": "goods",
  "sku": "WH-1000XM5",
  "title": "Sony WH-1000XM5",
  "quantity": 1,
  "unitPriceCents": 7900,
  "currency": "USD",
  "warrantyMonths": 24,
  "shippingDays": 3,
  "returnsDays": 30,
  "notes": "optional free-text, non-binding"
}
```

### Validation rules

- `unitPriceCents >= 0`, integer
- `quantity >= 1`, integer
- `currency` ISO 4217, immutable after round 1
- `warrantyMonths`, `shippingDays`, `returnsDays` non-negative integers

## Buyer mandate (client-side, not sent on wire in v1)

```json
{
  "sku": "WH-1000XM5",
  "maxUnitPriceCents": 8000,
  "minWarrantyMonths": 24,
  "currency": "USD",
  "quantity": 1
}
```

Buyer agent MUST NOT send `accept` for terms violating mandate without human approval (`input-required`).

## Merchant policy (server-side)

```json
{
  "sku": "WH-1000XM5",
  "listUnitPriceCents": 8999,
  "floorUnitPriceCents": 7500,
  "maxDiscountPercent": 15,
  "allowedLevers": ["unitPriceCents", "warrantyMonths", "shippingDays"],
  "requiresApprovalAboveCents": 8200
}
```

## State machine

```
                    ┌─────────┐
                    │ ACTIVE  │  (task created, no offer yet)
                    └────┬────┘
                         │ offer
                         ▼
                    ┌─────────────┐
         ┌─────────│ NEGOTIATING │─────────┐
         │         └──────┬──────┘         │
         │ counter        │ accept         │ withdraw
         │ (turn flip)    ▼                ▼
         └────────► NEGOTIATING      COMPLETED / WITHDRAWN
                         │
                         │ reject (round < max)
                         ▼
                    NEGOTIATING (turn = rejector)
                         │
                         │ reject (round = max) / timeout
                         ▼
                    REJECTED / EXPIRED
```

### Turn rule

After an offer or counteroffer, **only the receiver** may send: counteroffer, accept, reject, or withdraw.

Withdraw may be sent by either party at any time after session is ACTIVE.

## Deal record (artifact)

Produced on `accept`. Both parties SHOULD compute the same hash.

```json
{
  "schema": "urn:agent-bazaar:negotiation:v1:deal-record",
  "sessionId": "...",
  "contextId": "...",
  "acceptedActId": "...",
  "terms": { },
  "parties": {
    "buyer": { "agentId": "...", "endpoint": "..." },
    "merchant": { "agentId": "...", "endpoint": "..." }
  },
  "transcriptHash": "sha256-of-ordered-act-ids",
  "recordHash": "sha256-of-canonical-record-without-this-field"
}
```

Canonicalization: RFC 8785 JCS (same approach as A2CN, optional in v1 tests).

## Errors

| Code | When |
| --- | --- |
| `NOT_YOUR_TURN` | Act from wrong party |
| `INVALID_SEQUENCE` | Gap or duplicate sequence |
| `EXPIRED_OFFER` | `expiresAt` in the past |
| `MANDATE_EXCEEDED` | Accept would violate buyer mandate |
| `POLICY_VIOLATION` | Counter violates merchant floor |
| `UNKNOWN_SKU` | SKU not in merchant catalog |

Return as A2A agent message text + optional `data` error object; do not advance state.

## Compatibility note

This profile is **A2CN-inspired, not A2CN-compatible**. Field names and transport differ. If A2CN or an A2A standard extension wins later, we can add an adapter layer.
