from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Person:
    id: str
    aliases: list[str] = field(default_factory=list)
    display_name: str | None = None


@dataclass
class Target:
    platform: str
    url: str
    scope: str
    collect: list[str]
    match_people: list[str]
    auth_ref: str | None = None
    query: dict[str, Any] = field(default_factory=dict)
    playwright: dict[str, Any] = field(default_factory=dict)


@dataclass
class TextItem:
    content: str
    timestamp: str
    source: str
    platform: str
    type: str
    url: str | None = None
    collected_from: str | None = None
    thread_id: str | None = None
    source_file: str | None = None
    raw_author: str | None = None


@dataclass
class TargetsFile:
    batch_date: str | None
    viewer_id: str
    people: list[Person]
    targets: list[Target]
    meta: dict[str, Any] = field(default_factory=dict)