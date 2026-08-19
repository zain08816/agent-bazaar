# Agent Bazaar — Project Plan

An open marketplace where buyer agents discover merchant agents and negotiate price and terms over [A2A](https://a2a-protocol.org/). Natural language is for persuasion; structured offers are the contract.

## Problem

Agentic commerce today (UCP, ACP, AP2) covers discovery → cart → checkout → payment. It does **not** cover bilateral haggling: counter-offers, term tradeoffs, mandate limits, or a tamper-evident deal record.

Enterprise buyers already negotiate via closed platforms (Pactum, Fairmarkit). There is no open, merchant-facing protocol for **your** buyer agent to talk to **my** merchant agent.

## Product vision (v1)

A **closed demo** that proves the loop:

1. Human sets a **mandate** (product, max price, required terms).
2. **Buyer agent** searches the directory, opens parallel negotiations with 2–3 merchant agents.
3. **Merchant agents** counter within policy (floor price, allowed term levers).
4. UI shows the **offer timeline** (structured JSON), not just chat.
5. Buyer agent picks the best deal; both sides emit a **Deal Record** artifact.

No real money, no legal binding, no DIDs in v1.

## Architecture

See **[docs/architecture.md](./docs/architecture.md)** for full diagrams (protocol stack, sequences, state machine, deployment).

High-level:

```
Human → Buyer Agent → Directory (discover merchants)
              ├── A2A + Bazaar extension → Merchant A
              ├── A2A + Bazaar extension → Merchant B
              └── A2A + Bazaar extension → Merchant C
                                              └── MCP → inventory / pricing
```

### Layers

| Layer | Responsibility |
| --- | --- |
| **A2A** | Transport: Agent Cards, Tasks, Messages, `input-required`, streaming |
| **Bazaar extension** | Typed negotiation acts in `data` parts (offer, counter, accept, reject) |
| **Directory** | Registry of merchant Agent Cards + product catalog index |
| **Policy engine** | Deterministic floor/ceiling checks (not LLM) |
| **LLM** | Strategy only: which lever to move, how to phrase the counter |

### What we are NOT building in v1

- Payment (AP2 / Stripe) — stub a `settlement_pending` state only
- Cross-org identity (DIDs, VCs) — use API keys + signed deal hashes
- Full A2CN compatibility — borrow ideas, define our own thin schema
- Public multi-tenant marketplace — local/demo only

## Negotiation protocol (Bazaar profile)

One A2A **Task** = one negotiation session. Same `taskId` until terminal state.

### States

```
invited → offering → countering ⇄ countering → accepted
                                      ↘ rejected
                                      ↘ withdrawn
                                      ↘ expired
                                      ↘ input_required  (human / mandate)
```

### Message acts (`data` part, `schema`: `urn:agent-bazaar:negotiation:v1`)

| Act | Purpose |
| --- | --- |
| `offer` | Opening or counter proposal |
| `accept` | Unconditional yes to the latest offer |
| `reject` | Decline without new terms |
| `withdraw` | End session with no deal |

### Terms (v1 — goods)

```json
{
  "sku": "WH-1000XM5",
  "quantity": 1,
  "unitPriceCents": 7900,
  "currency": "USD",
  "warrantyMonths": 24,
  "shippingDays": 3,
  "returnsDays": 30
}
```

### Rules (from A2CN, simplified)

- Strict **turn-taking**: only the party that received the last offer may respond commercially.
- **One response** per open offer: counter, accept, reject, or withdraw.
- **Integer money** only (cents).
- **Completed tasks are immutable**; refinements = new Task, same `contextId`.
- Text `parts` are non-binding; only `data` acts count.

### Agent Card extension

```json
{
  "uri": "https://agent-bazaar.dev/extensions/negotiate/v1",
  "required": false,
  "params": {
    "dealTypes": ["goods"],
    "directoryUrl": "https://directory.agent-bazaar.dev"
  }
}
```

## Repo layout

```
agent-bazaar/
├── PLAN.md                 ← this file
├── README.md
├── docs/
│   ├── architecture.md
│   └── protocol.md         ← normative schema + state machine
├── schemas/
│   └── negotiation/v1/     ← JSON Schema for acts + terms
├── packages/
│   ├── protocol/           ← validation, state machine (Python)
│   ├── directory/          ← FastAPI registry + search
│   ├── buyer-agent/
│   └── merchant-agent/
└── apps/
    └── demo/               ← CLI or minimal web UI for offer timeline
```

## Phases

### Phase 0 — Foundation (current)

- [x] Plan + protocol sketch
- [ ] JSON schemas for acts and goods terms
- [ ] Python `NegotiationSession` state machine (pure, tested)
- [ ] GitHub repo public

### Phase 1 — Two agents, one deal

- [ ] Merchant agent (A2A server + Bazaar extension + hardcoded catalog)
- [ ] Buyer agent (A2A client + mandate parser)
- [ ] CLI demo: `buy headphones --max 8000 --warranty 24`
- [ ] Deal Record artifact (SHA-256 of canonical JSON, both agent IDs)

### Phase 2 — Mini marketplace

- [ ] Directory service: register merchants, search by SKU/tag
- [ ] 3 merchant agents with different policies (premium / discounter / warranty-focused)
- [ ] Parallel negotiations in one `contextId`; buyer picks winner
- [ ] Simple web UI: offer timeline + mandate display

### Phase 3 — Human in the loop

- [ ] Mandate object on buyer side (max spend, required terms)
- [ ] `input-required` when offer exceeds mandate → human approve in UI
- [ ] Merchant-side policy engine extracted from prompts

### Phase 4 — Hardening (optional)

- [ ] Ed25519 signatures on deal records
- [ ] A2A extension URI registered / aligned with community
- [ ] Services deal type (SLA, timeline, revisions)
- [ ] AP2 handoff stub after `accepted`

## Tech choices

| Choice | Rationale |
| --- | --- |
| **Python 3.12+** | Best A2A SDK story (`a2a-sdk`), FastAPI for directory |
| **JSON Schema** | Portable act definitions; TS/Python codegen later |
| **FastAPI** | Directory + optional merchant HTTP in one stack |
| **No LLM vendor lock** | OpenAI-compatible API interface; mock for tests |

## Open questions (workshop)

1. **Name** — `agent-bazaar` working title. Alternatives: `haggle-a2a`, `deal-desk`.
2. **First deal type** — goods only vs. services contract for demo?
3. **Directory** — centralized registry vs. pure `/.well-known/agent-card.json` crawl?
4. **License** — Apache 2.0 (align with A2A ecosystem) vs MIT?

## Success criteria for v1 demo

- Two merchant agents counter differently on the same SKU.
- Buyer agent runs both in parallel and selects lowest price meeting mandate.
- Every step visible as structured acts, not prose-only.
- Re-running the demo produces identical deal hashes for the same transcript.

## References

- [A2A Protocol](https://a2a-protocol.org/)
- [Life of a Task](https://a2a-protocol.org/latest/topics/life-of-a-task/) — `input-required`, `contextId`
- [A2A Discussion #1737](https://github.com/a2aproject/A2A/discussions/1737) — negotiation as extension
- [A2CN](https://a2cn.io/) — ideas to borrow, not to implement wholesale
- [UCP](https://ucp.dev/) / [AP2](https://ap2-protocol.org/) — downstream checkout/payment
