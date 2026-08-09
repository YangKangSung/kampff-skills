# scripts/ — public inventory

Product scripts shared by **standalone** (CLI/agent) and optional **VS Code** shell.

| Script | Role |
|--------|------|
| `kampff_paths.py` | `KAMPFF_DATA` or repo-local `kampff-data/` |
| `render_kampff_report.py` | analysis.json → HTML (dual-track) |
| `kampff_report_easy.py` | easy-track helpers |
| `wiki_store.py` | prior merge + promote |
| `community_post.py` | draft tones |
| `run_kampff_job.py` | request → hermes → analysis → render |
| `expand_handles_maigret.py` | optional handle map (see THIRD_PARTY_NOTICES) |
| `thread_actor_analyze.py` | seed thread → reply graph |
| `human_browse.py` | polite browse helpers |

System map: [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md).

```bash
python scripts/render_kampff_report.py -a docs/sample-analysis.json -o /tmp/k.html
python scripts/wiki_store.py prior --id demo --platform reddit --prompt
```
