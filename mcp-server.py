#!/usr/bin/env python3
"""
SMART MCP SERVER — Weatherspoon ASI
David Weatherspoon's Smart MCP Server pattern applied to the local ASI.

Exposes the full Weatherspoon ASI as HTTP JSON-RPC tools on port 8808.
Any AI system in the world can now talk to the Weatherspoon knowledge base.

Tools:
  POST /tool/ask              — Full ASI pipeline (research > critique > synthesize > improve > score)
  POST /tool/search_knowledge — Search the accumulated knowledge base
  POST /tool/teach            — Run a teaching session on a topic
  POST /tool/improve          — Trigger a self-improvement cycle
  POST /tool/list_skills      — List available skills from the 306-skill library
  POST /tool/get_skill        — Get full content of a specific skill
  POST /tool/status           — System health dashboard

Protocol: HTTP POST with JSON body, returns JSON response.
Port: 8808

Alex & David Weatherspoon
"From Pain to Purpose. From Passion to Prophet."
"""

import json
import os
import sys
import time
import hashlib
import traceback
from datetime import datetime
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

# ============================================================
# Import the ASI engine directly
# ============================================================

ASI_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ASI_DIR)

from asi import (
    ASISwarm, SelfImprover, KnowledgeBase, SkillRouter,
    CONFIG, AGENT_ROLES, ollama_generate, ollama_available
)

# ============================================================
# SERVER STATE — initialized once at startup
# ============================================================

swarm = None
improver = None
kb = None
router = None
start_time_ts = None
last_improvement = None

def init_asi():
    """Initialize the ASI components."""
    global swarm, improver, kb, router, start_time_ts
    swarm = ASISwarm()
    improver = SelfImprover(swarm)
    kb = swarm.kb
    router = swarm.router
    start_time_ts = datetime.now().isoformat()

# ============================================================
# TOOL IMPLEMENTATIONS
# ============================================================

def tool_ask(params):
    """Full ASI pipeline: research > critique > synthesize > improve > score."""
    query = params.get("query", "").strip()
    if not query:
        return {"error": "Missing required parameter: query"}

    if not ollama_available():
        return {"error": "Ollama not running. Start with: ollama serve"}

    response = swarm.process(query)

    # Pull the latest score from scores.jsonl
    score = None
    scores_file = Path(CONFIG["scores_file"])
    if scores_file.exists():
        lines = scores_file.read_text().strip().split("\n")
        if lines:
            last = json.loads(lines[-1])
            if last.get("query") == query:
                score = last.get("score")

    # Find skills that were matched
    skills = router.find_relevant_skills(query)

    # Find relevant knowledge entries
    prior = kb.search(query, top_k=3)
    sources = [{"query": p["query"], "score": p["score"]} for p in prior]

    return {
        "answer": response,
        "score": score,
        "skills_used": skills,
        "sources": sources,
        "model": CONFIG["model"],
        "agents": CONFIG["num_agents"],
        "rounds": CONFIG["rounds"]
    }


def tool_search_knowledge(params):
    """Search the accumulated knowledge base."""
    query = params.get("query", "").strip()
    if not query:
        return {"error": "Missing required parameter: query"}

    top_k = int(params.get("top_k", 5))
    results = kb.search(query, top_k=top_k)

    entries = []
    for r in results:
        entries.append({
            "id": r.get("id"),
            "query": r.get("query"),
            "response": r.get("response", "")[:2000],
            "score": r.get("score"),
            "timestamp": r.get("timestamp")
        })

    return {
        "query": query,
        "matches": len(entries),
        "entries": entries,
        "knowledge_stats": kb.stats()
    }


