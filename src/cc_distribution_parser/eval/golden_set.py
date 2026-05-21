"""Golden-set loader.

Walks `data/golden_eval/`. Each `<name>.pdf` (or `.docx`) must be paired with
a `<name>.json` ground-truth file with schema:

    {
      "template_id": "ilpa-cc-v1",
      "doc_class": "capital_call",
      "ground_truth": { "gp_name": "Acme", ... }
    }

Empty corpus is acceptable in the doc-independent build — `run_eval` emits
"no docs" and returns an empty metrics dict (eval gate passes vacuously).
"""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GoldenDoc:
    name: str
    file_path: pathlib.Path
    template_id: str
    doc_class: str
    ground_truth: dict[str, Any]


def load_golden_set(root: pathlib.Path | None = None) -> list[GoldenDoc]:
    root = root or pathlib.Path("data/golden_eval")
    if not root.exists():
        return []
    docs: list[GoldenDoc] = []
    for json_path in sorted(root.glob("*.json")):
        gt = json.loads(json_path.read_text(encoding="utf-8"))
        stem = json_path.stem
        # locate the paired doc
        for ext in (".pdf", ".docx"):
            doc_path = json_path.with_name(stem + ext)
            if doc_path.exists():
                docs.append(
                    GoldenDoc(
                        name=stem,
                        file_path=doc_path,
                        template_id=gt.get("template_id", "unknown"),
                        doc_class=gt.get("doc_class", "unknown"),
                        ground_truth=gt.get("ground_truth", {}),
                    )
                )
                break
    return docs
