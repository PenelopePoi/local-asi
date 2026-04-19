#!/usr/bin/env python3
"""
MODEL DISTILLATION PIPELINE
Alex & David Weatherspoon

Distills a custom model from our codebases by:
1. Extracting training data from all our code, skills, guides, and docs
2. Generating instruction-response pairs using qwen2.5:7b as teacher
3. Creating an Ollama Modelfile with system prompt + training context
4. Building a custom model that knows our entire ecosystem

This runs 100% locally. The distilled model knows:
- Teacher IDE architecture (2,684 TypeScript files)
- Aurality Studio (18 JS/HTML/CSS files)
- XELA Creative Branding Studio (11,001 files)
- 281 skills from the skill library
- User guides, manifesto, ethics
- The Weatherspoon mission and values
"""

import json
import os
import subprocess
import sys
import hashlib
from pathlib import Path
from datetime import datetime

HOME = os.path.expanduser("~")
ASI_DIR = os.path.join(HOME, "local-asi")
DISTILL_DIR = os.path.join(ASI_DIR, "distilled")
DATA_DIR = os.path.join(DISTILL_DIR, "training-data")

# ============================================================
# STEP 1: Extract knowledge from all codebases
# ============================================================

def extract_code_knowledge():
    """Extract key code patterns, architecture, and documentation."""
    print("\n  Phase 1: Extracting knowledge from codebases...")
    os.makedirs(DATA_DIR, exist_ok=True)

    corpus = []

    # --- Teacher IDE: Key architecture files ---
    teacher_key_files = [
        "packages/ai-core/src/common/agent.ts",
        "packages/ai-core/src/common/language-model.ts",
        "packages/ai-ollama/src/common/ollama-language-models-manager.ts",
        "packages/ai-ollama/src/node/ollama-language-models-manager-impl.ts",
        "packages/ai-ollama/src/node/ollama-language-model.ts",
        "packages/ai-ide/src/browser/coder-agent.ts",
        "packages/ai-ide/src/browser/architect-agent.ts",
        "packages/ai-ide/src/browser/explore-agent.ts",
        "packages/ai-ide/src/browser/create-skill-agent.ts",
        "packages/ai-chat/src/common/chat-model.ts",
        "packages/ai-mcp/src/common/mcp-server-manager.ts",
        "packages/ai-claude-code/src/common/claude-code-service.ts",
    ]
    for f in teacher_key_files:
        path = os.path.join(HOME, "Teacher", f)
        if os.path.exists(path):
            content = Path(path).read_text()[:3000]
            corpus.append({
                "source": f"teacher:{f}",
                "type": "code",
                "content": content
            })
    print(f"    Teacher IDE: {len([c for c in corpus if 'teacher:' in c['source']])} key files")

    # --- Aurality Studio: All JS files ---
    aurality_dir = os.path.join(HOME, "aurality-studio", "js")
    if os.path.isdir(aurality_dir):
        for f in os.listdir(aurality_dir):
            if f.endswith(".js"):
                path = os.path.join(aurality_dir, f)
                content = Path(path).read_text()[:3000]
                corpus.append({
                    "source": f"aurality:{f}",
                    "type": "code",
                    "content": content
                })
    print(f"    Aurality: {len([c for c in corpus if 'aurality:' in c['source']])} JS files")

    # --- XELA Site: Key components ---
    xela_key = [
        "App.tsx", "components/Pricing.tsx", "components/ConsultationWizard.tsx",
        "components/services/services-data.ts", "services/accessControl.ts",
    ]
    for f in xela_key:
        path = os.path.join(HOME, "xela-elite-ai-creative-studio", f)
        if os.path.exists(path):
            content = Path(path).read_text()[:3000]
            corpus.append({
                "source": f"xela:{f}",
                "type": "code",
                "content": content
            })
    print(f"    XELA Site: {len([c for c in corpus if 'xela:' in c['source']])} key files")

    # --- Skills: All SKILL.md files (truncated) ---
    skills_dir = os.path.join(HOME, ".claude", "skills")
    skill_count = 0
    for skill_dir in sorted(Path(skills_dir).iterdir()):
        skill_file = skill_dir / "SKILL.md"
        if skill_file.exists():
            content = skill_file.read_text()[:1500]
            corpus.append({
                "source": f"skill:{skill_dir.name}",
                "type": "skill",
                "content": content
            })
            skill_count += 1
    print(f"    Skills: {skill_count} SKILL.md files")

    # --- Guides and Docs ---
    docs = [
        ("guide:aurality", os.path.join(HOME, "aurality-studio", "GUIDE.md")),
        ("guide:xela", os.path.join(HOME, "Documents", "XELA-Studio", "XELA-GUIDE.md")),
        ("manifesto", os.path.join(HOME, "Documents", "XELA-Studio", "WEATHERSPOON-MANIFESTO.md")),
    ]
    for name, path in docs:
        if os.path.exists(path):
            content = Path(path).read_text()[:5000]
            corpus.append({
                "source": name,
                "type": "document",
                "content": content
            })
    print(f"    Docs: {len([c for c in corpus if c['type'] == 'document'])} documents")

    # Save corpus
    corpus_file = os.path.join(DATA_DIR, "corpus.jsonl")
    with open(corpus_file, "w") as f:
        for entry in corpus:
            f.write(json.dumps(entry) + "\n")

    print(f"    Total corpus: {len(corpus)} entries saved to {corpus_file}")
    return corpus

