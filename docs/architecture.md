# Architecture

Visual reference for Agent Bazaar. Diagrams use [Mermaid](https://mermaid.js.org/); they render on GitHub and in most Markdown viewers.

**Related:** [Negotiation protocol](./protocol.md) · [Project plan](../PLAN.md)

---

## Table of contents

1. [Protocol stack](#1-protocol-stack)
2. [System context](#2-system-context)
3. [Runtime components](#3-runtime-components)
4. [Package map](#4-package-map)
5. [Discovery and parallel negotiation](#5-discovery-and-parallel-negotiation)
6. [Single negotiation sequence](#6-single-negotiation-sequence)
7. [Message anatomy](#7-message-anatomy)
8. [Merchant agent internals](#8-merchant-agent-internals)
9. [Buyer agent internals](#9-buyer-agent-internals)
10. [Negotiation state machine](#10-negotiation-state-machine)
11. [Human-in-the-loop](#11-human-in-the-loop)
12. [Deal record flow](#12-deal-record-flow)
13. [Deployment (demo)](#13-deployment-demo)
14. [Security phases](#14-security-phases)
15. [A2A concept mapping](#15-a2a-concept-mapping)

---

## 1. Protocol stack

Agent Bazaar does not replace A2A. It adds a **negotiation profile** on top.

```mermaid
flowchart TB
    subgraph apps ["Application layer"]
        UI[Demo UI / CLI]
        BA[Buyer Agent]
        MA[Merchant Agents]
    end

    subgraph bazaar ["Agent Bazaar layer"]
        EXT[Bazaar extension<br/>offer · counter · accept]
        SM[NegotiationSession<br/>state machine]
        DR[Deal Record<br/>canonical hash]
        DIR[Directory<br/>registry + catalog]
    end

    subgraph transport ["Transport layer"]
        A2A[A2A Protocol<br/>Tasks · Messages · Agent Cards]
    end

    subgraph tools ["Tool layer"]
        MCP[MCP<br/>inventory · pricing · CRM]
    end

    subgraph future ["Future / out of scope v1"]
        AP2[AP2 / payment rails]
    end

    UI --> BA
    BA --> EXT
    MA --> EXT
    EXT --> SM
    SM --> A2A
    BA --> DIR
    MA --> DIR
    MA --> MCP
    DR --> AP2

    style bazaar fill:#e8f4ea,stroke:#2d6a4f
    style transport fill:#dbeafe,stroke:#1d4ed8
    style future fill:#f3f4f6,stroke:#9ca3af,stroke-dasharray: 5 5
```

| Layer | Protocol / component | Role |
| --- | --- | --- |
| Tool | MCP | Merchant reads catalog, floor price, stock |
| Transport | A2A | Agent discovery, task lifecycle, streaming |
| Negotiation | Bazaar extension | Typed commercial acts in `data` parts |
| Registry | Directory | Who sells what; not on the wire during haggle |
| Settlement | AP2 (later) | Pay after `accept` |

---

## 2. System context

One human shopping trip, multiple merchant agents competing.

```mermaid
C4Context
    title System context — Agent Bazaar (v1 demo)

    Person(buyer, "Human buyer", "Sets mandate: SKU, max price, terms")
    System(bazaar, "Agent Bazaar", "Directory + buyer agent + merchant agents + protocol")
    System_Ext(llm, "LLM API", "Strategy suggestions only")
    System_Ext(mcp, "Merchant MCP tools", "Inventory, pricing rules")

    Rel(buyer, bazaar, "Mandate + approve if over limit")
    Rel(bazaar, llm, "Optional counter strategy")
    Rel(bazaar, mcp, "Policy inputs")
```

```mermaid
flowchart LR
    subgraph human ["Human"]
        U[Buyer]
    end

    subgraph platform ["Agent Bazaar platform"]
        UI[Demo UI]
        DIR[(Directory)]
        BAG[Buyer Agent]
    end

    subgraph merchants ["Merchant agents"]
        M1[Premium Audio Co]
        M2[Budget Electronics]
        M3[Warranty Plus Shop]
    end

    U -->|mandate| UI
    UI --> BAG
    BAG -->|search SKU| DIR
    DIR -.->|Agent Cards| M1
    DIR -.->|Agent Cards| M2
    DIR -.->|Agent Cards| M3
    BAG <-->|A2A Tasks| M1
    BAG <-->|A2A Tasks| M2
    BAG <-->|A2A Tasks| M3
```

---

## 3. Runtime components

```mermaid
flowchart TB
    subgraph client_side ["Client side"]
        UI[Demo UI / CLI]
        BA[Buyer Agent]
        BM[(Buyer Mandate)]
        BS[Buyer Strategy<br/>LLM optional]
    end

    subgraph shared ["Shared infrastructure"]
        DIR[Directory Service]
        PROTO[protocol package<br/>state machine + schemas]
    end

    subgraph merchant_side ["Merchant side × N"]
        MA[Merchant Agent]
        POL[Policy Engine]
        CAT[(Catalog JSON)]
        MS[Merchant Strategy<br/>LLM optional]
    end

    UI --> BA
    BA --> BM
    BA --> BS
    BA --> PROTO
    BA --> DIR
    BA <-->|A2A JSON-RPC| MA
    MA --> POL
    MA --> CAT
    MA --> MS
    MA --> PROTO
    DIR -->|registers| MA
```

**Separation of concerns:** the LLM never advances session state. Only `packages/protocol` mutates turns, sequences, and terminal states.

---

## 4. Package map

```mermaid
flowchart LR
    subgraph repo ["agent-bazaar monorepo"]
        subgraph schemas ["schemas/"]
            S1[goods-terms.schema.json]
            S2[offer.schema.json]
        end

        subgraph packages ["packages/"]
            P[protocol ✓]
            D[directory]
            B[buyer-agent]
            M[merchant-agent]
        end

        subgraph apps ["apps/"]
            DEMO[demo]
        end

        subgraph docs ["docs/"]
            ARCH[architecture.md]
            PROT[protocol.md]
        end
    end

    B --> P
    M --> P
    D --> P
    DEMO --> B
    DEMO --> D
    P --> S1
    P --> S2
```

---

## 5. Discovery and parallel negotiation

One `contextId` groups every Task opened for the same shopping trip.

```mermaid
sequenceDiagram
    autonumber
    actor Human
    participant UI as Demo UI
    participant BA as Buyer Agent
    participant DIR as Directory
    participant M1 as Merchant A
    participant M2 as Merchant B
    participant M3 as Merchant C

    Human->>UI: Set mandate (SKU, max $80, 24mo warranty)
    UI->>BA: Start shopping trip
    BA->>DIR: GET /search?sku=WH-1000XM5
    DIR-->>BA: [AgentCard A, B, C]

    Note over BA: contextId = ctx-trip-001

    par Parallel negotiations
        BA->>M1: SendMessage(offer) → Task task-a
        BA->>M2: SendMessage(offer) → Task task-b
        BA->>M3: SendMessage(offer) → Task task-c
    end

    M1-->>BA: counteroffer $85
    M2-->>BA: counteroffer $79
    M3-->>BA: counteroffer $82 + 36mo warranty

    BA->>M2: SendMessage(counteroffer $77)
    M2-->>BA: counteroffer $78

    BA->>M2: SendMessage(accept)
    M2-->>BA: Task COMPLETED + Deal Record artifact

    BA->>UI: Best deal: Merchant B @ $78
    UI->>Human: Confirm deal timeline
```

---

## 6. Single negotiation sequence

Detail for **one** buyer ↔ merchant pair (one A2A Task).

```mermaid
sequenceDiagram
    autonumber
    participant BA as Buyer Agent
    participant A2A as A2A transport
    participant MA as Merchant Agent
    participant POL as Policy Engine
    participant LLM as LLM (optional)

    BA->>A2A: SendMessage<br/>data: offer $85<br/>text: "Looking for XM5"
    A2A->>MA: Deliver message
    MA->>MA: Parse Bazaar act
    MA->>POL: Check vs floor ($75) & catalog
    POL-->>MA: counter allowed @ $82
    MA->>LLM: Suggest lever (price vs warranty)
    LLM-->>MA: "Counter at $82, mention fast ship"
    MA->>A2A: Task NEGOTIATING<br/>data: counteroffer $82<br/>text: friendly prose
    A2A-->>BA: Stream / poll update

    BA->>A2A: SendMessage<br/>data: counteroffer $78
    A2A->>MA: Deliver (same taskId)
    MA->>POL: $78 above floor → accept band
    MA->>A2A: Task COMPLETED<br/>data: accept<br/>artifact: Deal Record
    A2A-->>BA: Final task state
```

---

## 7. Message anatomy

Every commercial turn is an A2A **Message** with two layers.

```mermaid
flowchart TB
    subgraph a2a_msg ["A2A Message"]
        META[messageId · role · taskId · contextId]
        subgraph parts ["parts[]"]
            DATA["data part — BINDING<br/>Bazaar act JSON"]
            TEXT["text part — NON-BINDING<br/>LLM prose for UX"]
        end
    end

    subgraph act ["Bazaar act (inside data part)"]
        ENV[schema · actId · sequence · round]
        PAY[ payload.terms<br/>sku · unitPriceCents · warrantyMonths · … ]
    end

    DATA --> ENV
    DATA --> PAY

    style DATA fill:#fef3c7,stroke:#d97706
    style TEXT fill:#f3f4f6,stroke:#9ca3af
    style PAY fill:#dcfce7,stroke:#16a34a
```

---

## 8. Merchant agent internals

```mermaid
flowchart TB
    IN[A2A SendMessage inbound]
    PARSE[Parse data part → NegotiationAct]
    VAL[protocol: validate turn + sequence]
    POL[Policy engine<br/>floor · max discount · levers]
    HIT{Within policy?}
    APPROVE{Above approval<br/>threshold?}
    LLM[LLM strategy<br/>which lever to move]
    OUT[Build response Message]
    A2AOUT[A2A Task / Message outbound]

    IN --> PARSE --> VAL
    VAL --> POL --> HIT
    HIT -->|no| OUT
    HIT -->|yes| APPROVE
    APPROVE -->|yes| INPUT[input-required pause]
    APPROVE -->|no| LLM --> OUT
    OUT --> A2AOUT
    INPUT --> A2AOUT

    style POL fill:#dbeafe,stroke:#2563eb
    style LLM fill:#f3e8ff,stroke:#9333ea
    style VAL fill:#dcfce7,stroke:#16a34a
```

---

## 9. Buyer agent internals

```mermaid
flowchart TB
    MAND[Buyer Mandate]
    DIR[Directory search]
    OPEN[Open N A2A Tasks]
    LOOP[Per-task loop]
    STRAT[LLM: counter strategy]
    PROTO[protocol: validate + apply act]
    MOK{Meets mandate?}
    HUMAN{Needs human?}
    PICK[Compare completed deals]
    BEST[Select winner]

    MAND --> DIR --> OPEN --> LOOP
    LOOP --> STRAT --> PROTO --> MOK
    MOK -->|no| STRAT
    MOK -->|yes, over max| HUMAN
    MOK -->|yes| PICK
    HUMAN -->|approved| PICK
    PICK --> BEST

    style PROTO fill:#dcfce7,stroke:#16a34a
    style MAND fill:#fef3c7,stroke:#d97706
```

---

## 10. Negotiation state machine

Implemented in `packages/protocol`. One instance per A2A Task.

```mermaid
stateDiagram-v2
    [*] --> ACTIVE: Task created

    ACTIVE --> NEGOTIATING: offer (initiator)
    ACTIVE --> WITHDRAWN: withdraw

    NEGOTIATING --> NEGOTIATING: counteroffer (turn flip)
    NEGOTIATING --> NEGOTIATING: reject (turn to rejector)
    NEGOTIATING --> COMPLETED: accept
    NEGOTIATING --> REJECTED: reject at max rounds
    NEGOTIATING --> WITHDRAWN: withdraw
    NEGOTIATING --> EXPIRED: round / session timeout

    COMPLETED --> [*]
    REJECTED --> [*]
    WITHDRAWN --> [*]
    EXPIRED --> [*]
```

**Turn rule:** after an offer or counteroffer, only the **receiver** may send the next commercial act.

---

## 11. Human-in-the-loop

When a deal exceeds the buyer mandate or merchant approval threshold.

```mermaid
sequenceDiagram
    autonumber
    actor Human
    participant BA as Buyer Agent
    participant MA as Merchant Agent

    BA->>MA: counteroffer $90
    Note over BA: mandate max = $80
    BA->>BA: protocol blocks auto-accept
    BA->>Human: input-required: approve $90?
    alt Human rejects
        Human->>BA: reject
        BA->>MA: withdraw or counter lower
    else Human approves
        Human->>BA: approve
        BA->>MA: SendMessage(accept)
        MA-->>BA: COMPLETED + Deal Record
    end
```

A2A mapping: `TASK_STATE_INPUT_REQUIRED` on the buyer's upstream Task (or merchant-side for manager approval).

---

## 12. Deal record flow

```mermaid
flowchart LR
    subgraph negotiation ["Negotiation transcript"]
        O1[offer seq 1]
        O2[counter seq 2]
        O3[counter seq 3]
        A4[accept seq 4]
    end

    subgraph record ["Deal Record artifact"]
        TERMS[Accepted terms JSON]
        PARTIES[Buyer + merchant IDs]
        TH[transcriptHash]
        RH[recordHash]
    end

    O1 --> O2 --> O3 --> A4
    A4 --> TERMS
    A4 --> PARTIES
    O1 & O2 & O3 & A4 --> TH
    TERMS & PARTIES & TH --> RH

    subgraph verify ["Both parties"]
        V1[Buyer computes RH]
        V2[Merchant computes RH]
    end

    RH --> V1
    RH --> V2
    V1 -.->|must match| V2
```

v1: SHA-256 over canonical JSON. Later: Ed25519 dual signatures.

---

## 13. Deployment (demo)

Phase 1–2 local layout.

```mermaid
flowchart TB
    subgraph host ["localhost"]
        UI[Demo UI :3000]
        DIR[Directory :8000]
        BAG[Buyer Agent :8010]
        M1[Merchant A :8001]
        M2[Merchant B :8002]
        M3[Merchant C :8003]
    end

    UI --> BAG
    BAG --> DIR
    BAG --> M1
    BAG --> M2
    BAG --> M3

    subgraph data ["Static data (v1)"]
        C1[catalog-a.json]
        C2[catalog-b.json]
        C3[catalog-c.json]
    end

    M1 --> C1
    M2 --> C2
    M3 --> C3
```

Phase 2 adds Docker Compose to run this stack with one command.

---

## 14. Security phases

```mermaid
timeline
    title Security maturity
    section v1 demo
        API keys : localhost HTTPS optional
        Self-declared mandates : buyer + merchant JSON
        Deal hash : SHA-256 canonical JSON
    section v2
        Agent Card securitySchemes : OAuth / API key
        Signed deal records : Ed25519
    section v3
        Mandate VCs : org-attested authority
        AP2 handoff : payment after accept
```

---

## 15. A2A concept mapping

```mermaid
flowchart LR
    subgraph bazaar ["Bazaar concept"]
        B1[Shopping trip]
        B2[Negotiation session]
        B3[Offer / counter]
        B4[Human pause]
        B5[Agreed deal]
        B6[Walk away]
    end

    subgraph a2a ["A2A concept"]
        A1[contextId]
        A2[Task]
        A3[Message + data part]
        A4[TASK_STATE_INPUT_REQUIRED]
        A5[Task COMPLETED + Artifact]
        A6[reject / withdraw → terminal Task]
    end

    B1 --> A1
    B2 --> A2
    B3 --> A3
    B4 --> A4
    B5 --> A5
    B6 --> A6
```

| Bazaar | A2A |
| --- | --- |
| Shopping trip | `contextId` |
| Negotiation session | `Task` |
| Offer / counter | `Message` with `data` part (+ optional `text`) |
| Human pause | `TASK_STATE_INPUT_REQUIRED` |
| Agreed deal | `Task` → `COMPLETED` + `Artifact` |
| Walk away | `reject` / `withdraw` → terminal Task |

---

## Component summaries

### Directory

- Stores merchant **Agent Cards** and catalog index
- `GET /merchants`, `GET /search?q=…`
- Self-register in v1 (`POST /merchants`, API key)

### Buyer agent

A2A **client**: mandate → directory search → parallel Tasks → pick best Deal Record.

### Merchant agent

A2A **server**: Agent Card + policy engine + optional LLM → counters within floor/ceiling.

### Protocol package

Shared state machine, schema validation, deal hashing. No HTTP, no LLM.
