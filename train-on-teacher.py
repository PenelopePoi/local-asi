#!/usr/bin/env python3
"""
Train Weatherspoon ASI on the Teacher IDE repository.
Feeds key source files into the knowledge graph so the ASI
understands Teacher's architecture, patterns, and codebase.
"""

import json
import hashlib
import os
import time
from datetime import datetime
from pathlib import Path

KNOWLEDGE_DIR = Path(os.path.expanduser("~/local-asi/knowledge"))
TEACHER_DIR = Path(os.path.expanduser("~/Teacher"))

# Key files to ingest — architecture, protocols, agents, widgets, configs
TRAINING_FILES = [
    # Core docs
    ("README.md", "Teacher IDE overview and features"),
    ("CLAUDE.md", "Development commands, architecture patterns, and coding guidelines"),
    # Protocols
    ("packages/teacher-core/src/common/teacher-protocol.ts", "Teacher service protocol — curriculum, lessons, workspace"),
    ("packages/teacher-core/src/common/progress-protocol.ts", "Progress tracking protocol — student progress, skill mastery"),
    ("packages/teacher-core/src/common/asi-bridge-protocol.ts", "ASI bridge protocol — connection to local ASI swarm"),
    ("packages/teacher-core/src/common/teacher-preferences.ts", "Teacher preferences schema"),
    # Frontend module
    ("packages/teacher-core/src/browser/teacher-frontend-module.ts", "Frontend DI bindings for all Teacher widgets and agents"),
    # AI Agents
    ("packages/teacher-core/src/browser/agents/tutor-agent.ts", "Tutor agent — Socratic teaching AI mentor"),
    ("packages/teacher-core/src/browser/agents/explain-agent.ts", "Explain agent — code explanation with visual analogies"),
    ("packages/teacher-core/src/browser/agents/review-agent.ts", "Review agent — teaching-focused code review"),
    # Widgets
    ("packages/teacher-core/src/browser/widgets/teacher-welcome-widget.tsx", "Welcome screen with status, actions, progress"),
    ("packages/teacher-core/src/browser/widgets/progress-dashboard-widget.tsx", "Progress dashboard — lessons, scores, skills"),
    ("packages/teacher-core/src/browser/widgets/curriculum-browser-widget.tsx", "Curriculum browser — course/module/lesson tree"),
    ("packages/teacher-core/src/browser/widgets/skill-browser-widget.tsx", "Skill browser — search and filter 300+ skills"),
    ("packages/teacher-core/src/browser/widgets/learning-analytics-widget.tsx", "Learning analytics — streaks, heatmap, weak areas"),
    ("packages/teacher-core/src/browser/widgets/ai-history-search-widget.tsx", "AI history search — filter past conversations"),
    ("packages/teacher-core/src/browser/widgets/learning-path-widget.tsx", "Learning path — visual recommended pathway"),
    # CSS
    ("packages/teacher-core/src/browser/style/teacher.css", "All Teacher widget styles — Theia CSS variables"),
    # AI infrastructure
    ("packages/ai-core/src/common/agent.ts", "Agent interface and PromptVariantSet"),
    ("packages/ai-chat/src/common/chat-agents.ts", "Chat agent base classes"),
    # Config
    ("packages/ai-ollama/src/common/ollama-preferences.ts", "Ollama provider preferences"),
    ("doc/coding-guidelines.md", "Theia coding guidelines — DI, naming, style, theming"),
]


def load_index():
    index_file = KNOWLEDGE_DIR / "index.json"
    if index_file.exists():
        return json.loads(index_file.read_text())
    return {"entries": [], "total_queries": 0, "avg_score": 0}


def save_index(index):
    index_file = KNOWLEDGE_DIR / "index.json"
    index_file.write_text(json.dumps(index, indent=2))


def store_knowledge(query, response, score, metadata=None):
    """Store knowledge entry in ASI knowledge base."""
    entry_id = hashlib.md5(f"{query}{time.time()}".encode()).hexdigest()[:12]
    entry = {
        "id": entry_id,
        "query": query,
        "response": response[:8000],
        "score": score,
        "timestamp": datetime.now().isoformat(),
        "metadata": metadata or {}
    }

    entry_file = KNOWLEDGE_DIR / f"{entry_id}.json"
    entry_file.write_text(json.dumps(entry, indent=2))

    index = load_index()
    index["entries"].append({
        "id": entry_id,
        "query": query[:200],
        "score": score,
        "timestamp": entry["timestamp"]
    })
    index["total_queries"] = len(index["entries"])
    scores = [e["score"] for e in index["entries"] if "score" in e]
    index["avg_score"] = sum(scores) / len(scores) if scores else 0
    save_index(index)

    return entry_id


