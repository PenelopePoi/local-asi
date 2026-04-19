#!/bin/bash
# auto-improve.sh — Perpetual self-improvement for weatherspoon-asi
# Runs nightly via cron. Each cycle:
# 1. Re-distills the model from latest codebases (picks up any new code/skills)
# 2. Runs the ASI self-improvement pass (re-processes weak knowledge entries)
# 3. Runs skill improvement cycle
# 4. Logs everything

set -uo pipefail

LOG_DIR="$HOME/automation/logs"
LOG="$LOG_DIR/asi-auto-improve-$(date +%Y-%m-%d).log"
mkdir -p "$LOG_DIR"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG"; }

log "=== WEATHERSPOON ASI AUTO-IMPROVE CYCLE ==="

# Phase 1: Re-distill model from latest code
log "Phase 1: Re-distilling weatherspoon-asi from latest codebases..."
cd "$HOME/local-asi"
python3 -c "
from distill import extract_code_knowledge, build_system_prompt, create_modelfile, build_model
import os
os.makedirs('distilled/training-data', exist_ok=True)
corpus = extract_code_knowledge()
system_prompt = build_system_prompt(corpus)
open('distilled/system-prompt.txt','w').write(system_prompt)
modelfile_path = create_modelfile(system_prompt, [])
build_model(modelfile_path)
print(f'Re-distilled from {len(corpus)} entries')
" >> "$LOG" 2>&1

if [ $? -eq 0 ]; then
    log "Phase 1: Model re-distilled successfully"
else
    log "Phase 1: FAILED - check log for errors"
fi

# Phase 2: ASI self-improvement (re-process worst knowledge entries)
log "Phase 2: ASI knowledge improvement..."
ENTRIES=$(python3 -c "
import json
from pathlib import Path
idx = Path('$HOME/local-asi/knowledge/index.json')
if idx.exists():
    data = json.loads(idx.read_text())
    print(len(data.get('entries', [])))
else:
    print(0)
" 2>/dev/null)

if [ "$ENTRIES" -gt 2 ]; then
    python3 -c "
import sys
sys.path.insert(0, '$HOME/local-asi')
from asi import ASISwarm, CONFIG, SelfImprover
CONFIG['model'] = 'weatherspoon-asi'
CONFIG['num_agents'] = 2
CONFIG['rounds'] = 1
swarm = ASISwarm()
improver = SelfImprover(swarm)
improver.improve_worst(3)
" >> "$LOG" 2>&1
    log "Phase 2: Re-processed 3 weakest knowledge entries"
else
    log "Phase 2: Skipped (only $ENTRIES entries, need 3+)"
fi

# Phase 3: Skill improvement cycle
log "Phase 3: Skill quality scan..."
BROKEN=$(for d in ~/.claude/skills/*/; do
    f="$d/SKILL.md"
    if [ -f "$f" ]; then
        head -20 "$f" | grep -q "^name:" || echo "broken"
    fi
done | wc -l | tr -d ' ')

TOTAL=$(ls -d ~/.claude/skills/*/ 2>/dev/null | wc -l | tr -d ' ')
SHORT=$(find ~/.claude/skills -name "SKILL.md" -size -500c 2>/dev/null | wc -l | tr -d ' ')

log "  Skills: $TOTAL total, $BROKEN broken frontmatter, $SHORT very short"

# Phase 4: Sync skill repo
log "Phase 4: Syncing skill repo..."
if [ -d "$HOME/claude-test/.git" ]; then
    cd "$HOME/claude-test"
    git pull origin claude/implement-computer-use-tool-hsc7F >> "$LOG" 2>&1
    # Sync new skills
    for skill_dir in skills/*/; do
        name=$(basename "$skill_dir")
        target="$HOME/.claude/skills/$name"
        mkdir -p "$target"
        [ -f "$skill_dir/README.md" ] && cp "$skill_dir/README.md" "$target/REFERENCE.md"
        for f in "$skill_dir"/*.py "$skill_dir"/*.js; do
            [ -f "$f" ] && cp "$f" "$target/"
        done
    done
    log "Phase 4: Repo synced"
else
    log "Phase 4: Skipped (repo not found)"
fi

# Phase 5: Health check
log "Phase 5: Health check..."
if [ -x "$HOME/.claude/skills/_automations/health-check.sh" ]; then
    bash "$HOME/.claude/skills/_automations/health-check.sh" --quiet >> "$LOG" 2>&1
fi

# Phase 6: Metrics
KNOWLEDGE_ENTRIES=$(python3 -c "
import json
from pathlib import Path
idx = Path('$HOME/local-asi/knowledge/index.json')
if idx.exists():
    data = json.loads(idx.read_text())
    entries = data.get('entries', [])
    avg = sum(e.get('score',0) for e in entries)/len(entries) if entries else 0
    print(f'{len(entries)} entries, avg score {avg:.1f}')
else:
    print('0 entries')
" 2>/dev/null)

# Append to improvement history
HISTORY="$HOME/local-asi/improvement-history.csv"
if [ ! -f "$HISTORY" ]; then
    echo "date,skills_total,skills_broken,skills_short,knowledge_entries,model_version" > "$HISTORY"
fi
echo "$(date +%Y-%m-%d),$TOTAL,$BROKEN,$SHORT,$KNOWLEDGE_ENTRIES,weatherspoon-asi" >> "$HISTORY"

log "=== CYCLE COMPLETE ==="
log "  Skills: $TOTAL total, $BROKEN broken, $SHORT short"
log "  Knowledge: $KNOWLEDGE_ENTRIES"
log "  Model: weatherspoon-asi (re-distilled)"
log "  Log: $LOG"
