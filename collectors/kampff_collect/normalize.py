from __future__ import annotations

from .models import Person, TextItem, TargetsFile


def author_matches(person: Person, raw_author: str | None) -> bool:
    if not raw_author:
        return False
    raw = raw_author.strip().lower()
    for alias in person.aliases:
        if alias.strip().lower() in raw or raw in alias.strip().lower():
            return True
    if person.display_name and person.display_name.strip().lower() in raw:
        return True
    return False


def assign_items(targets_file: TargetsFile, items: list[TextItem]) -> dict[str, list[TextItem]]:
    by_id: dict[str, list[TextItem]] = {p.id: [] for p in targets_file.people}
    people_by_id = {p.id: p for p in targets_file.people}

    for item in items:
        for pid, person in people_by_id.items():
            if author_matches(person, item.raw_author):
                by_id[pid].append(item)
                break

    return by_id


def to_bundle(targets_file: TargetsFile, assigned: dict[str, list[TextItem]]) -> dict:
    people = []
    for person in targets_file.people:
        texts = []
        for item in assigned.get(person.id, []):
            texts.append(
                {
                    "content": item.content,
                    "timestamp": item.timestamp,
                    "source": item.source,
                    "platform": item.platform,
                    "type": item.type,
                    "url": item.url,
                    "collected_from": item.collected_from,
                    "thread_id": item.thread_id,
                    "source_file": item.source_file,
                }
            )
        people.append(
            {
                "id": person.id,
                "display_name": person.display_name,
                "aliases": person.aliases,
                "texts": texts,
            }
        )

    return {
        "context": targets_file.meta.get("context", "mixed"),
        "viewer_id": targets_file.viewer_id,
        "batch_date": targets_file.batch_date,
        "people": people,
        "meta": targets_file.meta,
    }