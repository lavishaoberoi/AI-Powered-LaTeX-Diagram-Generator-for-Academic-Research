"""
In-memory + file-system diagram history manager.
Stores up to DIAGRAM_HISTORY_LIMIT versions per session.
"""
import json
import os
import uuid
from datetime import datetime
from pathlib import Path

HISTORY_LIMIT = int(os.getenv("DIAGRAM_HISTORY_LIMIT", "50"))
OUTPUT_FOLDER = os.getenv("OUTPUT_FOLDER", "outputs")

# Runtime store: {session_id: [DiagramRecord, ...]}
_store: dict[str, list[dict]] = {}


def _session_file(session_id: str) -> Path:
    p = Path(OUTPUT_FOLDER) / session_id
    p.mkdir(parents=True, exist_ok=True)
    return p / "history.json"


def _load_session(session_id: str) -> list[dict]:
    if session_id not in _store:
        sf = _session_file(session_id)
        if sf.exists():
            try:
                _store[session_id] = json.loads(sf.read_text(encoding="utf-8"))
            except Exception:
                _store[session_id] = []
        else:
            _store[session_id] = []
    return _store[session_id]


def _save_session(session_id: str) -> None:
    sf = _session_file(session_id)
    sf.write_text(
        json.dumps(_store[session_id], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def add_diagram(
    session_id: str,
    latex_code: str,
    explanation: str,
    diagram_type: str,
    pdf_path: str | None = None,
    png_path: str | None = None,
    prompt: str = "",
) -> dict:
    """Add a new diagram version to history. Returns the new record."""
    history = _load_session(session_id)
    record = {
        "id":           str(uuid.uuid4()),
        "version":      len(history) + 1,
        "timestamp":    datetime.utcnow().isoformat() + "Z",
        "prompt":       prompt,
        "diagram_type": diagram_type,
        "latex_code":   latex_code,
        "explanation":  explanation,
        "pdf_path":     pdf_path,
        "png_path":     png_path,
    }
    history.append(record)
    # Trim to limit
    if len(history) > HISTORY_LIMIT:
        _store[session_id] = history[-HISTORY_LIMIT:]
    _save_session(session_id)
    return record


def get_history(session_id: str) -> list[dict]:
    """Return all diagram records for a session (newest first)."""
    return list(reversed(_load_session(session_id)))


def get_diagram(session_id: str, diagram_id: str) -> dict | None:
    """Look up a specific diagram by its ID."""
    for rec in _load_session(session_id):
        if rec["id"] == diagram_id:
            return rec
    return None


def delete_diagram(session_id: str, diagram_id: str) -> bool:
    """Remove a single diagram from history. Returns True if deleted."""
    history = _load_session(session_id)
    new_history = [r for r in history if r["id"] != diagram_id]
    if len(new_history) < len(history):
        _store[session_id] = new_history
        _save_session(session_id)
        return True
    return False


def clear_history(session_id: str) -> None:
    """Wipe all history for a session."""
    _store[session_id] = []
    _save_session(session_id)
