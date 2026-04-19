#!/usr/bin/env python3
"""
LOCAL ASI — Distilled Artificial Superintelligence
Alex & David Weatherspoon

Techniques from Friedberg/Modern Wisdom transcript applied:
1. Multi-agent swarm (Karpathy's 30 agents pattern)
2. Self-scoring improvements (agents evaluate each other)
3. Self-replicating knowledge (moon factory pattern)
4. Edge computing (runs 100% local, zero cloud dependency)
5. Technology diffusion (democratized, free, open)
6. Compounding productivity (each cycle makes the next better)
7. Agency restoration (gives humans superpowers, not replacement)

v2 — Weatherspoon Vision Upgrade:
8. Multi-model orchestration (right model for the right job)
9. Agent-to-Agent protocol (structured messaging, confidence scores)
10. Knowledge graph (connected concepts, not flat JSON)
11. Adversarial red team (hallucination detection, claim verification)
12. Teaching protocol (/teach command, adaptive curriculum)
13. Export/share (/export — copyleft knowledge sharing)
14. Status dashboard (/dashboard — system health at a glance)

Inspired by David Weatherspoon's body of work:
- 209 repos, Smart MCP Server, AutoGem, Codepilot, Teacher IDE
- CVE-2025-8901 discovery
- "Collapses future possibilities into the present"
- "Moves the conceptual horizon forward by years"

Architecture:
- N agents running in parallel via Ollama
- Each agent has a role (researcher, critic, synthesizer, improver, scorer, red_team)
- Agents pass structured AgentMessages with confidence scores
- A scorer agent evaluates each round
- Red team agent hunts hallucinations and unsupported claims
- Best outputs survive, worst get regenerated (evolutionary pressure)
- Knowledge accumulates in a connected graph (concepts + links)
- Skills library (305 skills) acts as the domain expertise layer
- Self-improvement loop runs continuously
- Teaching protocol generates adaptive curricula
- Export packages knowledge freely (copyleft)

Runs on: Mac with Ollama + any 7B+ model
No cloud. No subscription. No API key. Yours forever.
"""

import json
import os
import subprocess
import sys
import time
import hashlib
import re
import zipfile
import shutil
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Optional

# ============================================================
# CONFIGURATION
# ============================================================

CONFIG = {
    "model": "weatherspoon-asi",           # Primary model (fallback: bonsai-8b)
    "fallback_model": "bonsai-8b",     # Fallback if primary unavailable
    "num_agents": 5,                    # Swarm size
    "rounds": 3,                        # Improvement rounds per query
    "temperature": 0.7,                 # Creativity vs precision
    "max_tokens": 2048,                 # Per-agent response limit
    "knowledge_dir": os.path.expanduser("~/local-asi/knowledge"),
    "skills_dir": os.path.expanduser("~/.claude/skills"),
    "log_dir": os.path.expanduser("~/local-asi/logs"),
    "scores_file": os.path.expanduser("~/local-asi/scores.jsonl"),
    "graph_file": os.path.expanduser("~/local-asi/knowledge/graph.json"),
    "export_dir": os.path.expanduser("~/local-asi/exports"),
    "lessons_dir": os.path.expanduser("~/local-asi/knowledge/lessons"),
}

# ============================================================
# MULTI-MODEL ROUTING — Right model for the right job
# David built Teacher IDE with 23 AI packages. Different
# models have different strengths. Use them accordingly.
# ============================================================

MODEL_ROUTING = {
    "researcher": {
        "model": "weatherspoon-asi",
        "reason": "Knows the codebase, trained on our corpus"
    },
    "critic": {
        "model": "qwen2.5:7b",
        "reason": "Fresh perspective, no bias from our training data"
    },
    "synthesizer": {
        "model": "weatherspoon-asi",
        "reason": "Needs deep context to merge perspectives"
    },
    "improver": {
        "model": "weatherspoon-asi",
        "reason": "Needs to understand our standards to improve"
    },
    "scorer": {
        "model": None,  # Uses whichever model is available
        "reason": "Scoring is model-agnostic — any model can judge quality"
    },
    "red_team": {
        "model": "qwen2.5:7b",
        "reason": "Adversarial review benefits from independent model"
    },
}

def get_model_for_role(role_name):
    """Get the best model for a given agent role."""
    route = MODEL_ROUTING.get(role_name, {})
    model = route.get("model")
    if model:
        return model
    # Scorer and unrecognized roles: try primary, fall back to whatever is available
    return CONFIG["model"]

# ============================================================
# AGENT-TO-AGENT PROTOCOL — Structured messaging
# Inspired by David's Smart MCP Server (Agent-to-Agent protocol)
# Agents don't just pass raw text. They pass structured context
# with confidence scores, uncertainties, and help requests.
# ============================================================

@dataclass
class AgentMessage:
    """
    Structured message for agent-to-agent communication.
    Inspired by David Weatherspoon's Smart MCP Server protocol.

    Every agent output includes:
    - sender: which agent produced this
    - receiver: who it's intended for (or 'broadcast')
    - content: the actual response text
    - confidence: 0.0-1.0 self-assessed confidence
    - uncertainties: list of things the agent isn't sure about
    - requests: list of specific help needed from other agents
    - metadata: timing, model used, etc.
    """
    sender: str
    receiver: str = "broadcast"
    content: str = ""
    confidence: float = 0.5
    uncertainties: list = field(default_factory=list)
    requests: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def to_context_string(self):
        """Format this message as context for another agent."""
        parts = [f"[From: {self.sender} | Confidence: {self.confidence:.0%}]"]
        parts.append(self.content)
        if self.uncertainties:
            parts.append(f"[Uncertainties: {'; '.join(self.uncertainties)}]")
        if self.requests:
            parts.append(f"[Help needed: {'; '.join(self.requests)}]")
        return "\n".join(parts)

    def summary(self):
        """One-line summary for logging."""
        return (
            f"{self.sender}->{self.receiver} "
            f"conf={self.confidence:.0%} "
            f"unc={len(self.uncertainties)} "
            f"req={len(self.requests)} "
            f"len={len(self.content)}"
        )


def parse_agent_output(raw_text, sender_role):
    """
    Parse raw model output into a structured AgentMessage.
    Extracts confidence, uncertainties, and help requests from the text.
    """
    msg = AgentMessage(sender=sender_role)
    msg.content = raw_text

    # Extract confidence signals from text
    confidence_signals = []
    low_conf_patterns = [
        r"i'm not sure", r"i am not sure", r"uncertain", r"unclear",
        r"i don't know", r"i do not know", r"possibly", r"might be",
        r"i think", r"it seems", r"arguably", r"debatable",
    ]
    high_conf_patterns = [
        r"certainly", r"definitely", r"clearly", r"without doubt",
        r"it is", r"the answer is", r"factually", r"confirmed",
    ]
    text_lower = raw_text.lower()
    for p in low_conf_patterns:
        if re.search(p, text_lower):
            confidence_signals.append(-0.1)
    for p in high_conf_patterns:
        if re.search(p, text_lower):
            confidence_signals.append(0.1)

    base_confidence = 0.6
    adjustment = sum(confidence_signals)
    msg.confidence = max(0.1, min(0.95, base_confidence + adjustment))

    # Extract explicit uncertainty markers
    for line in raw_text.split("\n"):
        line_lower = line.lower().strip()
        if any(marker in line_lower for marker in ["i'm not sure", "uncertain", "unclear", "unknown"]):
            if len(line.strip()) < 200:
                msg.uncertainties.append(line.strip())
        if any(marker in line_lower for marker in ["need more", "requires", "would need", "help with"]):
            if len(line.strip()) < 200:
                msg.requests.append(line.strip())

    msg.metadata = {
        "model": get_model_for_role(sender_role),
        "timestamp": datetime.now().isoformat(),
        "raw_length": len(raw_text),
    }

    return msg


# ============================================================
# AGENT ROLES — Each agent has a unique perspective
# ============================================================

