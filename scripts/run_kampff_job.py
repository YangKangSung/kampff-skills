#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kampff VS Code job runner — deterministic steps, not bare `hermes chat -q`.

Steps:
  1. Load request.json
  2. Ensure dataRoot layout (inbox/out/queue)
  3. Optional pre-harvest via operator collectors when present
  4. Hermes chat with skill + yolo + max-turns (agent must write analysis.json)
  5. Verify out/*-{id}-analysis.json exists (else fail)
  6. Render HTML via render_kampff_report.py when analysis present

Env:
  KAMPFF_DATA, KAMPFF_PEOPLE, KAMPFF_WIKI, KAMPFF_JOB_CONTROL, KAMPFF_* delays
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def die(msg: str, rc: int = 1) -> None:
    print(f"FATAL: {msg}", flush=True)
    raise SystemExit(rc)


def write_status(status_path: Path, **kw) -> None:
    data = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), **kw}
    status_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(data, ensure_ascii=True), flush=True)


def find_hermes(name: str) -> str:
    if name and Path(name).is_file():
        return name
    which = shutil.which(name) or shutil.which(name + ".exe")
    if which:
        return which
    local = os.environ.get("LOCALAPPDATA") or ""
    home = os.environ.get("USERPROFILE") or os.environ.get("HOME") or ""
    cands = [
        Path(local) / "hermes" / "hermes-agent" / "venv" / "Scripts" / "hermes.exe",
        Path(home) / "AppData" / "Local" / "hermes" / "hermes-agent" / "venv" / "Scripts" / "hermes.exe",
        Path(local) / "hermes" / "venvs" / "hermes" / "Scripts" / "hermes.exe",
        Path(home) / "AppData" / "Local" / "hermes" / "venvs" / "hermes" / "Scripts" / "hermes.exe",
        Path(local) / "hermes" / "bin" / "hermes.exe",
    ]
    for cand in cands:
        if cand.is_file():
            return str(cand)
    return name or "hermes"


def data_root() -> Path:
    """Prefer shared resolver; never require a fixed drive letter."""
    try:
        from kampff_paths import data_root as _shared

        return _shared()
    except Exception:
        pass
    env = (os.environ.get("KAMPFF_DATA") or "").strip()
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    sib = here.parent.parent / "kampff-data"
    sib.mkdir(parents=True, exist_ok=True)
    return sib


def skills_root() -> Path:
    env = (os.environ.get("KAMPFF_SKILLS") or "").strip()
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent


def find_skill_md() -> Path | None:
    """Resolve kampff SKILL.md: repo tree, then HERMES_HOME / LOCALAPPDATA hermes."""
    cands: list[Path] = []
    skills = skills_root()
    cands.append(skills / "kampff" / "SKILL.md")
    env_home = (os.environ.get("HERMES_HOME") or "").strip()
    local = os.environ.get("LOCALAPPDATA") or ""
    home = os.environ.get("USERPROFILE") or os.environ.get("HOME") or ""
    for base in filter(
        None,
        [
            env_home,
            str(Path(local) / "hermes") if local else "",
            str(Path(home) / "AppData" / "Local" / "hermes") if home else "",
        ],
    ):
        cands.append(Path(base) / "skills" / "kampff" / "SKILL.md")
    for c in cands:
        if c.is_file():
            return c
    return None


def skill_preload_block(max_chars: int = 14000) -> str:
    """Inline skill body — hermes -s kampff fails when name is ambiguous."""
    md = find_skill_md()
    if not md:
        print("WARN: kampff SKILL.md not found — running without skill body", flush=True)
        return (
            "## SKILL NOTE\n"
            "kampff SKILL.md not found on disk. Still write analysis.json to HARD DELIVERY path.\n"
        )
    body = md.read_text(encoding="utf-8", errors="replace")
    if len(body) > max_chars:
        body = body[:max_chars] + f"\n\n… truncated; full skill: {md}\n"
    print(f"skill preload: {md} ({len(body)} chars)", flush=True)
    return (
        f"## PRELOADED SKILL: kampff\n"
        f"Source: {md}\n"
        f"Hermes -s kampff is NOT used (Unknown skill / name collision on this host).\n"
        f"Follow this skill body.\n\n"
        f"{body}\n\n---\n"
    )


def ensure_layout(root: Path) -> None:
    for sub in ("inbox", "out", "queue", "raw"):
        (root / sub).mkdir(parents=True, exist_ok=True)


def find_analysis(out: Path, author_id: str, since_ts: float) -> Path | None:
    if not out.is_dir():
        return None
    id_l = author_id.lower()
    cands: list[Path] = []
    for p in out.glob("*-analysis.json"):
        try:
            if p.stat().st_mtime < since_ts - 30:
                # allow slightly older if name matches tightly
                pass
        except OSError:
            continue
        name = p.name.lower()
        if f"-{id_l}-analysis.json" in name or name == f"{id_l}-analysis.json":
            cands.append(p)
        elif id_l in name:
            cands.append(p)
    if not cands:
        return None
    cands.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    # prefer files touched after job start
    fresh = [p for p in cands if p.stat().st_mtime >= since_ts - 60]
    return (fresh or cands)[0]


def run(cmd: list[str], cwd: Path, log_path: Path | None = None) -> int:
    print("RUN:", " ".join(cmd), flush=True)
    print("CWD:", cwd, flush=True)
    try:
        if log_path:
            with log_path.open("w", encoding="utf-8", errors="replace") as lf:
                lf.write("CMD " + " ".join(cmd) + "\n\n")
                lf.flush()
                proc = subprocess.Popen(
                    cmd,
                    cwd=str(cwd),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                assert proc.stdout is not None
                for line in proc.stdout:
                    sys.stdout.write(line)
                    sys.stdout.flush()
                    lf.write(line)
                return int(proc.wait())
        return int(subprocess.call(cmd, cwd=str(cwd)))
    except FileNotFoundError as e:
        print(f"spawn fail: {e}", flush=True)
        return 127



def maybe_harvest(req: dict, root: Path, skills: Path) -> str | None:
    """Optional member harvest if scripts/harvest_*_member.py exists. Returns need_login or None."""
    platform = str(req.get("platform") or "")
    mode = str(req.get("mode") or "")
    parsed = req.get("parsed") or {}
    author = str(parsed.get("authorId") or req.get("input") or "").strip()
    nick = str(parsed.get("nick") or author).strip()
    day = str(req.get("date") or date.today().isoformat())
    if platform != "clien" or mode not in ("member", "auto", "") or not author:
        print("harvest skip: no matching member harvest platform", flush=True)
        return None
    # Prefer platform-named helper if present (often only on operator checkouts).
    script = skills / "scripts" / f"harvest_{platform}_member.py"
    if not script.is_file():
        script = skills / "scripts" / "harvest_member.py"
    if not script.is_file():
        print(f"harvest skip: no member harvest script for platform={platform}", flush=True)
        return None
    write_status_path = Path(
        str(Path(sys.argv[1])).replace("-request.json", "-runstatus.json")
    )
    harvest_log = Path(
        str(Path(sys.argv[1])).replace("-request.json", "-harvest.log")
    )
    write_status(
        write_status_path,
        phase="harvest",
        msg=f"member harvest {platform} {author}",
        activity=f"member harvest · {author}",
        current=author,
    )
    py = sys.executable
    rc = run([py, str(script), author, nick], cwd=skills, log_path=harvest_log)
    print(f"harvest rc={rc}", flush=True)

    log_txt = ""
    try:
        if harvest_log.is_file():
            log_txt = harvest_log.read_text(encoding="utf-8", errors="replace")
    except OSError:
        pass
    need_otp = "NEED_OTP" in log_txt
    login_ok = (
        "logged_in True" in log_txt
        or "로그인 OK" in log_txt
        or "사이트 계정 로그인 OK" in log_txt
    )
    hard_need_login = "NEED_LOGIN" in log_txt and not login_ok
    # stale SESSION.json logged_in=false must NOT override a successful harvest login
    need_login = need_otp or hard_need_login
    if need_login:
        msg = (
            "NEED_OTP: password ok — finish device/OTP in agent browser"
            if need_otp
            else "NEED_LOGIN: site session missing — register login or finish agent browser auth"
        )
        write_status(
            write_status_path,
            phase="error",
            msg=msg,
            activity="기기인증/OTP 필요" if need_otp else "로그인 필요",
            current=author,
            rc=3,
        )
        print(
            ("harvest NEED_OTP — " if need_otp else "harvest NEED_LOGIN — ")
            + "stop before hermes",
            flush=True,
        )
        return "need_otp" if need_otp else "need_login"
    if rc != 0:
        # e.g. HTTP 429 mid-harvest — keep partial inbox, continue to hermes
        print(
            f"harvest soft-fail rc={rc} login_ok={login_ok} — continuing to hermes",
            flush=True,
        )

    write_status(
        write_status_path,
        phase="harvest_done",
        msg=f"harvest rc={rc}",
        activity=f"수집 스크립트 종료 rc={rc}",
        current=author,
    )
    if rc != 0:
        print("harvest non-zero — continuing to hermes", flush=True)
    return None



def main() -> None:
    if len(sys.argv) < 3:
        die("usage: run_kampff_job.py <request.json> <prompt.txt> [hermes]")

    req_path = Path(sys.argv[1])
    prompt_path = Path(sys.argv[2])
    hermes_in = sys.argv[3] if len(sys.argv) > 3 else "hermes"
    status_path = Path(str(req_path).replace("-request.json", "-runstatus.json"))
    log_path = Path(str(req_path).replace("-request.json", "-hermes.log"))

    if not req_path.is_file():
        die(f"request missing: {req_path}")
    if not prompt_path.is_file():
        die(f"prompt missing: {prompt_path}")

    req = json.loads(req_path.read_text(encoding="utf-8"))
    root = data_root()
    skills = skills_root()
    os.environ["KAMPFF_DATA"] = str(root)
    ensure_layout(root)

    parsed = req.get("parsed") or {}
    author = str(
        parsed.get("authorId") or parsed.get("nick") or req.get("input") or "unknown"
    ).strip()
    day = str(req.get("date") or date.today().isoformat())
    out = root / "out"
    expected = out / f"{day}-{author}-analysis.json"

    print("=" * 60, flush=True)
    print("KAMPFF JOB pipeline", flush=True)
    print("request :", req_path, flush=True)
    print("dataRoot:", root, flush=True)
    print("skills  :", skills, flush=True)
    print("author  :", author, flush=True)
    print("expect  :", expected, flush=True)
    print("=" * 60, flush=True)

    t0 = time.time()
    write_status(status_path, phase="running", msg="pipeline start", dataRoot=str(root))

    # 1) harvest (best-effort; NEED_LOGIN is hard stop)
    try:
        harvest_err = maybe_harvest(req, root, skills)
    except Exception as e:
        print(f"harvest exception: {e}", flush=True)
        harvest_err = None
    if harvest_err in ("need_login", "need_otp"):
        otp = harvest_err == "need_otp"
        write_status(
            status_path,
            phase="error",
            msg=(
                "NEED_OTP: finish device/OTP in agent browser, then Go"
                if otp
                else "NEED_LOGIN: register site login in Kampff (or agent session), then retry"
            ),
            activity="기기인증/OTP 필요" if otp else "로그인 필요",
            current=author,
            rc=3,
        )
        die(
            (
                "NEED_OTP — finish device/OTP trust on agent browser, then Go"
                if otp
                else "NEED_LOGIN — register site username/password in Kampff, then Go again"
            ),
            rc=3,
        )

    # 2) hermes with skill + tools
    hermes = find_hermes(hermes_in)
    prompt = prompt_path.read_text(encoding="utf-8")
    skill_block = skill_preload_block()
    # Append hard delivery contract so agent cannot "chat only"
    prompt_extra = f"""

## HARD DELIVERY (machine-checked)
- You MUST create this file before finishing (absolute path):
  {expected}
- Also write HTML via: python scripts/render_kampff_report.py -a "{expected}" -o "{expected.with_name(expected.name.replace('-analysis.json', '-report.html'))}"
  (cwd = skills repo root) OR leave HTML to the runner if analysis exists.
- If harvest data exists under {root / 'inbox'}, USE it. Do not claim done without writing analysis.json.
- Reply with the absolute path of analysis.json on the last line.
"""
    full_prompt = skill_block + prompt + prompt_extra
    prompt_run = prompt_path.with_name(
        prompt_path.name.replace("-hermes-prompt.txt", "-hermes-prompt-run.txt")
    )
    prompt_run.write_text(full_prompt, encoding="utf-8")
    print(f"prompt chars: {len(full_prompt)} → {prompt_run}", flush=True)
    if len(full_prompt) > 28000:
        print(
            "WARN: prompt near Windows cmdline limit; consider shortening skill preload",
            flush=True,
        )

    write_status(
        status_path,
        phase="hermes",
        msg="hermes start (skill file brief, no -s)",
        activity=f"Hermes 분석 시작 · {author}",
        current=author,
        hermes=hermes,
        chars=len(full_prompt),
        expect=str(expected),
        skill=str(find_skill_md() or ""),
        prompt_run=str(prompt_run),
    )

    # Do NOT pass -s kampff (duplicate skill dirs → "Unknown skill(s): kampff").
    # Do NOT put full skill+prompt on -q (Windows CreateProcess cmdline ~32k).
    # Brief points Hermes at the on-disk prompt file (already written above).
    q = (
        f"You are a Kampff job worker. Read the FULL brief at this absolute path "
        f"and execute it end-to-end (tools allowed, yolo):\n"
        f"  {prompt_run}\n\n"
        f"HARD DELIVERY — create this file before finishing:\n"
        f"  {expected}\n"
        f"Use harvest under {root / 'inbox'} if present. "
        f"Last line of your reply = absolute path of analysis.json.\n"
        f"cwd for scripts: {skills}\n"
    )
    cmd = [
        hermes,
        "chat",
        "--cli",
        "-q",
        q,
        "--yolo",
        "-Q",
        "--max-turns",
        "90",
        "--source",
        "kampff-vscode",
        "--accept-hooks",
    ]
    rc = run(cmd, cwd=skills, log_path=log_path)
    write_status(
        status_path,
        phase="hermes_done",
        msg="hermes exited",
        rc=rc,
        hermes=hermes,
        log=str(log_path),
    )

    # 3) verify analysis
    found = find_analysis(out, author, t0)
    if not found and expected.is_file():
        found = expected

    # salvage: if hermes dumped JSON in log, try extract
    if not found and log_path.is_file():
        text = log_path.read_text(encoding="utf-8", errors="replace")
        # fenced json
        m = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", text)
        blob = m.group(1) if m else None
        if not blob:
            # last large { ... } with target-ish keys
            for m2 in re.finditer(r"(\{[\s\S]{200,}\})", text):
                cand = m2.group(1)
                if '"distance"' in cand or '"lenses"' in cand or '"subject"' in cand:
                    blob = cand
        if blob:
            try:
                data = json.loads(blob)
                expected.parent.mkdir(parents=True, exist_ok=True)
                expected.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                found = expected
                print(f"salvaged analysis from hermes log → {expected}", flush=True)
            except Exception as e:
                print(f"salvage parse fail: {e}", flush=True)

    if not found:
        write_status(
            status_path,
            phase="error",
            msg=f"no analysis.json under {out} for {author} after hermes rc={rc}",
            rc=2 if rc == 0 else rc,
            expect=str(expected),
            log=str(log_path),
        )
        die(
            f"Hermes finished (rc={rc}) but no analysis.json for '{author}'. "
            f"Expected {expected}. See {log_path}",
            rc=2 if rc == 0 else rc,
        )

    print(f"analysis OK: {found}", flush=True)

    # 4) render
    report = Path(str(found).replace("-analysis.json", "-report.html"))
    render = skills / "scripts" / "render_kampff_report.py"
    if render.is_file():
        write_status(status_path, phase="render", msg=f"render {report.name}")
        rrc = run(
            [sys.executable, str(render), "-a", str(found), "-o", str(report)],
            cwd=skills,
        )
        print(f"render rc={rrc} → {report if report.is_file() else 'MISSING'}", flush=True)
    else:
        print(f"render skip: no {render}", flush=True)

    write_status(
        status_path,
        phase="done",
        msg="pipeline complete",
        rc=0,
        analysis=str(found),
        report=str(report) if report.is_file() else None,
    )
    print("PIPELINE DONE", found, flush=True)
    raise SystemExit(0)


if __name__ == "__main__":
    main()
