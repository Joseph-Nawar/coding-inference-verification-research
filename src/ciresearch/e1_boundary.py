"""Review structural input and receipt boundaries without printing payloads."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

def main(directory):
    run = Path(directory)
    lines = (run / "ledger.jsonl").read_text().splitlines()
    ledger = [json.loads(row) for row in lines]
    assert ledger[-1]["event"] in {"global_freeze", "stopped"}
    starts = [row for row in ledger if row["event"] == "call_started"]
    done = [row for row in ledger if row["event"] == "call_complete"]
    assert len({r["id"] for r in starts}) == len(starts) <= 320
    assert len({r["id"] for r in done}) == len(done) <= len(starts)
    assert sum(r["tokens"] for r in done) <= 245760
    assert all(1 <= r["tokens"] <= 768 for r in done)
    assert all(not r["environment"]["container_ids"] and not r["environment"]["active_models"]
               for r in ledger if r["event"] in {"start", "chunk_start", "chunk_checkpoint"})
    panels, requests, cleaned = Counter(), Counter(), 0
    for f in run.glob("chunk-*/*/requests.jsonl"):
        panel = f.parent.name.split("-")[-1]
        assert panel in {"base", "D", "plus", "H"}
        candidate = f.parent.name.split("-")[0]
        assert any(row["id"] == candidate for row in done)
        entries = [json.loads(line) for line in f.read_text().splitlines()]
        assert entries and set(entries[0]) == {"code", "entry"}
        assert all(set(row) == {"args", "seconds"} for row in entries[1:])
        panels[panel] += 1
        requests[panel] += len(entries)-1
        cleaned += (f.parent/"cleanup").is_file() and (f.parent/"cleanup").read_text() == "verified\n"
        assert (f.parent/"inspect.json").is_file()
    assert cleaned == sum(panels.values())
    for group in range(8):
        before = [k for k,event in enumerate(ledger) if event.get("chunk") == group]
        if before and any(ledger[i]["event"] == "chunk_checkpoint" for i in before):
            names = [ledger[i]["event"] for i in before]
            assert names == ["chunk_start", "chunk_bank_frozen", "chunk_decisions_frozen", "chunk_checkpoint"]
    print(json.dumps({
        "stage_status": ledger[-1]["event"],
        "started_calls": len(starts),
        "completed_calls": len(done),
        "candidate_panels": dict(panels),
        "case_requests": dict(requests),
        "cleanup_count": cleaned,
        "ledger_sha256": hashlib.sha256((run/"ledger.jsonl").read_bytes()).hexdigest(),
    },indent=2))


if __name__ == "__main__":
    main(sys.argv[1])