def tool_teach(params):
    """Run a teaching session on a topic."""
    topic = params.get("topic", "").strip()
    if not topic:
        return {"error": "Missing required parameter: topic"}

    num_questions = int(params.get("num_questions", 5))

    if not ollama_available():
        return {"error": "Ollama not running. Start with: ollama serve"}

    # Step 1: Generate questions about the topic
    gen_prompt = (
        f"Generate exactly {num_questions} progressively harder questions "
        f"about: {topic}\n\n"
        f"Format each as a numbered list. Questions should go from beginner "
        f"to advanced. Return ONLY the numbered questions, nothing else."
    )
    questions_raw = ollama_generate(gen_prompt, system="You are an expert teacher.")
    questions = [
        q.strip().lstrip("0123456789.)- ").strip()
        for q in questions_raw.strip().split("\n")
        if q.strip() and any(c.isalpha() for c in q)
    ][:num_questions]

    # Step 2: Answer each question through the ASI pipeline
    results = []
    for i, question in enumerate(questions):
        full_query = f"[Teaching: {topic}] {question}"
        answer = swarm.process(full_query)

        # Get score
        score = None
        scores_file = Path(CONFIG["scores_file"])
        if scores_file.exists():
            lines = scores_file.read_text().strip().split("\n")
            if lines:
                last = json.loads(lines[-1])
                score = last.get("score")

        results.append({
            "question_number": i + 1,
            "question": question,
            "answer": answer[:2000],
            "score": score
        })

    avg_score = sum(r["score"] for r in results if r["score"]) / max(1, len([r for r in results if r["score"]]))

    return {
        "topic": topic,
        "num_questions": len(results),
        "results": results,
        "average_score": round(avg_score, 1),
        "knowledge_stats": kb.stats()
    }


def tool_improve(params):
    """Trigger a self-improvement cycle."""
    global last_improvement

    num_entries = int(params.get("num_entries", 3))

    if not ollama_available():
        return {"error": "Ollama not running. Start with: ollama serve"}

    stats_before = kb.stats()

    # Get the entries that will be re-processed
    entries = sorted(
        kb.index["entries"],
        key=lambda x: x["score"]
    )[:num_entries]

    if not entries:
        return {
            "message": "No entries to improve. Process some queries first.",
            "knowledge_stats": stats_before
        }

    targets = [{"id": e["id"], "query": e["query"][:100], "old_score": e["score"]} for e in entries]

    # Run improvement
    improver.improve_worst(num_entries)

    stats_after = kb.stats()
    last_improvement = datetime.now().isoformat()

    return {
        "entries_processed": len(targets),
        "targets": targets,
        "stats_before": stats_before,
        "stats_after": stats_after,
        "improvement_time": last_improvement
    }


def tool_list_skills(params):
    """List available skills from the 306-skill library."""
    category_filter = params.get("category", "").strip().lower()
    skills_dir = Path(CONFIG["skills_dir"])

    skills = []
    for skill_path in sorted(skills_dir.iterdir()):
        skill_file = skill_path / "SKILL.md"
        if not skill_file.exists():
            continue

        name = skill_path.name

        # Skip internal directories
        if name.startswith("_"):
            continue

        # Apply category filter if provided
        if category_filter and category_filter not in name.lower():
            # Also check content for category match
            try:
                content = skill_file.read_text()[:500]
                if category_filter not in content.lower():
                    continue
            except:
                continue

        # Extract description from frontmatter
        description = ""
        try:
            content = skill_file.read_text()
            if content.startswith("---"):
                frontmatter = content.split("---", 2)[1] if content.count("---") >= 2 else ""
                for line in frontmatter.split("\n"):
                    if line.strip().startswith("description:"):
                        description = line.split(":", 1)[1].strip().strip('"').strip("'")
                        break
            if not description:
                # Fallback: first non-empty, non-heading line
                for line in content.split("\n"):
                    line = line.strip()
                    if line and not line.startswith("#") and not line.startswith("---"):
                        description = line[:150]
                        break
        except:
            pass

        skills.append({
            "name": name,
            "description": description[:200]
        })

    return {
        "total_skills": len(skills),
        "category_filter": category_filter or None,
        "skills": skills
    }


