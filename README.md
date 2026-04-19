# LOCAL ASI -- Distilled Artificial Superintelligence

**Alex & David Weatherspoon**
*"From Pain to Purpose. From Passion to Prophet."*

---

## What This Is

A fully local, offline, zero-cloud multi-agent AI system that runs entirely on your Mac. Five parallel researcher agents debate, critique, synthesize, and improve each other's answers through an evolutionary pipeline. A red team agent hunts hallucinations. A knowledge graph connects everything learned. No subscription. No API key. No internet required. Yours forever.

## Architecture

```
                        +------------------+
                        |   User Query     |
                        +--------+---------+
                                 |
                    +------------v------------+
                    |     Skill Router        |
                    |  (305 skills library)   |
                    +------------+------------+
                                 |
                    +------------v------------+
                    | Knowledge Base + Graph  |
                    |  (prior context search) |
                    +------------+------------+
                                 |
            +--------------------v--------------------+
            |        5 Researcher Agents (parallel)   |
            |  model: weatherspoon-asi (primary)      |
            +--------------------+--------------------+
                                 |
                    +------------v------------+
                    |     Critic Agent        |
                    |  model: qwen2.5:7b      |
                    |  (independent review)   |
                    +------------+------------+
                                 |
                    +------------v------------+
                    |   Synthesizer Agent     |
                    |  (combines best parts)  |
                    +------------+------------+
                                 |
                    +------------v------------+
                    |    Improver Agent       |
                    |  (3 refinement rounds)  |
                    +------------+------------+
                                 |
                    +------------v------------+
                    |   Red Team Agent        |
                    |  model: qwen2.5:7b      |
                    | (hallucination hunter)  |
                    +------------+------------+
                                 |
                    +------------v------------+
                    |    Scorer Agent         |
                    | (1-10 on 5 dimensions)  |
                    +------------+------------+
                                 |
                    +------------v------------+
                    | Store if score >= 6/10  |
                    | Knowledge graph indexed |
                    +-------------------------+
```

### Multi-Model Routing

Different agent roles use different models for independent perspectives:

| Role | Model | Reason |
|------|-------|--------|
| Researcher | weatherspoon-asi | Trained on the Weatherspoon corpus |
| Critic | qwen2.5:7b | Fresh perspective, no bias from training data |
| Synthesizer | weatherspoon-asi | Needs deep context to merge |
| Improver | weatherspoon-asi | Must understand standards to improve |
| Scorer | (any available) | Scoring is model-agnostic |
| Red Team | qwen2.5:7b | Adversarial review benefits from independence |

### Agent-to-Agent Protocol

Agents communicate via structured `AgentMessage` objects (not raw text), carrying:
- Confidence scores (0.0--1.0), auto-extracted from language signals
- Explicit uncertainties flagged for downstream agents
- Help requests routed to specialists
- Metadata (model used, timing, raw length)

### Knowledge Graph

Knowledge is stored not as flat JSON but as a connected graph:
- **Concepts** are extracted from every entry (entities, technical terms, domain keywords)
- **Edges** link co-occurring concepts with weighted connections
- **Search** follows graph links (1-hop) to find conceptually related entries that keyword search misses

## Components

| File | Purpose |
|------|---------|
| `asi.py` | Core engine -- swarm orchestration, knowledge base, teaching protocol, dashboard, interactive CLI |
| `mcp-server.py` | HTTP JSON-RPC server (port 8808) exposing the ASI as tools for any AI agent |
| `distill.py` | Model distillation pipeline -- extracts training data from codebases and builds a custom Ollama model |
| `curriculum.py` | Auto-curriculum system -- 5 modules, 34 lessons, 130+ questions with scoring and mastery tracking |
| `auto-improve.sh` | Nightly cron script -- re-distills model, improves weak entries, scans skill health |
| `mcp-config.json` | MCP server configuration for Claude Code integration |

## Quick Start

```bash
# 1. Start Ollama (if not running)
ollama serve &

# 2. Pull a base model (one-time)
ollama pull qwen2.5:7b

# 3. (Optional) Distill a custom model from your codebases
python3 ~/local-asi/distill.py

# 4. Run the ASI
python3 ~/local-asi/asi.py
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `[any question]` | Full multi-agent pipeline (research, critique, synthesize, improve, red team, score) |
| `/improve` | Re-process the lowest-scored knowledge entries |
| `/stats` | Knowledge base statistics |
| `/dashboard` | Full system health dashboard (scores, trends, model health, routing) |
| `/teach TOPIC` | Interactive teaching session with progressive difficulty and weakness targeting |
| `/export` | Export knowledge bundle as a shareable zip (copyleft) |
| `/import FILE` | Import a knowledge bundle from another instance |
| `/search QUERY` | Search knowledge base using keywords + graph traversal |
| `/graph` | Show knowledge graph stats and top concepts |
| `/redteam` | Run adversarial audit on the last response |
| `/agents N` | Set swarm size (1--20) |
| `/rounds N` | Set improvement rounds (1--10) |
| `/model NAME` | Switch primary model |
| `/routing` | Show the multi-model routing table |
| `/route ROLE MODEL` | Change which model a specific role uses |
| `/quit` | Exit (knowledge preserved) |

## MCP Server

The MCP server exposes the ASI as HTTP tools on port 8808:

```bash
# Start the server
python3 ~/local-asi/mcp-server.py

