# How it works

One loop from contract to report, the gate every candidate passes, what a worker can see and where
the code lives. The [start page](../README.md#how-it-works) has the short version.

## One loop, step by step

```mermaid
sequenceDiagram
    autonumber
    box rgba(196,67,43,0.08) You decide
        actor S as You
    end
    box rgba(89,99,110,0.08) Infrastructure
        participant C as Coordinator
        participant DB as SQLite (single writer)
    end
    box rgba(47,91,234,0.08) Workers
        participant W as Worker (Claude, OpenAI or fake)
        participant T as MCP tools
    end
    box rgba(14,124,123,0.08) Route and evidence
        participant E as Protected evaluator
    end
    S->>C: question and contract
    C->>DB: register goal, falsifier, thresholds, evaluator hash
    C->>E: run controls first
    E-->>C: controls pass, or the pilot stops here
    par each worker, up to the concurrency limit
        C->>W: public contract and limits
        W->>T: read_contract, read_findings, read_artifact
        W->>T: register_variant, write_artifact
        W->>T: submit_result (sealed outbox)
    end
    C->>C: validate, copy, hash, de-duplicate
    C->>E: evaluate the exact imported bytes
    E-->>C: verdict and raw metric outputs
    C->>DB: evidence, verdict, independent re-check
    C-->>S: report rendered from the database
```

Workers never write to the database. They write to a private outbox that the coordinator treats as
untrusted input. One coordinator per project holds the lock; SQLite stays authoritative, and reports
and the append-only JSONL export are read from it.

## The evidence gate

Every candidate passes the same gate, whatever its outcome:

```mermaid
flowchart LR
    A["Worker proposal<br/>untrusted"] --> B{"Import<br/>schema, hash, run ID"}
    B -- rejected --> X["technical_error<br/>saved, never promoted"]
    B -- accepted --> C["Protected evaluator<br/>plain code"]
    C --> V["supported, negative<br/>or inconclusive"]
    V --> D{"Independent re-check<br/>second code path"}
    D -- failed --> F["verification failed<br/>shown as such"]
    D -- checked --> R["Report entry<br/>evidence link"]
    classDef agent stroke:#2f5bea,stroke-width:2px
    classDef evidence stroke:#0e7c7b,stroke-width:2px
    classDef neutral stroke:#59636e,stroke-width:2px
    class A agent
    class C,V,D,F,R evidence
    class B,X neutral
```

Execution status, scientific outcome and verification are separate fields: a finished run is not a
finding, a negative result is checked evidence, and an interrupted worker never becomes a positive
one. Result lines in the report are tagged `measured`, `simulated`, `cited`, `assumed`,
`interpretation` or `hypothesis`, and each scored run links its evidence.

## What a worker can see

Isolation does not depend on which agent SDK runs the worker. Every backend gets the same six MCP
tools and nothing else; the tests check the effective tool list for each backend.

```mermaid
flowchart TB
    LLM(["Model provider"])
    subgraph HOST["Host: trusted side"]
        SDK["Agent loop<br/>Claude or OpenAI SDK<br/>credentials stay here"]
        C["Coordinator"]
        DB[("SQLite state<br/>JSONL export")]
        EV["Protected evaluator<br/>holdout, trusted manifest"]
    end
    subgraph BOX["Worker container"]
        MCP["MCP tool server<br/>six tools, no shell"]
        WS["workspace, read-write<br/>sealed outbox"]
        PUB["public inputs<br/>read-only"]
    end
    LLM <-->|"prompts and replies"| SDK
    C -->|"public contract"| SDK
    C --> DB
    C -->|"exact imported bytes"| EV
    SDK <-->|"MCP over stdio"| MCP
    MCP --- WS
    MCP --- PUB
    WS -.->|"validated, hashed import"| C
    classDef agent stroke:#2f5bea,stroke-width:2px
    classDef evidence stroke:#0e7c7b,stroke-width:2px
    classDef neutral stroke:#59636e,stroke-width:2px
    class SDK,MCP agent
    class EV evidence
    class LLM,C,DB,WS,PUB neutral
```

- **Never reaches a worker:** evaluator code, holdout and final data, the database, credentials,
  final scores.
- **Two sandbox modes.** `none` serves declarative tools and refuses candidate code. `container`
  runs the tools in an OCI container (Docker or Podman, pinned by digest): no network, read-only
  root, non-root user, no capabilities, limits on processes, memory, CPU and wall time.
- **Fail closed.** Four probes must pass before a container worker starts: private paths absent,
  writes outside the workspace fail, network unreachable, timeouts clean up the whole process tree.
- **Honest limits.** Containers share the host kernel: they stop mistaken or opportunistic worker
  actions, not a determined kernel exploit. See the
  [threat model](DESIGN.md#phase-3b-sandbox-policy-and-threat-model).

## Where the code lives

```text
src/research_loops/
├── coordinator.py, scheduler.py, storage.py      state, dispatch, limits, recovery
├── tools.py, transports/                         the six MCP tools, served over stdio
├── adapters/                                     fake, claude_agent, openai_agents
├── evaluation.py, evaluator_worker.py            protected evaluator subprocess
├── protection.py, authorization.py               hash anchors, run authorization
├── openai_auth.py, auth_cli.py                   Sign in with ChatGPT, protected token store
├── sandbox.py, container_stdio.py                OCI isolation and preflight probes
├── verification.py, grounding.py, reporting.py   re-checks, provenance, reports
├── compute/                                      vendor-neutral training jobs
└── migrations/                                   numbered SQLite migrations
examples/planted-signal/                          the simulated first example
experiments/grain-cnn/                            the U-Net feasibility run
skills/                                           portable agent skills, incl. rloop-coach
docs/                                             lessons, design, decisions, status
tests/                                            offline tests, incl. container isolation
```

Documentation licensed CC BY 4.0.