AGENT_ROLES = {
    "researcher": {
        "system": (
            "You are a deep researcher. Given a question or task, provide the most "
            "thorough, evidence-based, factually accurate response possible. "
            "Cite specific numbers, dates, names, and mechanisms. "
            "If you're uncertain, say so explicitly — prefix uncertain claims with "
            "'I'm not sure but...' so downstream agents can flag them. Never fabricate."
        ),
        "purpose": "factual depth"
    },
    "critic": {
        "system": (
            "You are a ruthless critic. Your job is to find flaws, gaps, "
            "inaccuracies, logical fallacies, and missing perspectives in any "
            "response. Be specific about what's wrong and why. "
            "Suggest concrete fixes for every flaw you identify. "
            "Pay special attention to confidence levels — if a prior agent "
            "flagged uncertainty, investigate that area harder."
        ),
        "purpose": "error detection"
    },
    "synthesizer": {
        "system": (
            "You are a master synthesizer. Given multiple perspectives and "
            "critiques, combine them into a single coherent response that "
            "preserves the best insights from each while resolving contradictions. "
            "The output should be clearer and more useful than any individual input. "
            "When agents disagree, explain why you chose one perspective over another."
        ),
        "purpose": "integration"
    },
    "improver": {
        "system": (
            "You are an improvement engine. Given a response and its critique, "
            "produce a strictly better version. Every change must be an objective "
            "improvement: more accurate, more specific, more actionable, clearer. "
            "Never make a change that reduces quality. "
            "Address every uncertainty and help request from prior agents."
        ),
        "purpose": "quality uplift"
    },
    "scorer": {
        "system": (
            "You are a quality scorer. Rate responses on a scale of 1-10 across "
            "five dimensions: Accuracy (factual correctness), Depth (thoroughness), "
            "Clarity (ease of understanding), Actionability (practical usefulness), "
            "Insight (novel or non-obvious perspectives). "
            "Return ONLY a JSON object: {\"accuracy\": N, \"depth\": N, \"clarity\": N, "
            "\"actionability\": N, \"insight\": N, \"total\": N, \"reasoning\": \"...\"}"
        ),
        "purpose": "evaluation"
    },
    "red_team": {
        "system": (
            "You are an adversarial red team agent. Your mission is to find:\n"
            "1. HALLUCINATIONS — claims that sound plausible but are fabricated\n"
            "2. UNSUPPORTED CLAIMS — assertions not backed by the provided context\n"
            "3. LOGICAL FALLACIES — ad hominem, straw man, false dichotomy, etc.\n"
            "4. FACTUAL ERRORS — wrong dates, numbers, names, mechanisms\n"
            "5. OVERCONFIDENCE — claims stated as certain that should be hedged\n\n"
            "For EACH issue found, output a JSON line:\n"
            "{\"type\": \"hallucination|unsupported|fallacy|factual_error|overconfidence\", "
            "\"claim\": \"the problematic claim\", \"reason\": \"why it's wrong\", "
            "\"severity\": 1-10}\n\n"
            "End with a summary line:\n"
            "{\"hallucination_risk\": 1-10, \"total_issues\": N, \"verdict\": \"pass|flag|fail\"}\n\n"
            "Be thorough. Be adversarial. Break the answer."
        ),
        "purpose": "adversarial verification"
    },
}

# ============================================================
# OLLAMA INTERFACE
# ============================================================

# Track model health metrics for the dashboard
_model_metrics = defaultdict(lambda: {"calls": 0, "errors": 0, "total_time": 0.0})