def tool_get_skill(params):
    """Get full content of a specific skill."""
    skill_name = params.get("skill_name", "").strip()
    if not skill_name:
        return {"error": "Missing required parameter: skill_name"}

    skill_file = Path(CONFIG["skills_dir"]) / skill_name / "SKILL.md"
    if not skill_file.exists():
        return {"error": f"Skill not found: {skill_name}"}

    content = skill_file.read_text()

    return {
        "skill_name": skill_name,
        "content": content,
        "size_bytes": len(content.encode()),
        "path": str(skill_file)
    }


def tool_status(params):
    """System health dashboard."""
    global last_improvement

    # Knowledge stats
    k_stats = kb.stats()

    # Model health
    model_ok = ollama_available()

    # Score history
    recent_scores = []
    scores_file = Path(CONFIG["scores_file"])
    if scores_file.exists():
        lines = scores_file.read_text().strip().split("\n")
        for line in lines[-10:]:
            try:
                recent_scores.append(json.loads(line))
            except:
                pass

    # Skills count
    skills_dir = Path(CONFIG["skills_dir"])
    skill_count = len([
        d for d in skills_dir.iterdir()
        if (d / "SKILL.md").exists() and not d.name.startswith("_")
    ]) if skills_dir.exists() else 0

    # Uptime
    uptime = None
    if start_time_ts:
        start_dt = datetime.fromisoformat(start_time_ts)
        delta = datetime.now() - start_dt
        uptime = str(delta).split(".")[0]

    return {
        "server": {
            "status": "running",
            "port": 8808,
            "started": start_time_ts,
            "uptime": uptime
        },
        "model": {
            "name": CONFIG["model"],
            "fallback": CONFIG["fallback_model"],
            "ollama_running": model_ok,
            "agents": CONFIG["num_agents"],
            "rounds": CONFIG["rounds"]
        },
        "knowledge": {
            "total_entries": k_stats["total_entries"],
            "total_queries": k_stats["total_queries"],
            "avg_score": k_stats["avg_score"]
        },
        "skills": {
            "total": skill_count,
            "directory": CONFIG["skills_dir"]
        },
        "last_improvement": last_improvement,
        "recent_scores": [
            {"query": s.get("query", "")[:80], "score": s.get("score"), "elapsed": s.get("elapsed")}
            for s in recent_scores[-5:]
        ]
    }


# ============================================================
# TOOL REGISTRY
# ============================================================

TOOLS = {
    "ask": {
        "handler": tool_ask,
        "description": "Send a question through the full ASI pipeline (research > critique > synthesize > improve > score)",
        "params": {"query": "string (required)"}
    },
    "search_knowledge": {
        "handler": tool_search_knowledge,
        "description": "Search the accumulated knowledge base",
        "params": {"query": "string (required)", "top_k": "int (default 5)"}
    },
    "teach": {
        "handler": tool_teach,
        "description": "Run a teaching session on a topic",
        "params": {"topic": "string (required)", "num_questions": "int (default 5)"}
    },
    "improve": {
        "handler": tool_improve,
        "description": "Trigger a self-improvement cycle on lowest-scored entries",
        "params": {"num_entries": "int (default 3)"}
    },
    "list_skills": {
        "handler": tool_list_skills,
        "description": "List available skills from the 306-skill library",
        "params": {"category": "string (optional filter)"}
    },
    "get_skill": {
        "handler": tool_get_skill,
        "description": "Get full SKILL.md content of a specific skill",
        "params": {"skill_name": "string (required)"}
    },
    "status": {
        "handler": tool_status,
        "description": "System health dashboard — knowledge stats, model health, recent scores",
        "params": {}
    },
}

# ============================================================
# HTTP SERVER
# ============================================================