# Check status
curl -X POST http://localhost:8808/tool/status

# Ask a question through the full pipeline
curl -X POST http://localhost:8808/tool/ask -d '{"query": "What is XELA?"}'

# Search knowledge
curl -X POST http://localhost:8808/tool/search_knowledge -d '{"query": "branding", "top_k": 5}'
```

Available tools: `ask`, `search_knowledge`, `teach`, `improve`, `list_skills`, `get_skill`, `status`

## Auto-Curriculum

A structured teaching system with 5 modules across the full Weatherspoon domain:

1. **Aurality Studio** -- Sound fundamentals, beat making, mixing, mastering, DJing, DDJ-400, songwriting
2. **XELA Creative Branding** -- Branding theory, color/typography, logo design, packages, marketing, client management
3. **Teacher IDE** -- Eclipse Theia, InversifyJS, 23 AI packages, Ollama integration, MCP, agent system
4. **Security** -- Identity theft, business fraud, phishing, incident response, device hardening, guardian doctrine
5. **The Mission** -- Manifesto, copyleft, pain-to-purpose philosophy, ethical principles, technology diffusion

```bash
python3 ~/local-asi/curriculum.py run        # Next unmastered lesson
python3 ~/local-asi/curriculum.py status     # Mastery report
python3 ~/local-asi/curriculum.py weak       # Weakest areas
python3 ~/local-asi/curriculum.py run-all    # Full run (takes hours)
```

## Model Distillation

`distill.py` builds a custom Ollama model (`weatherspoon-asi`) by:

1. Extracting code from Teacher IDE, Aurality Studio, XELA Studio, and 280+ skills
2. Generating instruction-response pairs using qwen2.5:7b as teacher
3. Building a rich system prompt encoding the full ecosystem knowledge
4. Creating an Ollama Modelfile and building the custom model

```bash
python3 ~/local-asi/distill.py
# Then use it: ollama run weatherspoon-asi
```

## Nightly Self-Improvement

`auto-improve.sh` runs via cron and performs:

1. Re-distills the model from latest codebases (picks up new code and skills)
2. Re-processes the 3 weakest knowledge entries through the full pipeline
3. Scans skill library for broken or undersized entries
4. Logs metrics to `improvement-history.csv`

```bash
# Set up nightly cron at 2 AM
0 2 * * * bash ~/local-asi/auto-improve.sh
```

## Knowledge Persistence

Every answer scoring 6/10 or higher is stored in `~/local-asi/knowledge/` with:
- Full response text and metadata
- Concept extraction and graph indexing
- Score history in `scores.jsonl`
- Curriculum lessons in `knowledge/lessons/`

The more you use it, the smarter it gets. Knowledge compounds over time.

## Requirements

- macOS with [Ollama](https://ollama.com) installed (`brew install ollama`)
- Any 7B+ model (`ollama pull qwen2.5:7b`)
- Python 3.9+
- No internet required after initial model download
- No external Python dependencies (stdlib only)

## Techniques Applied

| # | Technique | Source | Implementation |
|---|-----------|--------|----------------|
| 1 | Multi-agent swarm | Karpathy's 30 agents | 5 parallel researchers with distinct roles |
| 2 | Self-scoring improvements | Agents evaluating each other | Scorer rates 1-10 on 5 dimensions |
| 3 | Self-replicating knowledge | Moon factory pattern | Knowledge base grows every query |
| 4 | Edge computing | "Run models on your desktop" | 100% Ollama, zero cloud |
| 5 | Technology diffusion | "All tech commoditizes" | Free, open source, copyleft |
| 6 | Compounding productivity | "Exponential curve" | Each cycle improves the next |
| 7 | Evolutionary pressure | Natural selection | Worst entries get re-processed |
| 8 | Multi-model orchestration | Right model for the right job | Role-based model routing |
| 9 | Agent-to-Agent protocol | Structured messaging | Confidence scores, uncertainties, help requests |
| 10 | Knowledge graph | Connected concepts | Graph traversal for related knowledge |
| 11 | Adversarial red team | Hallucination detection | Claim verification, factual error hunting |
| 12 | Teaching protocol | Adaptive curriculum | 5 modules, 34 lessons, mastery tracking |
| 13 | Export/share | Copyleft knowledge sharing | Zip bundles anyone can import |
| 14 | Status dashboard | System health at a glance | Scores, trends, model health, routing |

## License

Copyleft -- knowledge shared freely.

100% LOCAL. Zero cloud. Yours forever.
