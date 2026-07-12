# Third-party notices

This project is MIT-licensed. Optional integrations may pull in third-party tools.  
**Listing a tool here is not a dependency declaration** — install only if you use that path.

## soxoj/maigret (optional OSINT handle expansion)

| Field | Value |
|-------|--------|
| Project | [soxoj/maigret](https://github.com/soxoj/maigret) |
| Role in Kampff | Optional **collector pre-step**: username → public account map (aliases / candidate URLs). Not part of spectrograph analysis. |
| License | MIT |
| Copyright | Copyright (c) 2020-2026 Soxoj |
| Upstream license file | https://github.com/soxoj/maigret/blob/main/LICENSE |

### MIT License text (Maigret)

```
MIT License

Copyright (c) 2020-2026 Soxoj

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### Kampff usage notes

- **Do not vendor** Maigret source into this repo without keeping the notice above.
- Prefer **runtime install**: `pip install maigret` (or Docker `soxoj/maigret`).
- Wire-in points: `scripts/expand_handles_maigret.py`, `collectors/platforms/maigret.yaml`.
- Transitive deps of Maigret (e.g. socid_extractor and others) have **their own licenses** — re-check if you redistribute a frozen wheel/bundle.
- **Ethics:** lawful public surfaces only. Username collision is common — do not merge identities without independent evidence. Refuse stalking / harassment use cases (see `kampff/SKILL.md` hard rules).

## Adding more notices

When bundling or documenting another third-party tool:

1. Name, URL, role in Kampff
2. SPDX / license id + copyright line
3. Full license text if required by that license
4. Keep this file in distributions that ship those components
