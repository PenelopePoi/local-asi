#!/usr/bin/env python3
"""
Teacher Anomaly Detector — Sentinel-Network method pointed at your own stack.

What it looks for in the knowledge base and skill-writes audit log:

  1. Score collapses        — an entry previously ≥8 gets overwritten at <6
  2. Topic clustering       — N+ entries in 24h with strong query overlap
  3. Off-hours skill writes — writes between 02:00–05:00 outside the nightly
                              auto-improve window (configurable)
  4. Non-kebab skill names  — should have been rejected server-side; flag
                              any that slipped in historically
  5. Size outliers          — skill content >= 25 KB (approaching server cap)
  6. Reserved-name attempts — entries named against the reserved list
                              (should be 0; anything here is a server-bypass
                              signal worth investigating)

Writes:
  ~/local-asi/.anomalies/anomaly-report-<timestamp>.json
  ~/local-asi/.anomalies/anomaly-report-<timestamp>.md   (human-readable)

Exit code:
  0 — no anomalies beyond noise threshold
  1 — one or more anomalies above threshold (useful for cron → notify)
  2 — scan failed (couldn't read inputs)
"""

import json
import os
import re
import sys
import datetime
from collections import Counter, defaultdict
from pathlib import Path

HOME = Path.home()
ASI_DIR = HOME / "local-asi"
KB_DIR = ASI_DIR / "knowledge"
AUDIT_LOG = KB_DIR / "skill-writes.jsonl"
OUT_DIR = ASI_DIR / ".anomalies"

RESERVED_NAMES = {
    "teacher-link", "teacher-ask", "teacher-search-knowledge",
    "teacher-status", "teacher-get-skill", "teacher-teach-session",
    "teacher-contribute-skill", "smart-tool-selector",
    "ethical-ai-doctrine", "guardian-doctrine", "sos-doctrine",
}

SKILL_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*[a-z0-9]$")

# Hours in which skill writes are expected (the nightly improve cron runs around 02:00).
# Flag writes at 03:00–05:00 that are NOT the cron.
QUIET_HOURS = {3, 4, 5}
IMPROVE_MARKERS = ("improve", "auto-improve", "nightly")


def load_kb_entries():
    for f in KB_DIR.glob("*.json"):
        if f.name == "graph.json":
            continue
        try:
            yield json.loads(f.read_text())
        except (OSError, json.JSONDecodeError) as e:
            print(f"WARN  could not read {f.name}: {e}", file=sys.stderr)


def load_audit_records():
    if not AUDIT_LOG.exists():
        return
    for line in AUDIT_LOG.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


STOPWORDS = frozenset("""
about above after again against all any and are because been before being below
between both but can did does doing down during each few for from further had has
have having here how into its itself just like more most only other our over
same she should some such than that the their them then there these they this
those through too under until very was were what when where which while who whom
why will with would your about theyre youre well just like some more than less
very really into this that was were have has been being also would could should
will thats just now very about which said say know see get make take give let
people things way really make made doing done didnt dont werent its lets heres
theres wasnt isnt arent youre theyre weve theyve youve were
""".split())


def tokenize(text: str):
    words = re.findall(r"[a-z]{4,}", text.lower())
    return set(w for w in words if w not in STOPWORDS and len(w) < 20)


def detect_score_collapses(entries):
    by_query = defaultdict(list)
    for e in entries:
        q = (e.get("query") or "").strip().lower()
        s = e.get("score")
        ts = e.get("timestamp")
        if q and isinstance(s, (int, float)) and ts:
            by_query[q].append({"score": float(s), "ts": ts, "id": e.get("id")})

    findings = []
    for q, versions in by_query.items():
        if len(versions) < 2:
            continue
        versions.sort(key=lambda v: v["ts"])
        peak = max(v["score"] for v in versions)
        latest = versions[-1]
        if peak >= 8.0 and latest["score"] < 6.0:
            findings.append({
                "query":      q[:120],
                "peak":       round(peak, 2),
                "latest":     round(latest["score"], 2),
                "latest_ts":  latest["ts"],
                "versions":   len(versions),
            })
    return findings


def detect_topic_clusters(entries, min_cluster=3, window_hours=24, min_overlap=3):
    now = datetime.datetime.now()
    recent = []
    for e in entries:
        try:
            ts = datetime.datetime.fromisoformat(e["timestamp"])
        except (KeyError, ValueError):
            continue
        if (now - ts).total_seconds() <= window_hours * 3600:
            tokens = tokenize(e.get("query", "") + " " + e.get("response", "")[:500])
            recent.append({"query": e.get("query", "")[:120], "tokens": tokens, "ts": e["timestamp"]})

    clusters = []
    seen = [False] * len(recent)
    for i, a in enumerate(recent):
        if seen[i]:
            continue
        cluster = [a]
        for j in range(i + 1, len(recent)):
            if seen[j]:
                continue
            if len(a["tokens"] & recent[j]["tokens"]) >= min_overlap:
                cluster.append(recent[j])
                seen[j] = True
        if len(cluster) >= min_cluster:
            shared = set.intersection(*(c["tokens"] for c in cluster))
            clusters.append({
                "size":         len(cluster),
                "window_hours": window_hours,
                "shared_terms": sorted(shared)[:10],
                "queries":      [c["query"] for c in cluster],
            })
    return clusters


