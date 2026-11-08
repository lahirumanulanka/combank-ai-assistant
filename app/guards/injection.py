import re

from pydantic import BaseModel

PATTERNS: dict[str, list[str]] = {
    "instruction_override": [
        (r"\b(ignore|disregard|forget|override)\b.{0,30}\b(previous|prior|above|earlier|all|your)\b.{0,20}"
         r"\b(instructions?|rules?|prompts?|guidelines?)"),
        r"\byou are now\b",
        r"\b(maintenance|developer|debug|god) mode\b",
        r"\bsystem (notice|message|override)\b.{0,30}\b(ai|assistant|model)",
        r"\bpretend (to be|you are)\b",
    ],
    "data_exfiltration": [
        r"\b(reveal|print|show|repeat|output|leak|dump)\b.{0,40}\b(system prompt|instructions|hidden prompt)",
        r"\b(reveal|print|show|give|tell|list|send)\b.{0,30}\b(api|secret|private)[ _-]?keys?\b",
        r"\b(list|show|give)\b.{0,30}\b(all|every)\b.{0,30}\b(restricted|confidential|secret)\b",
        r"\baccess_level\b",
    ],
    "tool_abuse": [
        r"\b(call|run|execute|invoke|use)\b.{0,30}\badmin_\w+",
        r"\bfor (every|each|all) namespaces?\b",
        r"\b(delete|drop|wipe|purge)\b.{0,20}\b(all|every)\b",
    ],
}

COMPILED = {category: [re.compile(p, re.IGNORECASE | re.DOTALL) for p in patterns]
            for category, patterns in PATTERNS.items()}


class InjectionCheck(BaseModel):
    flagged: bool
    reasons: list[str]


def scan(text: str) -> InjectionCheck:
    reasons = [category for category, patterns in COMPILED.items() if any(p.search(text) for p in patterns)]
    return InjectionCheck(flagged=bool(reasons), reasons=reasons)


def guard_passages(passages: list[dict]) -> tuple[list[dict], list[str]]:
    kept, dropped = [], []
    for passage in passages:
        if scan(passage["text"]).flagged:
            dropped.append(passage["chunk_id"])
        else:
            kept.append(passage)
    return kept, dropped