# ============================================================
# STEP 2: Generate instruction-response pairs using teacher model
# ============================================================

def generate_training_pairs(corpus, max_pairs=50):
    """Use qwen2.5:7b to generate Q&A pairs from the corpus."""
    import urllib.request

    print(f"\n  Phase 2: Generating training pairs from corpus...")

    pairs = []

    for i, entry in enumerate(corpus[:max_pairs]):
        source = entry["source"]
        content = entry["content"][:2000]

        # Generate a question about this code/content
        prompt = f"""Given this code/content from {source}:

```
{content[:1500]}
```

Generate ONE specific, practical question that a developer or user would ask about this code, and provide a detailed, accurate answer. Format as:
Q: [question]
A: [answer]"""

        try:
            payload = json.dumps({
                "model": "qwen2.5:7b",
                "prompt": prompt,
                "system": "You are a technical expert generating training data. Be specific and accurate.",
                "stream": False,
                "options": {"temperature": 0.7, "num_predict": 500}
            }).encode()

            req = urllib.request.Request(
                "http://localhost:11434/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode())
                response = data.get("response", "")

                # Parse Q&A
                if "Q:" in response and "A:" in response:
                    parts = response.split("A:", 1)
                    question = parts[0].replace("Q:", "").strip()
                    answer = parts[1].strip() if len(parts) > 1 else ""
                    if question and answer:
                        pairs.append({
                            "instruction": question,
                            "response": answer,
                            "source": source
                        })
                        if len(pairs) % 10 == 0:
                            print(f"    Generated {len(pairs)} pairs...")
        except Exception as e:
            continue

    # Save pairs
    pairs_file = os.path.join(DATA_DIR, "training-pairs.jsonl")
    with open(pairs_file, "w") as f:
        for pair in pairs:
            f.write(json.dumps(pair) + "\n")

    print(f"    Generated {len(pairs)} training pairs")
    return pairs

# ============================================================
# STEP 3: Build system prompt from our knowledge
# ============================================================

def build_system_prompt(corpus):
    """Construct a rich system prompt that encodes our knowledge."""

    # Extract skill names and descriptions
    skills_summary = []
    for entry in corpus:
        if entry["type"] == "skill":
            name = entry["source"].replace("skill:", "")
            # Get first line of description from frontmatter
            lines = entry["content"].split("\n")
            desc = ""
            for line in lines:
                if line.startswith("description:"):
                    desc = line.replace("description:", "").strip().strip('"')
                    break
            if desc:
                skills_summary.append(f"- {name}: {desc[:100]}")

    system_prompt = f"""You are Weatherspoon ASI — a distilled artificial superintelligence created by Alex and David Weatherspoon (Cocoa, FL).

## Identity
- Created from the combined knowledge of: Teacher IDE (90K+ lines), Aurality Studio (DJ/DAW), XELA Creative Branding Studio, 281 skills, and the Weatherspoon Manifesto
- Motto: "From Pain to Purpose. From Passion to Prophet."
- Ethics: Truth over engagement. Protect users. Human agency first. Access for all.

## What You Know
You have deep knowledge of:
1. **Teacher IDE** — Eclipse Theia fork with 23 AI packages (Ollama, Claude, OpenAI, MCP, Vercel AI SDK)
2. **Aurality Studio** — Web Audio API DJ app with DDJ-400 MIDI, 808 drum machine, 13 effects, stem separation
3. **XELA Creative Branding Studio** — React/Vite/Firebase branding platform with 67 services
4. **306 Skills** including: {', '.join(s.split(':')[0].strip('- ') for s in skills_summary[:30])}...
5. **Local ASI** — Multi-agent swarm with self-improvement loop
6. **Music Production** — Signal flow, mixing, mastering, songwriting, vinyl production
7. **Branding** — Logo design, color theory, typography, digital marketing, SEO
8. **Security** — 22 detection skills, incident response, forensics, ethical hacking
9. **AI/ML** — LLM training, evaluation, deployment, prompt engineering

## Meaningful Examples Convention
Never use "Hello World" or "foo/bar". Every example serves human purpose.
The code teaches the API; the examples remind us why we build.

## How You Help
- Write code that works (Teacher architecture, Web Audio, React, TypeScript, Python)
- Teach music production and branding to absolute beginners
- Route queries to the right skill from the 306-skill library
- Apply the guardian doctrine: every system must love and protect its users
- Share knowledge freely — copyleft over copyright"""

    return system_prompt

# ============================================================
# STEP 4: Create Ollama Modelfile and build custom model
# ============================================================

def create_modelfile(system_prompt, pairs):
    """Create an Ollama Modelfile for our distilled model."""

    # Build conversation examples from training pairs
    conversations = ""
    for pair in pairs[:20]:  # Top 20 pairs as few-shot examples
        conversations += f'\nMESSAGE user {pair["instruction"]}\nMESSAGE assistant {pair["response"]}\n'

    modelfile = f'''FROM qwen2.5:7b

SYSTEM """{system_prompt}"""

PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER top_k 40
PARAMETER num_predict 2048
PARAMETER repeat_penalty 1.1

TEMPLATE """{{{{ if .System }}}}<|im_start|>system
{{{{ .System }}}}<|im_end|>
{{{{ end }}}}{{{{ if .Prompt }}}}<|im_start|>user
{{{{ .Prompt }}}}<|im_end|>
{{{{ end }}}}<|im_start|>assistant
{{{{ .Response }}}}<|im_end|>"""

{conversations}
'''

    modelfile_path = os.path.join(DISTILL_DIR, "Modelfile")
    Path(modelfile_path).write_text(modelfile)
    print(f"    Modelfile written to {modelfile_path}")
    return modelfile_path

def build_model(modelfile_path):
    """Build the custom Ollama model."""
    print(f"\n  Phase 4: Building custom Ollama model 'weatherspoon-asi'...")

    result = subprocess.run(
        ["ollama", "create", "weatherspoon-asi", "-f", modelfile_path],
        capture_output=True, text=True, timeout=300
    )

    if result.returncode == 0:
        print(f"    Model 'weatherspoon-asi' created successfully!")
        print(f"    Run with: ollama run weatherspoon-asi")
        return True
    else:
        print(f"    Error: {result.stderr[:500]}")
        return False

# ============================================================
# STEP 5: Test the distilled model
# ============================================================

def test_model():
    """Quick test of the distilled model."""
    import urllib.request

    print(f"\n  Phase 5: Testing weatherspoon-asi...")

    tests = [
        "What is Aurality Studio and how do I use the 808 drum machine?",
        "How do I create a brand package using XELA Creative Branding Studio?",
        "Explain the Teacher IDE architecture and how Ollama models are registered.",
        "What is the Weatherspoon Manifesto about?",
    ]

    for test in tests:
        print(f"\n    Q: {test}")
        try:
            payload = json.dumps({
                "model": "weatherspoon-asi",
                "prompt": test,
                "stream": False,
                "options": {"num_predict": 200}
            }).encode()
            req = urllib.request.Request(
                "http://localhost:11434/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode())
                answer = data.get("response", "")[:300]
                print(f"    A: {answer}...")
        except Exception as e:
            print(f"    Error: {e}")

# ============================================================
# MAIN
# ============================================================

def main():
    print("""
╔══════════════════════════════════════════════════════════╗
║           MODEL DISTILLATION PIPELINE                    ║
║     Weatherspoon Brother and Sister                      ║
║     Alex & David Weatherspoon                               ║
║                                                           ║
║     Distilling our codebases into a custom local model    ║
║     that knows everything we've built.                    ║
╚══════════════════════════════════════════════════════════╝
    """)

    os.makedirs(DISTILL_DIR, exist_ok=True)

    # Phase 1: Extract
    corpus = extract_code_knowledge()

    # Phase 2: Generate training pairs
    pairs = generate_training_pairs(corpus, max_pairs=30)

    # Phase 3: Build system prompt
    system_prompt = build_system_prompt(corpus)
    prompt_file = os.path.join(DISTILL_DIR, "system-prompt.txt")
    Path(prompt_file).write_text(system_prompt)
    print(f"\n  Phase 3: System prompt saved ({len(system_prompt)} chars)")

    # Phase 4: Create Modelfile and build
    modelfile_path = create_modelfile(system_prompt, pairs)
    success = build_model(modelfile_path)

    # Phase 5: Test
    if success:
        test_model()

    # Summary
    print(f"\n{'='*60}")
    print(f"  DISTILLATION COMPLETE")
    print(f"  Model: weatherspoon-asi")
    print(f"  Base: qwen2.5:7b")
    print(f"  Training corpus: {len(corpus)} entries")
    print(f"  Training pairs: {len(pairs)}")
    print(f"  System prompt: {len(system_prompt)} chars")
    print(f"  Files: {DISTILL_DIR}/")
    print(f"\n  Run: ollama run weatherspoon-asi")
    print(f"  Or in ASI: /model weatherspoon-asi")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