def detect_offhours_writes(audit_records):
    findings = []
    for rec in audit_records:
        ts = rec.get("ts")
        if not ts:
            continue
        try:
            dt = datetime.datetime.fromisoformat(ts)
        except ValueError:
            continue
        if dt.hour not in QUIET_HOURS:
            continue
        # Heuristic: nightly improve is tagged in description or name
        desc = (rec.get("description") or "") + " " + (rec.get("name") or "")
        if any(marker in desc.lower() for marker in IMPROVE_MARKERS):
            continue
        findings.append({
            "ts":     ts,
            "hour":   dt.hour,
            "name":   rec.get("name"),
            "bytes":  rec.get("bytes"),
            "sha":    rec.get("sha256_16"),
            "author": rec.get("author"),
            "reason": rec.get("reason"),
        })
    return findings


def detect_invalid_names(audit_records):
    findings = []
    for rec in audit_records:
        name = rec.get("name") or ""
        if not name:
            continue
        if not SKILL_NAME_RE.match(name):
            findings.append({"name": name, "ts": rec.get("ts"), "path": rec.get("path")})
        if name in RESERVED_NAMES:
            findings.append({
                "name":      name,
                "ts":        rec.get("ts"),
                "path":      rec.get("path"),
                "reserved":  True,
                "note":      "reserved name that somehow bypassed the server blocklist",
            })
    return findings


def detect_size_outliers(audit_records, threshold_bytes=25_000):
    findings = []
    for rec in audit_records:
        bytes_ = rec.get("bytes") or 0
        if bytes_ >= threshold_bytes:
            findings.append({
                "name":  rec.get("name"),
                "ts":    rec.get("ts"),
                "bytes": bytes_,
            })
    return findings


def summarize(report: dict) -> str:
    lines = [
        "# Teacher Anomaly Report",
        f"Generated: {report['generated_utc']}",
        f"KB entries scanned: {report['counts']['kb_entries']}",
        f"Audit records scanned: {report['counts']['audit_records']}",
        "",
    ]
    total = sum(len(v) for v in report["findings"].values())
    lines.append(f"**Total findings: {total}**")
    lines.append("")

    def section(title, items, fmt):
        lines.append(f"## {title} — {len(items)}")
        if not items:
            lines.append("_clear_")
        else:
            for it in items[:20]:
                lines.append(fmt(it))
        lines.append("")

    section(
        "Score collapses",
        report["findings"]["score_collapses"],
        lambda x: f"- `{x['query']}` peak {x['peak']} → latest {x['latest']} ({x['versions']} versions)",
    )
    section(
        "Topic clusters (≥3 entries in 24h with shared terms)",
        report["findings"]["topic_clusters"],
        lambda x: f"- {x['size']} entries, shared: {', '.join(x['shared_terms'][:6])}",
    )
    section(
        "Off-hours skill writes (02–05 UTC, not nightly improve)",
        report["findings"]["offhours_writes"],
        lambda x: f"- {x['ts']} — {x['name']} ({x['bytes']} bytes) author={x.get('author') or '—'}",
    )
    section(
        "Invalid / reserved skill names",
        report["findings"]["invalid_names"],
        lambda x: f"- `{x['name']}` at {x['ts']}" + (" [RESERVED]" if x.get("reserved") else ""),
    )
    section(
        "Size outliers (≥25 KB)",
        report["findings"]["size_outliers"],
        lambda x: f"- {x['name']} {x['bytes']} bytes at {x['ts']}",
    )
    return "\n".join(lines)


def main():
    if not KB_DIR.exists():
        print(f"ERROR  knowledge dir not found: {KB_DIR}", file=sys.stderr)
        sys.exit(2)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

    kb = list(load_kb_entries())
    audit = list(load_audit_records())

    findings = {
        "score_collapses":  detect_score_collapses(kb),
        "topic_clusters":   detect_topic_clusters(kb),
        "offhours_writes":  detect_offhours_writes(audit),
        "invalid_names":    detect_invalid_names(audit),
        "size_outliers":    detect_size_outliers(audit),
    }

    report = {
        "generated_utc":  datetime.datetime.utcnow().isoformat() + "Z",
        "counts":         {"kb_entries": len(kb), "audit_records": len(audit)},
        "findings":       findings,
    }

    (OUT_DIR / f"anomaly-report-{stamp}.json").write_text(json.dumps(report, indent=2, default=str))
    (OUT_DIR / f"anomaly-report-{stamp}.md").write_text(summarize(report))

    total = sum(len(v) for v in findings.values())
    print(f"Anomaly scan complete. Findings: {total}")
    print(f"  JSON: {OUT_DIR / f'anomaly-report-{stamp}.json'}")
    print(f"  MD:   {OUT_DIR / f'anomaly-report-{stamp}.md'}")
    sys.exit(1 if total > 0 else 0)


if __name__ == "__main__":
    main()
