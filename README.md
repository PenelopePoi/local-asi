# LOCAL ASI — Distilled Artificial Superintelligence

**Alex & David Weatherspoon**
*"From Pain to Purpose. From Passion to Prophet."*

## What This Is

A local, offline, zero-cloud multi-agent AI system that runs entirely on your Mac.
No subscription. No API key. No internet required. Yours forever.

## How It Works (Friedberg Techniques Applied)

| Technique | Source | Implementation |
|-----------|--------|----------------|
| Multi-agent swarm | Karpathy's 30 agents | 5 parallel agents with distinct roles |
| Self-scoring improvements | Agents evaluating each other | Scorer agent rates 1-10 on 5 dimensions |
| Self-replicating knowledge | Moon factory pattern | Knowledge base grows every query |
| Edge computing | "Run models on your desktop" | 100% Ollama, zero cloud |
| Technology diffusion | "All tech commoditizes" | Free, open source, copyleft |
| Compounding productivity | "Exponential curve" | Each cycle improves the next |
| Evolutionary pressure | Natural selection | Worst entries get re-processed |

## The Pipeline

```
Query → Skill Router (305 skills) → Knowledge Base Search
  → 5 Researcher Agents (parallel)
  → Critic Agent (finds flaws)
  → Synthesizer Agent (combines best)
  → Improver Agent (3 rounds)
  → Scorer Agent (1-10 rating)
  → Store if ≥ 6/10
  → Self-improvement cycle (worst get re-processed)
```

## Quick Start

```bash
# Start Ollama (if not running)
ollama serve &

# Pull a model (one-time)
ollama pull qwen2.5:7b

# Run ASI
python3 ~/local-asi/asi.py
```

## Commands

| Command | What It Does |
|---------|-------------|
| `[any question]` | Full multi-agent pipeline |
| `/improve` | Re-process lowest-scored entries |
| `/stats` | Knowledge base statistics |
| `/agents 10` | Change agent count (1-20) |
| `/rounds 5` | Change improvement rounds (1-10) |
| `/model llama3.3` | Switch model |
| `/search [query]` | Search knowledge base |
| `/quit` | Exit (knowledge preserved) |

## Agent Roles

1. **Researcher** (×5) — Deep factual investigation
2. **Critic** — Finds flaws, gaps, inaccuracies
3. **Synthesizer** — Combines best insights
4. **Improver** — Makes it strictly better (3 rounds)
5. **Scorer** — Rates on accuracy, depth, clarity, actionability, insight

## Knowledge Persistence

Every good answer (score ≥ 6) is stored in `~/local-asi/knowledge/`.
Future queries search this base first — knowledge compounds over time.
The more you use it, the smarter it gets.

## Self-Improvement

Run `/improve` or set up a cron:
```bash
# Nightly improvement at 2 AM
0 2 * * * cd ~/local-asi && echo "/improve" | python3 asi.py
```

## Requirements

- Mac with Ollama installed (`brew install ollama`)
- Any 7B+ model (`ollama pull qwen2.5:7b`)
- Python 3.9+
- No internet after initial model download