class MCPHandler(BaseHTTPRequestHandler):
    """HTTP request handler for MCP tool endpoints."""

    def _send_json(self, data, status=200):
        body = json.dumps(data, indent=2, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self._send_json({})

    def do_GET(self):
        """GET / returns tool catalog. GET /tool/{name} returns tool info."""
        path = urlparse(self.path).path.rstrip("/")

        if path == "" or path == "/":
            self._send_json({
                "server": "Weatherspoon ASI — Smart MCP Server",
                "version": "1.0.0",
                "author": "David Weatherspoon",
                "motto": "From Pain to Purpose. From Passion to Prophet.",
                "protocol": "POST /tool/{name} with JSON body",
                "tools": {
                    name: {
                        "description": t["description"],
                        "params": t["params"],
                        "endpoint": f"/tool/{name}"
                    }
                    for name, t in TOOLS.items()
                }
            })
            return

        if path.startswith("/tool/"):
            tool_name = path[6:]
            if tool_name in TOOLS:
                t = TOOLS[tool_name]
                self._send_json({
                    "tool": tool_name,
                    "description": t["description"],
                    "params": t["params"],
                    "method": "POST",
                    "endpoint": f"/tool/{tool_name}"
                })
            else:
                self._send_json({"error": f"Unknown tool: {tool_name}"}, 404)
            return

        self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        """POST /tool/{name} — execute a tool."""
        path = urlparse(self.path).path.rstrip("/")

        if not path.startswith("/tool/"):
            self._send_json({"error": "Use POST /tool/{name}"}, 400)
            return

        tool_name = path[6:]
        if tool_name not in TOOLS:
            self._send_json({
                "error": f"Unknown tool: {tool_name}",
                "available": list(TOOLS.keys())
            }, 404)
            return

        # Parse JSON body
        params = {}
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > 0:
            body = self.rfile.read(content_length)
            try:
                params = json.loads(body.decode())
            except json.JSONDecodeError:
                self._send_json({"error": "Invalid JSON body"}, 400)
                return

        # Execute tool
        start = time.time()
        try:
            result = TOOLS[tool_name]["handler"](params)
            elapsed = round(time.time() - start, 2)
            self._send_json({
                "tool": tool_name,
                "success": True,
                "elapsed_seconds": elapsed,
                "result": result
            })
        except Exception as e:
            elapsed = round(time.time() - start, 2)
            self._send_json({
                "tool": tool_name,
                "success": False,
                "elapsed_seconds": elapsed,
                "error": str(e),
                "traceback": traceback.format_exc()
            }, 500)

    def log_message(self, format, *args):
        """Custom log format."""
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"  [{ts}] {args[0]}")


# ============================================================
# MAIN
# ============================================================

def main():
    print("""
 ========================================================
   SMART MCP SERVER — Weatherspoon ASI
   David Weatherspoon's Agent-to-Agent Protocol
   Alex & David Weatherspoon

   Any AI system in the world can now talk to the
   Weatherspoon knowledge base.
 ========================================================
    """)

    # Initialize ASI components
    print("  Initializing ASI engine...")
    init_asi()

    k_stats = kb.stats()
    skills_dir = Path(CONFIG["skills_dir"])
    skill_count = len([
        d for d in skills_dir.iterdir()
        if (d / "SKILL.md").exists() and not d.name.startswith("_")
    ]) if skills_dir.exists() else 0

    print(f"  Model: {CONFIG['model']}")
    print(f"  Knowledge: {k_stats['total_entries']} entries, avg score {k_stats['avg_score']:.1f}")
    print(f"  Skills: {skill_count} loaded")
    print(f"  Ollama: {'running' if ollama_available() else 'NOT RUNNING'}")

    # Start HTTP server
    port = 8808
    server = HTTPServer(("0.0.0.0", port), MCPHandler)
    print(f"\n  MCP Server listening on port {port}")
    print(f"  Catalog:  http://localhost:{port}/")
    print(f"  Example:  curl -X POST http://localhost:{port}/tool/status")
    print(f"  Ask:      curl -X POST http://localhost:{port}/tool/ask -d '{{\"query\": \"What is XELA?\"}}'")
    print(f"\n  Tools available: {', '.join(TOOLS.keys())}")
    print(f"  Press Ctrl+C to stop.\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped. Knowledge preserved.\n")
        server.server_close()


if __name__ == "__main__":
    main()
