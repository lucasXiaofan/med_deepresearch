"""Session management for agent_v2.

A session is a multi-interaction context. Think of it like a patient visit:
- Multiple agent runs happen within one session
- Agent can store notes that persist across runs
- All sessions live in one folder as JSON files
"""
import json
import uuid
import fcntl
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

# Default session directory
DEFAULT_SESSION_DIR = Path("./sessions")


class Session:
    """Manages session state with file locking for parallel safety.

    Each session has:
    - session_id: Unique identifier
    - context: What the session is about
    - store: List of dicts the agent has stored (append-only)
    - history: List of run summaries
    """

    def __init__(
        self,
        session_id: Optional[str] = None,
        session_dir: Optional[Path] = None,
        context: str = ""
    ):
        self.session_id = session_id or self._generate_id()
        self.session_dir = Path(session_dir) if session_dir else DEFAULT_SESSION_DIR
        self.session_dir.mkdir(parents=True, exist_ok=True)

        self.context = context
        self.store: List[Dict[str, Any]] = []  # Append-only list of dicts
        self.history: List[Dict[str, Any]] = []
        self.created_at: str = datetime.now().isoformat()
        self.updated_at: str = self.created_at

        self._load()

    def _generate_id(self) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        short_uuid = uuid.uuid4().hex[:8]
        return f"session_{timestamp}_{short_uuid}"

    @property
    def session_file(self) -> Path:
        return self.session_dir / f"{self.session_id}.json"

    def _load(self):
        """Load session from disk (with file locking)."""
        if not self.session_file.exists():
            return

        try:
            with open(self.session_file, "r", encoding="utf-8") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)  # Shared lock for reading
                try:
                    data = json.load(f)
                    self.context = data.get("context", self.context)
                    self.store = data.get("store", [])
                    self.history = data.get("history", [])
                    self.created_at = data.get("created_at", self.created_at)
                    self.updated_at = data.get("updated_at", self.updated_at)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except (json.JSONDecodeError, IOError):
            pass

    def save(self):
        """Persist session to disk (with file locking)."""
        self.updated_at = datetime.now().isoformat()
        data = {
            "session_id": self.session_id,
            "context": self.context,
            "store": self.store,
            "history": self.history,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

        # Write with exclusive lock
        with open(self.session_file, "w", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # Exclusive lock for writing
            try:
                json.dump(data, f, indent=2, ensure_ascii=False)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def append_store(self, data: Dict[str, Any]):
        """Append a dict to the session store.

        This is the only way to add data - append only, no delete/update.
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "data": data
        }
        self.store.append(entry)
        self.save()

    def add_run(self, run_summary: Dict[str, Any]):
        """Add a run summary to history."""
        run_summary["timestamp"] = datetime.now().isoformat()
        self.history.append(run_summary)
        self.save()

    def get_context_prompt(self) -> str:
        """Generate prompt snippet for agent to see session state."""
        parts = []

        if self.context:
            parts.append(f"## Session Context\n{self.context}")

        if self.store:
            # Show recent stored items (last 10)
            recent = self.store[-10:]
            store_text = json.dumps(recent, indent=2, ensure_ascii=False)
            parts.append(f"## Session Store (your saved notes)\n```json\n{store_text}\n```")

        if self.history:
            parts.append("## Previous Runs in This Session")
            for i, run in enumerate(self.history[-5:], 1):
                summary = run.get("output_summary", run.get("output", ""))[:200]
                parts.append(f"{i}. [{run.get('timestamp', '')}] {summary}...")

        if not parts:
            return ""

        return (
            "---\n"
            f"# SESSION: {self.session_id}\n\n"
            + "\n\n".join(parts)
            + "\n---\n"
        )


def list_sessions(session_dir: Path = None) -> List[Dict[str, Any]]:
    """List all sessions."""
    session_dir = Path(session_dir) if session_dir else DEFAULT_SESSION_DIR
    if not session_dir.exists():
        return []

    sessions = []
    for f in session_dir.glob("*.json"):
        try:
            with open(f, "r", encoding="utf-8") as file:
                data = json.load(file)
            sessions.append({
                "session_id": data.get("session_id", f.stem),
                "created_at": data.get("created_at", ""),
                "updated_at": data.get("updated_at", ""),
                "context": (data.get("context", "")[:100] + "...") if data.get("context") else "",
                "runs": len(data.get("history", [])),
                "store_items": len(data.get("store", []))
            })
        except (json.JSONDecodeError, IOError):
            continue

    return sorted(sessions, key=lambda x: x.get("updated_at", ""), reverse=True)