def update_graph(concept, related_concepts, description):
    """Add concept to knowledge graph."""
    graph_file = KNOWLEDGE_DIR / "graph.json"
    if graph_file.exists():
        graph = json.loads(graph_file.read_text())
    else:
        graph = {"nodes": {}, "edges": []}

    graph["nodes"][concept] = {
        "description": description,
        "updated": datetime.now().isoformat()
    }

    for related in related_concepts:
        edge = {"from": concept, "to": related, "type": "related_to"}
        if edge not in graph["edges"]:
            graph["edges"].append(edge)

    graph_file.write_text(json.dumps(graph, indent=2))


def train():
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\n  Training Weatherspoon ASI on Teacher IDE")
    print(f"  Repository: {TEACHER_DIR}")
    print(f"  Knowledge dir: {KNOWLEDGE_DIR}")
    print(f"  Files to ingest: {len(TRAINING_FILES)}")
    print()

    ingested = 0
    skipped = 0

    for rel_path, description in TRAINING_FILES:
        full_path = TEACHER_DIR / rel_path
        if not full_path.exists():
            print(f"  SKIP  {rel_path} (not found)")
            skipped += 1
            continue

        content = full_path.read_text(errors='replace')

        # Truncate very large files
        if len(content) > 15000:
            content = content[:15000] + f"\n\n... (truncated at 15000 chars, full file is {len(content)} chars)"

        query = f"What is {rel_path} in the Teacher IDE and what does it do?"
        response = f"# {rel_path}\n\n**Description:** {description}\n\n**Content:**\n```\n{content}\n```"

        # Determine related concepts
        concepts = []
        if "agent" in rel_path.lower():
            concepts = ["Teacher IDE", "AI Agents", "Theia", "Chat", "Ollama"]
        elif "widget" in rel_path.lower():
            concepts = ["Teacher IDE", "UI Widgets", "React", "Theia", "ReactWidget"]
        elif "protocol" in rel_path.lower():
            concepts = ["Teacher IDE", "Service Protocol", "RPC", "Backend"]
        elif "preference" in rel_path.lower():
            concepts = ["Teacher IDE", "Configuration", "Settings"]
        elif rel_path.endswith(".css"):
            concepts = ["Teacher IDE", "Styling", "CSS", "Theming"]
        elif rel_path.endswith(".md"):
            concepts = ["Teacher IDE", "Documentation"]
        else:
            concepts = ["Teacher IDE", "Core"]

        entry_id = store_knowledge(query, response, 9.0, {
            "source": "teacher-repo-training",
            "file": rel_path,
            "description": description,
            "category": "codebase"
        })

        # Add to graph
        concept_name = Path(rel_path).stem.replace("-", " ").replace("_", " ").title()
        update_graph(concept_name, concepts, description)

        print(f"  OK    {rel_path} ({len(content)} chars) → {entry_id}")
        ingested += 1

    # Add a summary entry
    summary = f"""Teacher IDE is an Eclipse Theia-based IDE fork with AI-powered tutoring capabilities.

Key architecture:
- 91 packages in a Lerna monorepo
- React 18 + TypeScript + InversifyJS DI
- 7 custom widgets: welcome, progress dashboard, curriculum browser, skill browser, learning analytics, AI history search, learning path
- 3 AI agents: Tutor (Socratic), Explain (visual analogies), Review (teaching-focused)
- Local ASI bridge for multi-agent research swarm
- 300+ skills library symlinked from ~/.claude/skills/
- Ollama integration for local LLM inference
- MCP (Model Context Protocol) for external tool integration

Services:
- TeacherService: curriculum management, lesson loading, workspace templates
- ProgressTrackingService: student progress, skill mastery, learning analytics
- ASIBridgeService: bridge to local ASI swarm on port 8808

Coding patterns:
- ReactWidget base class for all UI
- @injectable() + @inject() + @postConstruct() for DI
- nls.localize() for all user-facing strings
- codicon icons, var(--theia-*) CSS variables
- ContributionProvider pattern for extensibility
- WidgetFactory for panel registration
"""

    store_knowledge(
        "What is Teacher IDE and how is it architected?",
        summary, 10.0,
        {"source": "teacher-repo-training", "category": "architecture-summary"}
    )
    update_graph("Teacher IDE", [
        "Theia", "React", "TypeScript", "InversifyJS",
        "Ollama", "ASI", "MCP", "Curriculum", "Progress Tracking"
    ], "AI-powered IDE for learning to code, built on Eclipse Theia")

    print(f"\n  Done: {ingested} files ingested, {skipped} skipped")
    print(f"  Knowledge entries: {load_index()['total_queries']}")
    print()


if __name__ == "__main__":
    train()
