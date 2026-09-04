"""Tableau de bord local, en lecture seule, du plan de travail Skull."""
from __future__ import annotations

import re
import sys
import threading
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template

PROJECT_DIR = Path(__file__).resolve().parent
TODO_PATH = PROJECT_DIR / "TODO.md"
CHECKBOX = re.compile(r"^\s*- \[([x~ ])\]\s+(.*)$", re.IGNORECASE)
PHASE = re.compile(r"^##\s+(.+?)\s*$")
app = Flask(__name__, template_folder="templates", static_folder="static")


def status_for(items: list[dict[str, str]]) -> str:
    states = {item["state"] for item in items}
    if not items:
        return "SANS TÂCHE"
    if states == {"done"}:
        return "VALIDÉ"
    if "partial" in states:
        return "PARTIEL"
    if "done" in states:
        return "EN COURS"
    return "À FAIRE"


def parse_todo(todo_path: Path = TODO_PATH) -> dict[str, Any]:
    """Relit TODO.md : aucune seconde liste de tâches à maintenir."""
    if not todo_path.is_file():
        raise FileNotFoundError(f"Plan introuvable : {todo_path}")
    phases: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in todo_path.read_text(encoding="utf-8").splitlines():
        heading = PHASE.match(line)
        if heading:
            current = {"title": heading.group(1), "items": []}
            phases.append(current)
            continue
        checkbox = CHECKBOX.match(line)
        if checkbox and current is not None:
            mark, label = checkbox.groups()
            current["items"].append({"label": label, "state": {"x": "done", "~": "partial", " ": "todo"}[mark.lower()]})
    phases = [phase for phase in phases if phase["items"]]
    counters = {"done": 0, "partial": 0, "todo": 0}
    for phase in phases:
        phase["status"] = status_for(phase["items"])
        phase["counts"] = {state: sum(item["state"] == state for item in phase["items"]) for state in counters}
        for state, amount in phase["counts"].items():
            counters[state] += amount
    total = sum(counters.values())
    progress = round(100 * (counters["done"] + 0.5 * counters["partial"]) / total) if total else 0
    return {
        "project": "SKULL // TABLEAU DE MISSION",
        "updated_at": datetime.fromtimestamp(todo_path.stat().st_mtime).astimezone().isoformat(),
        "served_at": datetime.now().astimezone().isoformat(),
        "progress": progress,
        "total": total,
        "counters": counters,
        "phases": phases,
    }


@app.get("/")
def dashboard() -> str:
    return render_template("tasks_dashboard.html")


@app.get("/api/tasks")
def tasks_api():
    try:
        return jsonify(parse_todo())
    except FileNotFoundError as error:
        return jsonify({"error": str(error)}), 503


if __name__ == "__main__":
    if "--open" in sys.argv:
        threading.Timer(0.6, lambda: webbrowser.open("http://127.0.0.1:5055")).start()
    app.run(host="127.0.0.1", port=5055, debug=False)