def ollama_generate(prompt, system="", model=None, temperature=None):
    """Call Ollama locally via HTTP API. Zero cloud dependency."""
    import urllib.request
    model = model or CONFIG["model"]
    temp = temperature or CONFIG["temperature"]
    start = time.time()

    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "options": {"temperature": temp, "num_predict": CONFIG["max_tokens"]}
    }).encode()

    try:
        req = urllib.request.Request(
            "http://localhost:11434/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode())
            elapsed = time.time() - start
            _model_metrics[model]["calls"] += 1
            _model_metrics[model]["total_time"] += elapsed
            return data.get("response", "").strip()
    except Exception as e:
        elapsed = time.time() - start
        _model_metrics[model]["calls"] += 1
        _model_metrics[model]["errors"] += 1
        _model_metrics[model]["total_time"] += elapsed
        # Try fallback model
        if model != CONFIG["fallback_model"]:
            return ollama_generate(prompt, system, CONFIG["fallback_model"], temp)
        return f"[ERROR] {str(e)}"


def ollama_available():
    """Check if Ollama is running."""
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except:
        return False

# ============================================================
# KNOWLEDGE GRAPH — Connected concepts, not flat JSON
# David's 209 repos are interconnected. Knowledge should be too.
# ============================================================

class KnowledgeGraph:
    """
    Upgrade from flat JSON to a connected knowledge graph.
    Every entry gets concept extraction. Related entries link by shared concepts.
    Search follows links to find related knowledge (not just keyword match).
    """

    def __init__(self):
        self.graph_file = Path(CONFIG["graph_file"])
        self.graph = self._load_graph()

    def _load_graph(self):
        if self.graph_file.exists():
            try:
                return json.loads(self.graph_file.read_text())
            except:
                pass
        return {
            "nodes": {},       # concept_id -> {label, type, mentions: [entry_ids]}
            "edges": [],       # [{source, target, weight, type}]
            "entry_concepts": {}  # entry_id -> [concept_ids]
        }

    def _save_graph(self):
        self.graph_file.parent.mkdir(parents=True, exist_ok=True)
        self.graph_file.write_text(json.dumps(self.graph, indent=2))

    def extract_concepts(self, text):
        """
        Extract key concepts/entities from text.
        Uses pattern matching — no external dependencies needed.
        """
        concepts = set()

        # Extract capitalized phrases (likely proper nouns / entities)
        for match in re.finditer(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', text):
            phrase = match.group(1)
            if len(phrase) > 2 and phrase not in {"The", "This", "That", "They", "What", "When", "Where", "How", "Why"}:
                concepts.add(phrase.lower())

        # Extract technical terms (CamelCase, snake_case, hyphenated)
        for match in re.finditer(r'\b([a-z]+[-_][a-z]+[-_]?[a-z]*)\b', text):
            concepts.add(match.group(1))
        for match in re.finditer(r'\b([A-Z][a-z]+[A-Z][a-zA-Z]*)\b', text):
            concepts.add(match.group(1).lower())

        # Extract quoted terms
        for match in re.finditer(r'"([^"]{2,40})"', text):
            concepts.add(match.group(1).lower())

        # Extract domain keywords
        domain_keywords = [
            "ai", "model", "agent", "swarm", "knowledge", "security", "branding",
            "music", "audio", "react", "typescript", "python", "ollama", "mcp",
            "teacher", "skill", "api", "database", "firebase", "vercel",
            "production", "mixing", "mastering", "llm", "training", "distill",
        ]
        text_lower = text.lower()
        for kw in domain_keywords:
            if kw in text_lower:
                concepts.add(kw)

        return list(concepts)[:30]  # Cap at 30 concepts per entry

    def add_entry(self, entry_id, text, score=0):
        """Add an entry to the graph with concept extraction and linking."""
        concepts = self.extract_concepts(text)
        concept_ids = []

        for concept in concepts:
            concept_id = hashlib.md5(concept.encode()).hexdigest()[:8]
            concept_ids.append(concept_id)

            if concept_id not in self.graph["nodes"]:
                self.graph["nodes"][concept_id] = {
                    "label": concept,
                    "type": "concept",
                    "mentions": []
                }
            if entry_id not in self.graph["nodes"][concept_id]["mentions"]:
                self.graph["nodes"][concept_id]["mentions"].append(entry_id)

        self.graph["entry_concepts"][entry_id] = concept_ids

        # Create edges between co-occurring concepts
        for i, c1 in enumerate(concept_ids):
            for c2 in concept_ids[i+1:]:
                existing = None
                for edge in self.graph["edges"]:
                    if (edge["source"] == c1 and edge["target"] == c2) or \
                       (edge["source"] == c2 and edge["target"] == c1):
                        existing = edge
                        break
                if existing:
                    existing["weight"] += 1
                else:
                    self.graph["edges"].append({
                        "source": c1,
                        "target": c2,
                        "weight": 1,
                        "type": "co-occurrence"
                    })

        self._save_graph()
        return concepts

    def find_related_entries(self, query, top_k=5):
        """
        Find related knowledge entries by following concept links.
        Not just keyword match — follows the graph to find connected knowledge.
        """
        query_concepts = self.extract_concepts(query)
        query_concept_ids = set()
        for concept in query_concepts:
            concept_id = hashlib.md5(concept.encode()).hexdigest()[:8]
            if concept_id in self.graph["nodes"]:
                query_concept_ids.add(concept_id)

        # Score entries by concept overlap (direct match)
        entry_scores = defaultdict(float)
        for cid in query_concept_ids:
            node = self.graph["nodes"].get(cid, {})
            for entry_id in node.get("mentions", []):
                entry_scores[entry_id] += 2.0  # Direct concept match

        # Follow edges to find related concepts (1-hop)
        related_concept_ids = set()
        for cid in query_concept_ids:
            for edge in self.graph["edges"]:
                if edge["source"] == cid:
                    related_concept_ids.add(edge["target"])
                elif edge["target"] == cid:
                    related_concept_ids.add(edge["source"])

        # Score entries reachable via 1-hop
        for cid in related_concept_ids - query_concept_ids:
            node = self.graph["nodes"].get(cid, {})
            for entry_id in node.get("mentions", []):
                entry_scores[entry_id] += 0.5  # 1-hop related

        # Sort by score
        ranked = sorted(entry_scores.items(), key=lambda x: x[1], reverse=True)
        return [eid for eid, _ in ranked[:top_k]]

    def stats(self):
        return {
            "concepts": len(self.graph["nodes"]),
            "edges": len(self.graph["edges"]),
            "entries_mapped": len(self.graph["entry_concepts"]),
        }


# ============================================================
# KNOWLEDGE BASE — Self-replicating local knowledge
# ============================================================

class KnowledgeBase:
    """
    Local knowledge accumulator. Every good answer gets stored.
    Moon factory pattern: knowledge builds on itself.
    Now backed by a knowledge graph for connected retrieval.
    """

    def __init__(self):
        self.dir = Path(CONFIG["knowledge_dir"])
        self.dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.dir / "index.json"
        self.index = self._load_index()
        self.graph = KnowledgeGraph()

    def _load_index(self):
        if self.index_file.exists():
            return json.loads(self.index_file.read_text())
        return {"entries": [], "total_queries": 0, "avg_score": 0}

    def _save_index(self):
        self.index_file.write_text(json.dumps(self.index, indent=2))

    def store(self, query, response, score, metadata=None):
        """Store a high-quality response for future reference."""
        entry_id = hashlib.md5(f"{query}{time.time()}".encode()).hexdigest()[:12]
        entry = {
            "id": entry_id,
            "query": query,
            "response": response[:5000],  # Truncate to save space
            "score": score,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }

        # Save entry
        entry_file = self.dir / f"{entry_id}.json"
        entry_file.write_text(json.dumps(entry, indent=2))

        # Update index
        self.index["entries"].append({
            "id": entry_id,
            "query": query[:200],
            "score": score,
            "timestamp": entry["timestamp"]
        })
        self.index["total_queries"] += 1

        scores = [e["score"] for e in self.index["entries"]]
        self.index["avg_score"] = sum(scores) / len(scores) if scores else 0
        self._save_index()

        # Add to knowledge graph
        concepts = self.graph.add_entry(entry_id, f"{query} {response[:2000]}", score)
        if concepts:
            entry["metadata"]["concepts"] = concepts[:10]
            entry_file.write_text(json.dumps(entry, indent=2))

        return entry_id

    def search(self, query, top_k=3):
        """
        Search using both keyword matching AND knowledge graph traversal.
        Graph search finds conceptually related entries that keyword search misses.
        """
        # Keyword search (original)
        query_words = set(query.lower().split())
        keyword_scored = []
        for entry in self.index["entries"]:
            entry_words = set(entry["query"].lower().split())
            overlap = len(query_words & entry_words)
            if overlap > 0:
                keyword_scored.append((overlap, entry["id"]))

        keyword_scored.sort(reverse=True, key=lambda x: x[0])
        keyword_ids = [eid for _, eid in keyword_scored[:top_k]]

        # Graph search (new)
        graph_ids = self.graph.find_related_entries(query, top_k=top_k)

        # Merge results (keyword matches first, then graph discoveries)
        seen = set()
        merged_ids = []
        for eid in keyword_ids + graph_ids:
            if eid not in seen:
                seen.add(eid)
                merged_ids.append(eid)

        # Load and return entries
        results = []
        for eid in merged_ids[:top_k]:
            entry_file = self.dir / f"{eid}.json"
            if entry_file.exists():
                results.append(json.loads(entry_file.read_text()))
        return results

    def get_all_entries(self):
        """Load all knowledge entries."""
        entries = []
        for entry_meta in self.index["entries"]:
            entry_file = self.dir / f"{entry_meta['id']}.json"
            if entry_file.exists():
                entries.append(json.loads(entry_file.read_text()))
        return entries

    def stats(self):
        graph_stats = self.graph.stats()
        return {
            "total_entries": len(self.index["entries"]),
            "total_queries": self.index["total_queries"],
            "avg_score": round(self.index["avg_score"], 2),
            "graph_concepts": graph_stats["concepts"],
            "graph_edges": graph_stats["edges"],
        }

# ============================================================
# SKILL ROUTER — Tap into 305 skills for domain expertise
# ============================================================

class SkillRouter:
    """Route queries to relevant skills from the 305-skill library."""

    def __init__(self):
        self.categories_file = Path(CONFIG["skills_dir"]) / "smart-tool-selector" / "categories.json"
        self.categories = self._load_categories()

    def _load_categories(self):
        if self.categories_file.exists():
            return json.loads(self.categories_file.read_text())
        return {}

    def find_relevant_skills(self, query, max_skills=3):
        """Find skills relevant to the query using keyword matching."""
        query_lower = query.lower()
        matches = []

        for category, data in self.categories.items():
            keywords = data.get("keywords", [])
            skill_names = data.get("skills", [])
            score = sum(1 for kw in keywords if kw.lower() in query_lower)
            if score > 0:
                matches.append((score, category, skill_names))

        matches.sort(reverse=True, key=lambda x: x[0])

        # Collect top skills
        skills = []
        for _, category, skill_names in matches[:2]:
            for s in skill_names[:max_skills]:
                if len(skills) < max_skills:
                    skills.append(s)
        return skills

    def get_skill_context(self, skill_name):
        """Load a skill's content for context injection."""
        skill_file = Path(CONFIG["skills_dir"]) / skill_name / "SKILL.md"
        if skill_file.exists():
            content = skill_file.read_text()
            # Strip frontmatter, return body only
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    return parts[2].strip()[:2000]
            return content[:2000]
        return ""

# ============================================================
# RED TEAM AGENT — Adversarial hallucination hunter
# Goes beyond the critic. Actively tries to break the answer.
# ============================================================

class RedTeamAgent:
    """
    Adversarial agent that hunts hallucinations, unsupported claims,
    logical fallacies, and overconfidence. Scores hallucination risk 1-10.

    Checks factual claims against the stored knowledge corpus.
    Flags anything not supported by evidence.
    """

    def __init__(self, kb):
        self.kb = kb

    def audit(self, query, response, agent_messages=None):
        """
        Run adversarial audit on a response.
        Returns: dict with issues, hallucination_risk, verdict
        """
        # Build context from knowledge base for fact-checking
        prior_knowledge = self.kb.search(query, top_k=5)
        corpus_context = ""
        if prior_knowledge:
            corpus_context = "Known facts from the knowledge base:\n"
            for p in prior_knowledge:
                corpus_context += f"- {p['query']}: {p['response'][:300]}\n"

        # Build context from agent messages
        agent_context = ""
        if agent_messages:
            uncertainties = []
            for msg in agent_messages:
                if isinstance(msg, AgentMessage) and msg.uncertainties:
                    uncertainties.extend(msg.uncertainties)
            if uncertainties:
                agent_context = (
                    "\nPrior agents flagged these uncertainties:\n"
                    + "\n".join(f"- {u}" for u in uncertainties[:10])
                )

        prompt = (
            f"QUERY: {query}\n\n"
            f"RESPONSE TO AUDIT:\n{response}\n\n"
            f"{corpus_context}\n"
            f"{agent_context}\n\n"
            "Perform your adversarial audit. Find every issue. "
            "Output JSON lines for each issue, then a summary line."
        )

        model = get_model_for_role("red_team")
        raw = ollama_generate(
            prompt,
            system=AGENT_ROLES["red_team"]["system"],
            model=model,
            temperature=0.3  # Low temperature for precise analysis
        )

        return self._parse_audit(raw)

    def _parse_audit(self, raw_output):
        """Parse the red team output into structured findings."""
        issues = []
        summary = {"hallucination_risk": 5, "total_issues": 0, "verdict": "flag"}

        for line in raw_output.split("\n"):
            line = line.strip()
            if not line:
                continue
            # Try to parse JSON objects from the output
            try:
                start = line.find("{")
                end = line.rfind("}") + 1
                if start >= 0 and end > start:
                    obj = json.loads(line[start:end])
                    if "hallucination_risk" in obj:
                        summary = obj
                    elif "type" in obj and "claim" in obj:
                        issues.append(obj)
            except json.JSONDecodeError:
                continue

        summary["total_issues"] = len(issues)
        if not issues:
            summary["hallucination_risk"] = 2
            summary["verdict"] = "pass"
        elif len(issues) >= 5:
            summary["hallucination_risk"] = min(10, summary.get("hallucination_risk", 5) + 2)
            summary["verdict"] = "fail"

        return {
            "issues": issues,
            "summary": summary,
            "raw": raw_output,
        }


# ============================================================
# ASI SWARM — Multi-agent orchestration
# ============================================================

class ASISwarm:
    """
    The core ASI engine. Runs N agents in parallel,
    has them critique and improve each other's work,
    scores the results, and keeps only the best.

    v2: Multi-model routing, Agent-to-Agent protocol,
    knowledge graph search, red team adversarial audit.
    """

    def __init__(self):
        self.kb = KnowledgeBase()
        self.router = SkillRouter()
        self.red_team = RedTeamAgent(self.kb)
        self.log_dir = Path(CONFIG["log_dir"])
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def _run_agent(self, role_name, prompt, extra_context=""):
        """Run a single agent with its role, using the right model."""
        role = AGENT_ROLES[role_name]
        system = role["system"]
        if extra_context:
            system += f"\n\nAdditional context:\n{extra_context}"
        model = get_model_for_role(role_name)
        raw = ollama_generate(prompt, system=system, model=model)
        # Parse into structured AgentMessage
        msg = parse_agent_output(raw, role_name)
        msg.metadata["model"] = model
        return msg

    def _score_response(self, query, response):
        """Have the scorer agent evaluate a response."""
        prompt = (
            f"Query: {query}\n\n"
            f"Response to score:\n{response}\n\n"
            "Score this response. Return ONLY valid JSON."
        )
        msg = self._run_agent("scorer", prompt)
        raw = msg.content

        # Parse score
        try:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(raw[start:end])
                total = data.get("total", 5)
                if isinstance(total, (int, float)):
                    if total > 10:
                        dims = [data.get(k, 5) for k in ["accuracy","depth","clarity","actionability","insight"]]
                        valid = [d for d in dims if isinstance(d, (int, float)) and 1 <= d <= 10]
                        total = sum(valid) / len(valid) if valid else 5
                    return min(10, max(1, round(total, 1)))
        except:
            pass
        return 5  # Default score

    def process(self, query):
        """
        Full ASI pipeline:
        1. Route to relevant skills
        2. Search knowledge base + graph for prior context
        3. Run parallel researcher agents (multi-model)
        4. Critic evaluates all responses (independent model)
        5. Synthesizer combines the best
        6. Improver refines the synthesis
        7. Red team adversarial audit
        8. Scorer evaluates final output
        9. Store if above threshold (with graph indexing)
        """
        start_time = time.time()
        agent_messages = []  # Collect all agent messages for protocol

        print(f"\n{'='*60}")
        print(f"  LOCAL ASI v2 — Processing Query")
        print(f"  Primary: {CONFIG['model']} | Critic: {MODEL_ROUTING['critic']['model']}")
        print(f"  Agents: {CONFIG['num_agents']} | Rounds: {CONFIG['rounds']}")
        print(f"{'='*60}\n")

        # Step 1: Find relevant skills
        skills = self.router.find_relevant_skills(query)
        skill_context = ""
        if skills:
            print(f"  Skills matched: {', '.join(skills)}")
            for s in skills[:2]:
                ctx = self.router.get_skill_context(s)
                if ctx:
                    skill_context += f"\n[Skill: {s}]\n{ctx[:800]}\n"

        # Step 2: Search knowledge base + graph
        prior = self.kb.search(query)
        prior_context = ""
        if prior:
            print(f"  Prior knowledge: {len(prior)} entries found (keyword + graph)")
            for p in prior[:2]:
                prior_context += f"\n[Prior answer, score={p['score']}]\n{p['response'][:500]}\n"

        # Step 3: Parallel research phase (multi-model)
        print(f"\n  Phase 1: Research ({CONFIG['num_agents']} agents, model={MODEL_ROUTING['researcher']['model']})...")
        research_prompt = f"Question: {query}"
        if skill_context:
            research_prompt += f"\n\nDomain expertise:\n{skill_context}"
        if prior_context:
            research_prompt += f"\n\nPrior knowledge:\n{prior_context}"

        responses = []
        with ThreadPoolExecutor(max_workers=CONFIG["num_agents"]) as executor:
            futures = []
            for i in range(CONFIG["num_agents"]):
                f = executor.submit(self._run_agent, "researcher", research_prompt)
                futures.append(f)
            for f in as_completed(futures):
                msg = f.result()
                if not msg.content.startswith("[ERROR]"):
                    responses.append(msg)
                    agent_messages.append(msg)
                    print(f"    Agent: {msg.summary()}")

        if not responses:
            return "All agents failed. Check if Ollama is running: `ollama serve`"

        # Step 4: Critique phase (independent model for fresh perspective)
        print(f"\n  Phase 2: Critique (model={MODEL_ROUTING['critic']['model']})...")
        all_context = "\n---\n".join(msg.to_context_string() for msg in responses[:3])
        critique_msg = self._run_agent("critic",
            f"Original question: {query}\n\n"
            f"Responses to critique:\n{all_context}"
        )
        agent_messages.append(critique_msg)
        print(f"    Critic: {critique_msg.summary()}")

        # Step 5: Synthesis phase
        print(f"\n  Phase 3: Synthesize...")
        synthesis_msg = self._run_agent("synthesizer",
            f"Original question: {query}\n\n"
            f"Multiple research responses:\n{all_context}\n\n"
            f"Critique of these responses:\n{critique_msg.to_context_string()}"
        )
        agent_messages.append(synthesis_msg)
        print(f"    Synthesizer: {synthesis_msg.summary()}")

        # Step 6: Improvement rounds
        current_msg = synthesis_msg
        for r in range(CONFIG["rounds"]):
            print(f"\n  Phase 4: Improve (round {r+1}/{CONFIG['rounds']})...")
            current_msg = self._run_agent("improver",
                f"Original question: {query}\n\n"
                f"Current best answer:\n{current_msg.to_context_string()}\n\n"
                f"Critique to address:\n{critique_msg.to_context_string()}\n\n"
                "Produce a strictly better version."
            )
            agent_messages.append(current_msg)
            print(f"    Improver: {current_msg.summary()}")

        current = current_msg.content

        # Step 7: Red team adversarial audit
        print(f"\n  Phase 5: Red Team Audit (model={MODEL_ROUTING['red_team']['model']})...")
        audit = self.red_team.audit(query, current, agent_messages)
        audit_summary = audit["summary"]
        print(f"    Hallucination risk: {audit_summary.get('hallucination_risk', '?')}/10")
        print(f"    Issues found: {audit_summary.get('total_issues', 0)}")
        print(f"    Verdict: {audit_summary.get('verdict', '?')}")

        # If red team flags serious issues, run another improvement round
        if audit_summary.get("verdict") == "fail" and audit["issues"]:
            print(f"\n  Phase 5b: Addressing red team findings...")
            issue_text = "\n".join(
                f"- [{iss.get('type','?')}] {iss.get('claim','?')}: {iss.get('reason','?')}"
                for iss in audit["issues"][:5]
            )
            current_msg = self._run_agent("improver",
                f"Original question: {query}\n\n"
                f"Current answer:\n{current}\n\n"
                f"RED TEAM FINDINGS (must fix):\n{issue_text}\n\n"
                "Fix every red team issue. Remove or hedge unsupported claims. "
                "Correct factual errors. Produce a safer, more accurate version."
            )
            current = current_msg.content
            print(f"    Post-audit improvement: {len(current)} chars")

        # Step 8: Final scoring
        print(f"\n  Phase 6: Score...")
        score = self._score_response(query, current)
        print(f"    Final score: {score}/10")

        # Step 9: Store if good (with graph indexing)
        elapsed = time.time() - start_time
        if score >= 6:
            entry_id = self.kb.store(query, current, score, {
                "skills": skills,
                "elapsed": round(elapsed, 1),
                "agents": CONFIG["num_agents"],
                "rounds": CONFIG["rounds"],
                "hallucination_risk": audit_summary.get("hallucination_risk", 0),
                "red_team_verdict": audit_summary.get("verdict", "unknown"),
                "models_used": list(set(
                    msg.metadata.get("model", "unknown") for msg in agent_messages
                )),
            })
            print(f"    Stored in knowledge base: {entry_id}")

        # Log
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "score": score,
            "elapsed": round(elapsed, 1),
            "skills": skills,
            "response_length": len(current),
            "hallucination_risk": audit_summary.get("hallucination_risk", 0),
            "red_team_verdict": audit_summary.get("verdict", "unknown"),
            "agent_count": len(agent_messages),
            "avg_confidence": round(
                sum(m.confidence for m in agent_messages) / len(agent_messages), 2
            ) if agent_messages else 0,
        }
        scores_file = Path(CONFIG["scores_file"])
        with open(scores_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

        print(f"\n{'='*60}")
        print(f"  Completed in {elapsed:.1f}s | Score: {score}/10")
        print(f"  Knowledge base: {self.kb.stats()}")
        print(f"{'='*60}\n")

        return current

# ============================================================
# CONTINUOUS IMPROVEMENT LOOP
# ============================================================

class SelfImprover:
    """
    Friedberg pattern: agents score improvements to themselves.
    Karpathy pattern: 30 agents talking to each other making better LLMs.

    This runs continuously, taking the worst-scored entries in the
    knowledge base and re-processing them with the latest model.
    """

    def __init__(self, swarm):
        self.swarm = swarm

    def improve_worst(self, n=3):
        """Re-process the N lowest-scored entries."""
        entries = sorted(
            self.swarm.kb.index["entries"],
            key=lambda x: x["score"]
        )[:n]

        print(f"\n  Self-Improvement: Re-processing {len(entries)} low-score entries...")
        for entry in entries:
            print(f"\n    Re-processing: {entry['query'][:60]}... (score: {entry['score']})")
            new_response = self.swarm.process(entry["query"])
            # The process method already stores if score >= 6

    def run_cycle(self):
        """Run one full improvement cycle."""
        stats = self.swarm.kb.stats()
        print(f"\n{'='*60}")
        print(f"  SELF-IMPROVEMENT CYCLE")
        print(f"  Knowledge base: {stats['total_entries']} entries, avg score: {stats['avg_score']}")
        print(f"{'='*60}")

        if stats["total_entries"] >= 3:
            self.improve_worst(3)
        else:
            print("  Not enough entries yet. Process more queries first.")

# ============================================================
# TEACHING PROTOCOL — /teach command
# Inspired by David's Teacher IDE with 23 AI packages.
# Structured curriculum that adapts to the learner.
# ============================================================

class TeachingProtocol:
    """
    Structured teaching curriculum that:
    1. Takes a topic, generates 5 progressively harder questions
    2. Scores each answer
    3. Identifies weak areas
    4. Generates follow-up questions targeting weaknesses
    5. Logs the session as a 'lesson' in the knowledge base
    """

    def __init__(self, swarm):
        self.swarm = swarm
        self.lessons_dir = Path(CONFIG["lessons_dir"])
        self.lessons_dir.mkdir(parents=True, exist_ok=True)

    def _generate_questions(self, topic, difficulty_start=1, count=5, weak_areas=None):
        """Generate progressively harder questions on a topic."""
        weakness_note = ""
        if weak_areas:
            weakness_note = (
                f"\nThe learner is weak in these areas — focus questions there:\n"
                + "\n".join(f"- {w}" for w in weak_areas)
            )

        prompt = (
            f"Generate {count} questions about '{topic}' with progressive difficulty.\n"
            f"Start at difficulty level {difficulty_start}/10 and increase.\n"
            f"{weakness_note}\n\n"
            "Format each as:\n"
            "Q1 [difficulty: N/10]: question text\n"
            "EXPECTED: brief expected answer\n\n"
            "Make questions specific, practical, and testable."
        )

        raw = ollama_generate(prompt, system=(
            "You are a master teacher designing a curriculum. "
            "Create questions that build understanding progressively. "
            "Each question should be harder than the last. "
            "Include expected answers so responses can be scored."
        ))

        # Parse questions
        questions = []
        current_q = None
        for line in raw.split("\n"):
            line = line.strip()
            if re.match(r'Q\d+', line):
                if current_q:
                    questions.append(current_q)
                diff_match = re.search(r'difficulty:\s*(\d+)', line)
                diff = int(diff_match.group(1)) if diff_match else difficulty_start
                q_text = re.sub(r'Q\d+\s*\[.*?\]:\s*', '', line).strip()
                current_q = {"question": q_text, "difficulty": diff, "expected": ""}
            elif line.upper().startswith("EXPECTED:") and current_q:
                current_q["expected"] = line.split(":", 1)[1].strip()
        if current_q:
            questions.append(current_q)

        return questions[:count]

    def _score_answer(self, question, expected, user_answer):
        """Score a user's answer against expected answer."""
        prompt = (
            f"Question: {question}\n"
            f"Expected answer: {expected}\n"
            f"Student's answer: {user_answer}\n\n"
            "Score the student's answer from 1-10 on:\n"
            "- Correctness (does it match the expected answer?)\n"
            "- Completeness (does it cover all key points?)\n"
            "- Understanding (does the student show real comprehension?)\n\n"
            "Return ONLY a JSON object:\n"
            "{\"correctness\": N, \"completeness\": N, \"understanding\": N, "
            "\"total\": N, \"weak_area\": \"specific area to improve\", "
            "\"feedback\": \"specific feedback\"}"
        )
        raw = ollama_generate(prompt, system="You are a fair, encouraging teacher who gives specific feedback.")

        try:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(raw[start:end])
        except:
            pass
        return {"correctness": 5, "completeness": 5, "understanding": 5, "total": 5,
                "weak_area": "unknown", "feedback": "Could not parse score."}

    def run_lesson(self, topic):
        """Run a full teaching session on a topic."""
        print(f"\n{'='*60}")
        print(f"  TEACHING PROTOCOL — {topic}")
        print(f"  5 questions, progressive difficulty")
        print(f"  Type your answers or 'skip' to skip, 'quit' to end")
        print(f"{'='*60}\n")

        lesson = {
            "topic": topic,
            "timestamp": datetime.now().isoformat(),
            "questions": [],
            "scores": [],
            "weak_areas": [],
        }

        # Round 1: Initial 5 questions
        questions = self._generate_questions(topic)
        if not questions:
            print("  Failed to generate questions. Try again.")
            return

        for i, q in enumerate(questions):
            print(f"\n  Q{i+1} [Difficulty: {q['difficulty']}/10]:")
            print(f"  {q['question']}\n")

            try:
                answer = input("  Your answer > ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\n  Lesson ended early.")
                break

            if answer.lower() == "quit":
                break
            if answer.lower() == "skip":
                lesson["questions"].append({**q, "answer": "[skipped]", "score": 0})
                lesson["scores"].append(0)
                continue

            # Score the answer
            result = self._score_answer(q["question"], q["expected"], answer)
            total = result.get("total", 5)
            if isinstance(total, (int, float)) and total > 10:
                total = total / 3  # Normalize if summed

            lesson["questions"].append({
                **q,
                "answer": answer,
                "score": total,
                "feedback": result.get("feedback", ""),
            })
            lesson["scores"].append(total)

            print(f"\n  Score: {total}/10")
            print(f"  Feedback: {result.get('feedback', 'N/A')}")

            weak = result.get("weak_area", "")
            if weak and weak != "unknown" and total < 7:
                lesson["weak_areas"].append(weak)
                print(f"  Weak area identified: {weak}")

        # Round 2: Follow-up questions targeting weaknesses
        if lesson["weak_areas"]:
            print(f"\n{'='*60}")
            print(f"  FOLLOW-UP ROUND — Targeting weaknesses")
            print(f"  Weak areas: {', '.join(lesson['weak_areas'][:3])}")
            print(f"{'='*60}\n")

            follow_ups = self._generate_questions(
                topic, difficulty_start=3, count=3,
                weak_areas=lesson["weak_areas"][:3]
            )

            for i, q in enumerate(follow_ups):
                print(f"\n  Follow-up {i+1} [Difficulty: {q['difficulty']}/10]:")
                print(f"  {q['question']}\n")

                try:
                    answer = input("  Your answer > ").strip()
                except (KeyboardInterrupt, EOFError):
                    break

                if answer.lower() in ("quit", "skip"):
                    break

                result = self._score_answer(q["question"], q["expected"], answer)
                total = result.get("total", 5)
                if isinstance(total, (int, float)) and total > 10:
                    total = total / 3

                lesson["questions"].append({**q, "answer": answer, "score": total,
                                            "feedback": result.get("feedback", ""), "round": 2})
                lesson["scores"].append(total)
                print(f"\n  Score: {total}/10 | {result.get('feedback', '')}")

        # Summary
        avg_score = sum(lesson["scores"]) / len(lesson["scores"]) if lesson["scores"] else 0
        lesson["avg_score"] = round(avg_score, 1)

        print(f"\n{'='*60}")
        print(f"  LESSON COMPLETE — {topic}")
        print(f"  Questions answered: {len(lesson['scores'])}")
        print(f"  Average score: {avg_score:.1f}/10")
        if lesson["weak_areas"]:
            print(f"  Weak areas: {', '.join(lesson['weak_areas'][:5])}")
        print(f"{'='*60}\n")

        # Save lesson
        lesson_id = hashlib.md5(f"{topic}{time.time()}".encode()).hexdigest()[:12]
        lesson_file = self.lessons_dir / f"{lesson_id}.json"
        lesson_file.write_text(json.dumps(lesson, indent=2))

        # Store in knowledge base if decent performance
        if avg_score >= 5:
            self.swarm.kb.store(
                f"[lesson] {topic}",
                json.dumps({
                    "topic": topic,
                    "avg_score": avg_score,
                    "weak_areas": lesson["weak_areas"],
                    "questions_count": len(lesson["scores"]),
                }),
                avg_score,
                {"type": "lesson", "lesson_id": lesson_id}
            )

        return lesson


# ============================================================
# EXPORT/SHARE — Copyleft knowledge sharing
# David's philosophy: knowledge shared freely.
# ============================================================

class KnowledgeExporter:
    """
    Package the knowledge base and model config into a shareable bundle.
    Copyleft — knowledge shared freely. Anyone can import.
    """

    def __init__(self, kb):
        self.kb = kb
        self.export_dir = Path(CONFIG["export_dir"])
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def export_bundle(self, name=None):
        """
        Create a shareable knowledge bundle containing:
        - All knowledge entries
        - Knowledge graph
        - Model configuration
        - Score history
        - Lessons
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = name or f"asi-knowledge-{timestamp}"
        bundle_dir = self.export_dir / name
        bundle_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n  Exporting knowledge bundle: {name}")

        # 1. Knowledge entries
        entries = self.kb.get_all_entries()
        entries_file = bundle_dir / "knowledge-entries.jsonl"
        with open(entries_file, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
        print(f"    Knowledge entries: {len(entries)}")

        # 2. Knowledge graph
        graph_src = Path(CONFIG["graph_file"])
        if graph_src.exists():
            shutil.copy2(graph_src, bundle_dir / "graph.json")
            print(f"    Knowledge graph: copied")

        # 3. Model config
        config_export = {
            "model_routing": MODEL_ROUTING,
            "config": {k: v for k, v in CONFIG.items()
                       if k not in ("knowledge_dir", "skills_dir", "log_dir",
                                    "scores_file", "graph_file", "export_dir", "lessons_dir")},
            "agent_roles": {k: {"purpose": v["purpose"]} for k, v in AGENT_ROLES.items()},
        }
        (bundle_dir / "model-config.json").write_text(json.dumps(config_export, indent=2))
        print(f"    Model config: exported")

        # 4. Score history
        scores_file = Path(CONFIG["scores_file"])
        if scores_file.exists():
            shutil.copy2(scores_file, bundle_dir / "scores.jsonl")
            print(f"    Score history: copied")

        # 5. Lessons
        lessons_dir = Path(CONFIG["lessons_dir"])
        if lessons_dir.exists():
            lesson_files = list(lessons_dir.glob("*.json"))
            if lesson_files:
                (bundle_dir / "lessons").mkdir(exist_ok=True)
                for lf in lesson_files:
                    shutil.copy2(lf, bundle_dir / "lessons" / lf.name)
                print(f"    Lessons: {len(lesson_files)}")

        # 6. Manifest
        manifest = {
            "name": name,
            "created": datetime.now().isoformat(),
            "version": "2.0",
            "license": "Copyleft — knowledge shared freely",
            "creator": "Alex & David Weatherspoon",
            "motto": "From Pain to Purpose. From Passion to Prophet.",
            "stats": self.kb.stats(),
            "contents": {
                "entries": len(entries),
                "has_graph": graph_src.exists(),
                "has_scores": scores_file.exists(),
                "lessons": len(list(lessons_dir.glob("*.json"))) if lessons_dir.exists() else 0,
            }
        }
        (bundle_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

        # 7. Create zip
        zip_path = self.export_dir / f"{name}.zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_path in bundle_dir.rglob("*"):
                if file_path.is_file():
                    zf.write(file_path, file_path.relative_to(bundle_dir))

        # Clean up directory (keep zip)
        shutil.rmtree(bundle_dir)

        print(f"\n  Bundle exported: {zip_path}")
        print(f"  Size: {zip_path.stat().st_size / 1024:.1f} KB")
        print(f"  License: Copyleft — share freely")
        return str(zip_path)

    def import_bundle(self, zip_path):
        """Import a knowledge bundle from a zip file."""
        zip_path = Path(zip_path)
        if not zip_path.exists():
            print(f"  File not found: {zip_path}")
            return False

        temp_dir = self.export_dir / "_import_temp"
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(temp_dir)

            # Import knowledge entries
            entries_file = temp_dir / "knowledge-entries.jsonl"
            imported = 0
            if entries_file.exists():
                for line in entries_file.read_text().strip().split("\n"):
                    if not line:
                        continue
                    entry = json.loads(line)
                    self.kb.store(
                        entry.get("query", ""),
                        entry.get("response", ""),
                        entry.get("score", 5),
                        entry.get("metadata", {})
                    )
                    imported += 1

            # Import graph (merge)
            graph_file = temp_dir / "graph.json"
            if graph_file.exists():
                imported_graph = json.loads(graph_file.read_text())
                for nid, node in imported_graph.get("nodes", {}).items():
                    if nid not in self.kb.graph.graph["nodes"]:
                        self.kb.graph.graph["nodes"][nid] = node
                for edge in imported_graph.get("edges", []):
                    self.kb.graph.graph["edges"].append(edge)
                self.kb.graph._save_graph()

            print(f"\n  Imported {imported} knowledge entries")
            print(f"  Knowledge base: {self.kb.stats()}")
            return True

        except Exception as e:
            print(f"  Import error: {e}")
            return False
        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)


# ============================================================
# STATUS DASHBOARD — System health at a glance
# ============================================================

class Dashboard:
    """
    System health dashboard showing:
    - Total knowledge entries + avg score
    - Score trend over time
    - Weakest domains
    - Model health (response times, error rates)
    - Last improvement cycle results
    """

    def __init__(self, kb):
        self.kb = kb

    def show(self):
        """Display the full dashboard."""
        stats = self.kb.stats()
        scores_file = Path(CONFIG["scores_file"])

        print(f"\n{'='*60}")
        print(f"  LOCAL ASI v2 — DASHBOARD")
        print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")

        # --- Knowledge Base ---
        print(f"\n  KNOWLEDGE BASE")
        print(f"  {'Entries:':<25} {stats['total_entries']}")
        print(f"  {'Total queries:':<25} {stats['total_queries']}")
        print(f"  {'Average score:':<25} {stats['avg_score']}/10")
        print(f"  {'Graph concepts:':<25} {stats.get('graph_concepts', 0)}")
        print(f"  {'Graph edges:':<25} {stats.get('graph_edges', 0)}")

        # --- Score Trend ---
        if scores_file.exists():
            lines = scores_file.read_text().strip().split("\n")
            entries = [json.loads(l) for l in lines if l.strip()]

            if len(entries) >= 2:
                recent = entries[-10:]
                older = entries[:-10] if len(entries) > 10 else entries[:len(entries)//2]
                recent_avg = sum(e.get("score", 5) for e in recent) / len(recent)
                older_avg = sum(e.get("score", 5) for e in older) / len(older) if older else recent_avg

                trend = recent_avg - older_avg
                trend_icon = "UP" if trend > 0.3 else "DOWN" if trend < -0.3 else "STABLE"

                print(f"\n  SCORE TREND")
                print(f"  {'Recent avg (last 10):':<25} {recent_avg:.1f}/10")
                print(f"  {'Previous avg:':<25} {older_avg:.1f}/10")
                print(f"  {'Trend:':<25} {trend_icon} ({trend:+.1f})")

            # --- Weakest Domains ---
            if entries:
                domain_scores = defaultdict(list)
                for e in entries:
                    query = e.get("query", "")
                    # Categorize by first significant word
                    words = [w.lower() for w in query.split() if len(w) > 3]
                    category = words[0] if words else "general"
                    domain_scores[category].append(e.get("score", 5))

                domain_avgs = {
                    cat: sum(scores) / len(scores)
                    for cat, scores in domain_scores.items()
                    if len(scores) >= 1
                }
                weakest = sorted(domain_avgs.items(), key=lambda x: x[1])[:5]

                if weakest:
                    print(f"\n  WEAKEST DOMAINS")
                    for domain, avg in weakest:
                        count = len(domain_scores[domain])
                        print(f"    {domain:<20} {avg:.1f}/10  ({count} queries)")

            # --- Hallucination Risk ---
            risk_entries = [e for e in entries if "hallucination_risk" in e]
            if risk_entries:
                avg_risk = sum(e["hallucination_risk"] for e in risk_entries) / len(risk_entries)
                print(f"\n  RED TEAM METRICS")
                print(f"  {'Avg hallucination risk:':<25} {avg_risk:.1f}/10")
                print(f"  {'Audited queries:':<25} {len(risk_entries)}")
                verdicts = defaultdict(int)
                for e in risk_entries:
                    verdicts[e.get("red_team_verdict", "unknown")] += 1
                for verdict, count in sorted(verdicts.items()):
                    print(f"  {'  ' + verdict + ':':<25} {count}")

            # --- Recent Queries ---
            print(f"\n  RECENT QUERIES")
            for e in entries[-5:]:
                rt_mark = ""
                if e.get("red_team_verdict") == "fail":
                    rt_mark = " [RT:FAIL]"
                elif e.get("red_team_verdict") == "pass":
                    rt_mark = " [RT:PASS]"
                print(f"    [{e.get('score', '?')}/10] {e.get('query', '?')[:45]}... ({e.get('elapsed', '?')}s){rt_mark}")

        # --- Model Health ---
        print(f"\n  MODEL HEALTH")
        if _model_metrics:
            for model, metrics in sorted(_model_metrics.items()):
                calls = metrics["calls"]
                errors = metrics["errors"]
                avg_time = metrics["total_time"] / calls if calls > 0 else 0
                error_rate = (errors / calls * 100) if calls > 0 else 0
                print(f"    {model:<25} calls={calls}  errors={errors} ({error_rate:.0f}%)  avg={avg_time:.1f}s")
        else:
            print(f"    No model calls recorded this session yet.")

        # --- Multi-Model Routing ---
        print(f"\n  MODEL ROUTING")
        for role, route in MODEL_ROUTING.items():
            model = route["model"] or "(any available)"
            print(f"    {role:<15} -> {model:<25} ({route['reason'][:40]})")

        # --- Lessons ---
        lessons_dir = Path(CONFIG["lessons_dir"])
        if lessons_dir.exists():
            lesson_files = list(lessons_dir.glob("*.json"))
            if lesson_files:
                print(f"\n  TEACHING")
                print(f"  {'Total lessons:':<25} {len(lesson_files)}")
                # Show most recent lesson
                most_recent = max(lesson_files, key=lambda f: f.stat().st_mtime)
                try:
                    lesson = json.loads(most_recent.read_text())
                    print(f"  {'Last topic:':<25} {lesson.get('topic', '?')}")
                    print(f"  {'Last score:':<25} {lesson.get('avg_score', '?')}/10")
                    if lesson.get("weak_areas"):
                        print(f"  {'Weak areas:':<25} {', '.join(lesson['weak_areas'][:3])}")
                except:
                    pass

        print(f"\n{'='*60}\n")


# ============================================================
# INTERACTIVE CLI
# ============================================================

def print_banner():
    print("""
+===========================================================+
|                    LOCAL ASI v2                            |
|         Distilled Artificial Superintelligence             |
|                                                           |
|  Alex & David Weatherspoon |
|  "From Pain to Purpose. From Passion to Prophet."         |
|                                                           |
|  v2 Upgrades — Weatherspoon Vision:                       |
|    Multi-model orchestration (right model, right job)     |
|    Agent-to-Agent protocol (structured messaging)         |
|    Knowledge graph (connected concepts)                   |
|    Red team agent (adversarial hallucination hunter)       |
|    Teaching protocol (adaptive curriculum)                 |
|    Export/share (copyleft knowledge sharing)               |
|    Status dashboard (system health at a glance)           |
|                                                           |
|  Inspired by: Smart MCP Server, Teacher IDE, AutoGem,     |
|  Codepilot, CVE-2025-8901, and 209 repos.                |
|                                                           |
|  100% LOCAL. Zero cloud. Yours forever.                   |
+===========================================================+
    """)

def main():
    print_banner()

    if not ollama_available():
        print("  [!] Ollama not running. Start it with: ollama serve")
        print("  [!] Then pull a model: ollama pull qwen2.5:7b")
        sys.exit(1)

    swarm = ASISwarm()
    improver = SelfImprover(swarm)
    teacher = TeachingProtocol(swarm)
    exporter = KnowledgeExporter(swarm.kb)
    dashboard = Dashboard(swarm.kb)

    print(f"  Primary model: {CONFIG['model']}")
    print(f"  Critic model:  {MODEL_ROUTING['critic']['model']}")
    print(f"  Red team model: {MODEL_ROUTING['red_team']['model']}")
    try:
        skills_count = len(list(Path(CONFIG['skills_dir']).glob('*/SKILL.md')))
    except:
        skills_count = 0
    print(f"  Skills: {skills_count} loaded")
    print(f"  Knowledge: {swarm.kb.stats()}")
    print(f"\n  Commands:")
    print(f"    [query]       — Ask anything (multi-agent pipeline)")
    print(f"    /improve      — Run self-improvement cycle")
    print(f"    /stats        — Show knowledge base stats")
    print(f"    /dashboard    — Full system health dashboard")
    print(f"    /teach TOPIC  — Start a teaching session")
    print(f"    /export       — Export knowledge bundle (copyleft)")
    print(f"    /import FILE  — Import a knowledge bundle")
    print(f"    /agents N     — Set number of agents (default: 5)")
    print(f"    /rounds N     — Set improvement rounds (default: 3)")
    print(f"    /model NAME   — Switch primary model")
    print(f"    /routing      — Show/edit model routing table")
    print(f"    /search Q     — Search knowledge base + graph")
    print(f"    /graph        — Show knowledge graph stats")
    print(f"    /redteam Q    — Run red team audit on last response")
    print(f"    /quit         — Exit")
    print()

    last_response = ""  # Track last response for /redteam

    while True:
        try:
            query = input("  ASI > ").strip()
            if not query:
                continue

            if query == "/quit":
                print("\n  Knowledge preserved. From Pain to Purpose.\n")
                break

            elif query == "/improve":
                improver.run_cycle()

            elif query == "/stats":
                stats = swarm.kb.stats()
                print(f"\n  Knowledge Base Stats:")
                print(f"    Entries: {stats['total_entries']}")
                print(f"    Total queries: {stats['total_queries']}")
                print(f"    Average score: {stats['avg_score']}")
                print(f"    Graph concepts: {stats.get('graph_concepts', 0)}")
                print(f"    Graph edges: {stats.get('graph_edges', 0)}")

                # Show score history
                scores_file = Path(CONFIG["scores_file"])
                if scores_file.exists():
                    lines = scores_file.read_text().strip().split("\n")
                    recent = [json.loads(l) for l in lines[-5:]]
                    print(f"\n  Recent queries:")
                    for r in recent:
                        print(f"    [{r['score']}/10] {r['query'][:50]}... ({r['elapsed']}s)")
                print()

            elif query == "/dashboard":
                dashboard.show()

            elif query.startswith("/teach"):
                parts = query.split(None, 1)
                if len(parts) < 2:
                    print("  Usage: /teach TOPIC")
                    print("  Example: /teach python decorators")
                else:
                    teacher.run_lesson(parts[1])

            elif query == "/export":
                path = exporter.export_bundle()
                print(f"  Share this file with anyone. Knowledge wants to be free.")

            elif query.startswith("/import "):
                path = query.split(None, 1)[1]
                exporter.import_bundle(path)

            elif query.startswith("/agents "):
                n = int(query.split()[1])
                CONFIG["num_agents"] = max(1, min(20, n))
                print(f"  Agents set to {CONFIG['num_agents']}")

            elif query.startswith("/rounds "):
                n = int(query.split()[1])
                CONFIG["rounds"] = max(1, min(10, n))
                print(f"  Rounds set to {CONFIG['rounds']}")

            elif query.startswith("/model "):
                new_model = query.split(None, 1)[1]
                CONFIG["model"] = new_model
                MODEL_ROUTING["researcher"]["model"] = new_model
                MODEL_ROUTING["synthesizer"]["model"] = new_model
                MODEL_ROUTING["improver"]["model"] = new_model
                print(f"  Primary model set to {CONFIG['model']}")
                print(f"  Updated routing for researcher, synthesizer, improver")

            elif query == "/routing":
                print(f"\n  MODEL ROUTING TABLE")
                print(f"  {'Role':<15} {'Model':<25} {'Reason'}")
                print(f"  {'-'*15} {'-'*25} {'-'*35}")
                for role, route in MODEL_ROUTING.items():
                    model = route["model"] or "(any available)"
                    print(f"  {role:<15} {model:<25} {route['reason']}")
                print(f"\n  To change: /route ROLE MODEL")
                print(f"  Example: /route critic llama3.2:3b")
                print()

            elif query.startswith("/route "):
                parts = query.split()
                if len(parts) >= 3:
                    role = parts[1]
                    model = parts[2]
                    if role in MODEL_ROUTING:
                        MODEL_ROUTING[role]["model"] = model
                        print(f"  {role} now uses {model}")
                    else:
                        print(f"  Unknown role: {role}")
                        print(f"  Available: {', '.join(MODEL_ROUTING.keys())}")
                else:
                    print("  Usage: /route ROLE MODEL")

            elif query.startswith("/search "):
                q = query.split(None, 1)[1]
                results = swarm.kb.search(q)
                if results:
                    for r in results:
                        concepts = r.get("metadata", {}).get("concepts", [])
                        concept_str = f" [{', '.join(concepts[:5])}]" if concepts else ""
                        print(f"\n  [{r['score']}/10] {r['query']}{concept_str}")
                        print(f"  {r['response'][:300]}...")
                else:
                    print("  No matching entries found.")

            elif query == "/graph":
                gstats = swarm.kb.graph.stats()
                print(f"\n  KNOWLEDGE GRAPH")
                print(f"    Concepts: {gstats['concepts']}")
                print(f"    Edges: {gstats['edges']}")
                print(f"    Entries mapped: {gstats['entries_mapped']}")

                # Show top concepts
                if swarm.kb.graph.graph["nodes"]:
                    top = sorted(
                        swarm.kb.graph.graph["nodes"].items(),
                        key=lambda x: len(x[1].get("mentions", [])),
                        reverse=True
                    )[:10]
                    print(f"\n    Top concepts:")
                    for cid, node in top:
                        mentions = len(node.get("mentions", []))
                        print(f"      {node['label']:<30} {mentions} mentions")
                print()

            elif query.startswith("/redteam"):
                if not last_response:
                    print("  No previous response to audit. Ask a question first.")
                else:
                    parts = query.split(None, 1)
                    q = parts[1] if len(parts) > 1 else "general query"
                    print(f"\n  Running red team audit...")
                    audit = swarm.red_team.audit(q, last_response)
                    summary = audit["summary"]
                    print(f"\n  RED TEAM AUDIT RESULTS")
                    print(f"    Hallucination risk: {summary.get('hallucination_risk', '?')}/10")
                    print(f"    Issues found: {summary.get('total_issues', 0)}")
                    print(f"    Verdict: {summary.get('verdict', '?')}")
                    if audit["issues"]:
                        print(f"\n    Issues:")
                        for iss in audit["issues"][:10]:
                            print(f"      [{iss.get('type','?')}] {iss.get('claim','?')[:60]}")
                            print(f"        Reason: {iss.get('reason','?')[:80]}")
                            print(f"        Severity: {iss.get('severity','?')}/10")
                    print()

            else:
                last_response = swarm.process(query)
                print(f"\n{last_response}\n")

        except KeyboardInterrupt:
            print("\n\n  Interrupted. Knowledge preserved.\n")
            break
        except Exception as e:
            print(f"\n  [Error] {e}\n")

def serve(port: int = 8765):
    """HTTP serve mode for Teacher IDE integration."""
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import json as _json

    swarm = AgentSwarm()

    class ASIHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/status':
                status = {
                    'running': True,
                    'ollama_connected': swarm.check_ollama(),
                    'knowledge_entries': len(swarm.knowledge.entries) if hasattr(swarm, 'knowledge') else 0,
                    'model_name': CONFIG.get('model', 'unknown')
                }
                self._respond(200, status)
            elif self.path == '/health':
                self._respond(200, {'ok': True})
            else:
                self._respond(404, {'error': 'Not found'})

        def do_POST(self):
            content_length = int(self.headers.get('Content-Length', 0))
            body = _json.loads(self.rfile.read(content_length)) if content_length else {}

            if self.path == '/query':
                prompt = body.get('prompt', '')
                result = swarm.process(prompt)
                self._respond(200, {
                    'answer': result,
                    'confidence': 0.8,
                    'sources': [],
                    'researcher_count': CONFIG.get('num_agents', 5)
                })
            elif self.path == '/teach':
                topic = body.get('topic', '')
                level = body.get('student_level', 'beginner')
                result = swarm.process(f'/teach {topic} at {level} level')
                self._respond(200, {
                    'answer': result,
                    'confidence': 0.8,
                    'sources': [],
                    'researcher_count': CONFIG.get('num_agents', 5)
                })
            else:
                self._respond(404, {'error': 'Not found'})

        def _respond(self, code, data):
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(_json.dumps(data).encode())

        def log_message(self, format, *args):
            pass  # Suppress default logging

    server = HTTPServer(('127.0.0.1', port), ASIHandler)
    print(f"\n  ASI HTTP server running on http://127.0.0.1:{port}")
    print(f"  Endpoints: GET /status, POST /query, POST /teach")
    print(f"  Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  ASI server stopped.\n")
        server.server_close()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == '--serve':
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 8765
        serve(port)
    else:
        main()
