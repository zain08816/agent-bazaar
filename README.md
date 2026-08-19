# Agent Bazaar

A marketplace where buyer agents discover merchant agents and **negotiate price and terms** using [A2A](https://a2a-protocol.org/) plus a thin negotiation extension.

> Checkout protocols (UCP, ACP) handle "buy at list price." Agent Bazaar handles "talk me down."

## Status

**Phase 0** — planning and protocol design. Not production-ready.

## What this is

- **Directory** — find merchant agents and what they sell
- **Bazaar negotiation profile** — structured offers/counters/accepts in A2A `data` parts
- **Buyer + merchant agents** — LLM for strategy, deterministic code for policy and state
- **Deal record** — canonical hash of what both sides agreed to

## What this is not (yet)

- Real payments
- Legal contracts
- A2CN implementation
- A public hosted marketplace

## Docs

- [Project plan](./PLAN.md)
- [Architecture & diagrams](./docs/architecture.md)
- [Negotiation protocol v1](./docs/protocol.md)
- [Contributing](./CONTRIBUTING.md)

## Quick start

Coming in Phase 1.

```bash
# future
pip install -e packages/protocol
python apps/demo/run_negotiation.py --sku WH-1000XM5 --max-cents 8000
```

## License

Apache-2.0
