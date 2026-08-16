/**
 * One-click job: queue → spawn Hermes (not fragile terminal PATH) → poll → UI progress.
 */
import { spawn, spawnSync, ChildProcessWithoutNullStreams } from "child_process";
import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";
import { AnalyzeRequest } from "./analyze";
import { getConfig } from "./config";
import {
  findLatestAnalysis,
  findLatestReport,
  openReportForTarget,
  renderReportForTarget,
  snapshotDepthTagged,
} from "./renderReport";
import { materializeSiteAuth } from "./sites";
import { promoteOutputsToWiki } from "./wikiStore";
import { kampffLog, showKampffLog } from "./log";

export type JobPhase =
  | "idle"
  | "queued"
  | "running"
  | "analysis"
  | "render"
  | "paused"
  | "cancelled"
  | "done"
  | "error";

export interface JobStep {
  id: string;
  label: string;
  hint?: string;
  state: "pending" | "active" | "done" | "error" | "skip";
}

export interface JobProgress {
  jobId: string;
  targetId: string;
  nick?: string;
  phase: JobPhase;
  steps: JobStep[];
  message: string;
  detail?: string;
  /** Short live action line (current post/board/search). */
  activity?: string;
  /** Concrete materials collected so far (posts, indexes…). */
  materials?: string[];
  humanPhase?: string;
  elapsedSec?: number;
  analysisPath?: string;
  reportPath?: string;
  promptPath?: string;
  queuePath?: string;
  wikiPromotePath?: string;
  startedAt: string;
  updatedAt: string;
  error?: string;
  pct: number;
  live?: boolean;
}

type Listener = (p: JobProgress) => void;

const listeners = new Set<Listener>();
let active: JobProgress | null = null;
let pollTimer: NodeJS.Timeout | undefined;
let childProc: ChildProcessWithoutNullStreams | undefined;
let statusItem: vscode.StatusBarItem | undefined;
let notifResolve: (() => void) | undefined;
let notifProgress:
  | vscode.Progress<{ message?: string; increment?: number }>
  | undefined;
let lastNotifPct = 0;
/** Phase before pause (so resume can restore). */
let phaseBeforePause: JobPhase | undefined;
let controlPath: string | undefined;
let pollCtx:
  | { targetId: string; req: AnalyzeRequest; t0: number; maxMs: number }
  | undefined;
/** Latest meaningful child stdout/stderr line for live UI. */
let lastChildActivity = "";

function log(msg: string): void {
  kampffLog(msg);
}

function noteChildActivity(line: string): void {
  const t = line.replace(/\s+/g, " ").trim();
  if (!t || t.length < 3) return;
  // skip pure noise / huge dumps
  if (t.length > 280) return;
  if (/^(=+|CMD |WARN:|prompt chars)/i.test(t)) return;
  // harvest / pipeline signals
  if (
    /^(writer |commenter |unique |harvest |hermes |DONE |BLOCKED|myInfo|logged_in|render |analysis |pipeline|KAMPFF |\[|\d+\/\d+|skip |FATAL|NEED_LOGIN|site )/i.test(
      t
    ) ||
    /posts_fetched|texts=|board\/|fetch |member harvest|skill preload|LIVE /i.test(
      t
    ) ||
    (t.startsWith("{") && /"phase"\s*:/.test(t))
  ) {
    if (t.startsWith("{") && /"phase"\s*:/.test(t)) {
      try {
        const j = JSON.parse(t) as {
          phase?: string;
          msg?: string;
          activity?: string;
          current?: string;
        };
        const bit =
          j.activity ||
          j.current ||
          (j.phase && j.msg ? `${j.phase}: ${j.msg}` : j.msg || j.phase || "");
        if (bit) lastChildActivity = String(bit).slice(0, 200);
        return;
      } catch {
        /* fall through */
      }
    }
    lastChildActivity = t.slice(0, 200);
  }
}

interface InboxLive {
  summary: string;
  items: string[];
  activity?: string;
  postCount: number;
  indexCount: number;
  textCount: number;
  boards: string[];
}

function findRawDir(dataRoot: string, targetId: string): string | null {
  const inbox = path.join(dataRoot, "inbox");
  if (!fs.existsSync(inbox) || !targetId) return null;
  const id = targetId.toLowerCase();
  let best: { p: string; m: number } | null = null;
  let days: string[] = [];
  try {
    days = fs.readdirSync(inbox);
  } catch {
    return null;
  }
  for (const day of days) {
    const rawRoot = path.join(inbox, day, "raw");
    if (!fs.existsSync(rawRoot)) continue;
    let kids: string[] = [];
    try {
      kids = fs.readdirSync(rawRoot);
    } catch {
      continue;
    }
    for (const kid of kids) {
      if (kid.toLowerCase() !== id) continue;
      const p = path.join(rawRoot, kid);
      try {
        const m = fs.statSync(p).mtimeMs;
        if (!best || m > best.m) best = { p, m };
      } catch {
        /* ignore */
      }
    }
  }
  return best?.p || null;
}

function scanInboxMaterials(targetId: string): InboxLive {
  const empty: InboxLive = {
    summary: "",
    items: [],
    postCount: 0,
    indexCount: 0,
    textCount: 0,
    boards: [],
  };
  const dataRoot = getConfig().dataRoot;
  if (!dataRoot || !targetId) return empty;
  const raw = findRawDir(dataRoot, targetId);
  if (!raw) return empty;

  const items: string[] = [];
  let activity: string | undefined;
  let postCount = 0;
  let indexCount = 0;
  let textCount = 0;
  const boardMap = new Map<string, number>();

  const livePath = path.join(raw, "LIVE.json");
  if (fs.existsSync(livePath)) {
    try {
      const live = JSON.parse(fs.readFileSync(livePath, "utf8")) as {
        activity?: string;
        current?: string;
        msg?: string;
        phase?: string;
        i?: number;
        n?: number;
        board?: string;
        sn?: string;
        title?: string;
        posts_fetched?: number;
        texts?: number;
      };
      const cur =
        live.activity ||
        live.current ||
        (live.board && live.sn
          ? `${live.board}/${live.sn}${live.title ? ` · ${live.title}` : ""}`
          : live.msg || "");
      if (cur) {
        activity =
          live.i != null && live.n != null
            ? `[${live.i}/${live.n}] ${cur}`
            : String(cur);
      }
      if (typeof live.posts_fetched === "number") postCount = live.posts_fetched;
      if (typeof live.texts === "number") textCount = live.texts;
    } catch {
      /* ignore */
    }
  }

  const postsDir = path.join(raw, "posts");
  if (fs.existsSync(postsDir)) {
    try {
      const files = fs
        .readdirSync(postsDir)
        .filter((f) => f.endsWith(".html"))
        .map((f) => {
          const fp = path.join(postsDir, f);
          let m = 0;
          try {
            m = fs.statSync(fp).mtimeMs;
          } catch {
            /* */
          }
          return { f, m };
        })
        .sort((a, b) => b.m - a.m);
      postCount = Math.max(postCount, files.length);
      for (const { f } of files) {
        const base = f.replace(/\.html$/i, "");
        const board = base.split("_")[0] || base;
        boardMap.set(board, (boardMap.get(board) || 0) + 1);
      }
      for (const { f } of files.slice(0, 6)) {
        items.push(`글 ${f.replace(/\.html$/i, "")}`);
      }
      if (files.length > 6) items.push(`…글 ${files.length - 6}개 더`);
    } catch {
      /* ignore */
    }
  }

  const idxDir = path.join(raw, "indexes");
  if (fs.existsSync(idxDir)) {
    try {
      const idxs = fs.readdirSync(idxDir).filter((f) => /\.(html|json)$/i.test(f));
      indexCount = idxs.length;
      if (idxs.length) items.push(`검색목록 ${idxs.length}개`);
    } catch {
      /* ignore */
    }
  }

  for (const name of ["texts.json", "texts_clean.json"]) {
    const tp = path.join(raw, name);
    if (!fs.existsSync(tp)) continue;
    try {
      const arr = JSON.parse(fs.readFileSync(tp, "utf8"));
      if (Array.isArray(arr)) {
        textCount = Math.max(textCount, arr.length);
        break;
      }
    } catch {
      /* ignore */
    }
  }

  const statePath = path.join(raw, "STATE.json");
  if (fs.existsSync(statePath)) {
    try {
      const st = JSON.parse(fs.readFileSync(statePath, "utf8")) as {
        posts_fetched?: number;
        texts?: number;
        writer?: number;
        commenter?: number;
      };
      if (typeof st.posts_fetched === "number")
        postCount = Math.max(postCount, st.posts_fetched);
      if (typeof st.texts === "number") textCount = Math.max(textCount, st.texts);
      if (st.writer || st.commenter) {
        items.unshift(
          `목록 글쓴이 ${st.writer || 0} · 댓글단 글 ${st.commenter || 0}`
        );
      }
    } catch {
      /* ignore */
    }
  }

  const boards = Array.from(boardMap.entries())
    .sort((a, b) => b[1] - a[1])
    .map(([b, n]) => `${b}×${n}`);

  const bits: string[] = [];
  if (postCount) bits.push(`글 HTML ${postCount}`);
  if (textCount) bits.push(`텍스트 ${textCount}`);
  if (indexCount) bits.push(`검색 ${indexCount}`);
  if (boards.length) bits.push(boards.slice(0, 4).join(" "));
  const summary = bits.join(" · ");

  return {
    summary,
    items: items.slice(0, 10),
    activity,
    postCount,
    indexCount,
    textCount,
    boards,
  };
}

function buildRunningDetail(
  runMsg: string,
  runPhase: string,
  inbox: InboxLive,
  elapsedSec: number
): { detail: string; activity: string; materials: string[]; human: string } {
  const activity =
    inbox.activity ||
    lastChildActivity ||
    (runMsg ? runMsg : "") ||
    "";
  const materials = [...inbox.items];
  if (inbox.summary && !materials.includes(inbox.summary)) {
    /* summary goes in detail head */
  }

  let human = "분석하는 중";
  if (runPhase === "harvest" || /^harvest/i.test(runMsg) || /writer |commenter |\[/.test(activity)) {
    human = "자료 수집";
  } else if (runPhase === "hermes" || runPhase === "running") {
    human = inbox.postCount > 0 || inbox.textCount > 0 ? "분석 엔진" : "수집·분석";
  } else if (runPhase === "render") {
    human = "보고서";
  }

  const lines: string[] = [];
  if (activity) lines.push(activity);
  else if (runMsg) lines.push(runMsg);
  if (inbox.summary) lines.push(`모음: ${inbox.summary}`);
  else if (!activity) {
    lines.push(
      elapsedSec < 20
        ? "시작 — 검색 목록·본문 수집 준비"
        : "아직 파일 안 쌓임 · 로그인/검색 대기일 수 있음"
    );
  }

  return {
    detail: lines.join("\n"),
    activity: activity || lines[0] || "",
    materials,
    human,
  };
}

export function onJobProgress(fn: Listener): vscode.Disposable {
  listeners.add(fn);
  if (active) fn(active);
  return new vscode.Disposable(() => listeners.delete(fn));
}

export function getActiveJob(): JobProgress | null {
  return active;
}

export function idleProgress(): JobProgress {
  return {
    jobId: "",
    targetId: "",
    phase: "idle",
    steps: stepsTemplate(),
    message: "대기 중",
    detail: "ID를 넣고 ① 분석 시작을 누르면 여기서 진행이 보입니다.",
    humanPhase: "준비",
    elapsedSec: 0,
    startedAt: "",
    updatedAt: new Date().toISOString(),
    pct: 0,
    live: false,
  };
}

function ensureStatus(): vscode.StatusBarItem {
  if (!statusItem) {
    statusItem = vscode.window.createStatusBarItem(
      vscode.StatusBarAlignment.Left,
      100
    );
    statusItem.command = "kampff.focusReportBuilder";
  }
  return statusItem;
}

function emit(p: JobProgress, opts?: { persist?: boolean }): void {
  active = p;
  for (const fn of Array.from(listeners)) {
    try {
      fn(p);
    } catch {
      /* ignore */
    }
  }
  // External progress watch must NOT rewrite progress.json — that refreshes
  // updatedAt forever and UI stays "분석 중" after the real job died.
  const persist = opts?.persist !== false;
  try {
    if (persist && p.queuePath) {
      const prog = p.queuePath.replace(/-request\.json$/i, "-progress.json");
      fs.writeFileSync(prog, JSON.stringify(p, null, 2), "utf8");
    }
  } catch (e) {
    log(`progress write fail: ${e}`);
  }

  const sb = ensureStatus();
  if (p.phase === "idle") {
    sb.hide();
  } else if (p.phase === "done") {
    sb.text = `$(pass-filled) Kampff 완료 · ${p.targetId}`;
    sb.tooltip = p.reportPath || p.message;
    sb.backgroundColor = undefined;
    sb.show();
    setTimeout(() => sb.hide(), 10000);
  } else if (p.phase === "cancelled") {
    sb.text = `$(circle-slash) Kampff 중단 · ${p.targetId}`;
    sb.tooltip = p.message || "사용자가 중단함";
    sb.backgroundColor = undefined;
    sb.show();
    setTimeout(() => sb.hide(), 8000);
  } else if (p.phase === "paused") {
    sb.text = `$(debug-pause) Kampff 일시정지 · ${p.targetId}`;
    sb.tooltip = p.detail || p.message;
    sb.backgroundColor = new vscode.ThemeColor(
      "statusBarItem.warningBackground"
    );
    sb.show();
  } else if (p.phase === "error") {
    sb.text = `$(error) Kampff 실패 · ${p.targetId}`;
    sb.tooltip = p.error || p.detail || p.message;
    sb.backgroundColor = new vscode.ThemeColor(
      "statusBarItem.errorBackground"
    );
    sb.show();
  } else {
    const el =
      p.elapsedSec != null ? ` · ${formatElapsed(p.elapsedSec)}` : "";
    sb.text = `$(sync~spin) Kampff ${p.pct}%${el} · ${p.targetId}`;
    sb.tooltip = [p.humanPhase, p.message, p.detail]
      .filter(Boolean)
      .join("\n");
    sb.backgroundColor = new vscode.ThemeColor(
      "statusBarItem.warningBackground"
    );
    sb.show();
  }

  if (notifProgress && p.phase !== "idle") {
    const inc = Math.max(0, p.pct - lastNotifPct);
    lastNotifPct = p.pct;
    notifProgress.report({
      message: `${p.humanPhase || p.message}${
        p.elapsedSec != null ? ` · ${formatElapsed(p.elapsedSec)}` : ""
      }${
        p.activity
          ? ` · ${p.activity}`
          : p.detail
            ? ` · ${String(p.detail).split('\n')[0]}`
            : ""
      }`,
      increment: inc > 0 ? inc : undefined,
    });
  }
  if ((p.phase === "done" || p.phase === "error" || p.phase === "cancelled") && notifResolve) {
    const r = notifResolve;
    notifResolve = undefined;
    notifProgress = undefined;
    lastNotifPct = 0;
    r();
  }
}

function formatElapsed(sec: number): string {
  const s = Math.max(0, Math.floor(sec));
  const m = Math.floor(s / 60);
  const r = s % 60;
  if (m <= 0) return `${r}초`;
  return `${m}분 ${r}초`;
}

function stepsTemplate(): JobStep[] {
  return [
    { id: "queue", label: "접수", hint: "작업 기록", state: "pending" },
    {
      id: "run",
      label: "분석 엔진",
      hint: "수집·추론 (시간 걸림)",
      state: "pending",
    },
    {
      id: "analysis",
      label: "dossier 데이터",
      hint: "analysis.json",
      state: "pending",
    },
    {
      id: "report",
      label: "HTML 보고서",
      hint: "그래프 dossier",
      state: "pending",
    },
    { id: "open", label: "열기", hint: "자동으로 보여 줌", state: "pending" },
  ];
}

function setStep(
  steps: JobStep[],
  id: string,
  state: JobStep["state"]
): JobStep[] {
  return steps.map((s) => (s.id === id ? { ...s, state } : s));
}

function humanPhase(phase: JobPhase): string {
  switch (phase) {
    case "queued":
      return "접수했어요";
    case "running":
      return "분석하는 중";
    case "analysis":
      return "결과 파일 확인";
    case "render":
      return "보고서 만드는 중";
    case "paused":
      return "일시정지";
    case "cancelled":
      return "중단됨";
    case "done":
      return "끝 · 보고서 준비됨";
    case "error":
      return "문제 발생";
    default:
      return "준비";
  }
}

function livePct(phase: JobPhase, elapsedSec: number): number {
  const base: Record<string, number> = {
    queued: 6,
    running: 18,
    analysis: 68,
    render: 86,
    paused: 0,
    cancelled: 100,
    done: 100,
    error: 100,
    idle: 0,
  };
  let p = base[phase] ?? 0;
  if (phase === "running") p = Math.min(55, 18 + elapsedSec * 0.05);
  else if (phase === "analysis") p = Math.min(84, 68 + elapsedSec * 0.02);
  else if (phase === "paused" && active) p = active.pct || 0;
  return Math.round(p);
}

function ensureDir(d: string): void {
  if (!fs.existsSync(d)) fs.mkdirSync(d, { recursive: true });
}

/** Resolve hermes executable — VS Code terminal PATH is often incomplete on Windows. */
export function resolveHermesCommand(configured: string): string {
  const home = process.env.USERPROFILE || process.env.HOME || "";
  const local = process.env.LOCALAPPDATA || "";
  const cfg = (configured || "").trim();
  const candidates = [
    cfg,
    cfg && !cfg.toLowerCase().endsWith(".exe") ? `${cfg}.exe` : "",
    // Current Hermes layout (this machine): %LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\
    path.join(local, "hermes", "hermes-agent", "venv", "Scripts", "hermes.exe"),
    path.join(home, "AppData", "Local", "hermes", "hermes-agent", "venv", "Scripts", "hermes.exe"),
    // Older / alternate layouts
    path.join(local, "hermes", "venvs", "hermes", "Scripts", "hermes.exe"),
    path.join(home, "AppData", "Local", "hermes", "venvs", "hermes", "Scripts", "hermes.exe"),
    path.join(local, "hermes", "bin", "hermes.exe"),
  ].filter((c) => !!c);

  for (const c of candidates) {
    try {
      if (fs.existsSync(c) && fs.statSync(c).isFile()) return c;
    } catch {
      /* ignore */
    }
  }
  return cfg || "hermes";
}

function resolvePython(configured: string): string {
  const c = (configured || "python").trim();
  if (path.isAbsolute(c) && fs.existsSync(c)) return c;
  const local = process.env.LOCALAPPDATA || "";
  const home = process.env.USERPROFILE || process.env.HOME || "";
  const candidates = [
    path.join(local, "hermes", "hermes-agent", "venv", "Scripts", "python.exe"),
    path.join(home, "AppData", "Local", "hermes", "hermes-agent", "venv", "Scripts", "python.exe"),
    path.join(local, "hermes", "venvs", "hermes", "Scripts", "python.exe"),
    path.join(home, "AppData", "Local", "hermes", "venvs", "hermes", "Scripts", "python.exe"),
  ];
  for (const p of candidates) {
    if (fs.existsSync(p)) return p;
  }
  return c || "python";
}

function writePipelineRunner(p: string): void {
  ensureDir(path.dirname(p));
  // Windows console default is often cp949 — never print raw unicode to stdout
  // without reconfigure; also keep banner ASCII-safe as belt-and-suspenders.
  fs.writeFileSync(
    p,
    `#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import json, os, shutil, subprocess, sys, time
from pathlib import Path

# Windows: avoid UnicodeEncodeError on cp949 consoles (VS Code Output pipe)
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

req_path = Path(sys.argv[1])
prompt_path = Path(sys.argv[2])
hermes_in = sys.argv[3] if len(sys.argv) > 3 else "hermes"
status_path = Path(str(req_path).replace("-request.json", "-runstatus.json"))

def write_status(**kw):
    data = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), **kw}
    status_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    # ASCII-safe console line (cp949-safe even without reconfigure)
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

hermes = find_hermes(hermes_in)
prompt = prompt_path.read_text(encoding="utf-8")
write_status(phase="running", msg="hermes start", hermes=hermes, chars=len(prompt))
print("=" * 60, flush=True)
print("KAMPFF JOB - running analysis", flush=True)
print("hermes :", hermes, flush=True)
print("prompt :", str(prompt_path), flush=True)
print("chars  :", len(prompt), flush=True)
print("=" * 60, flush=True)
# --cli: override display.interface=tui (no-TTY spawn otherwise exits 0 idle)
cmd = [
    hermes, "chat", "--cli", "-q", prompt,
    "--yolo", "-Q",
    "--max-turns", "90",
    "--source", "kampff-vscode",
    "--accept-hooks",
]
# note: do not pass -s kampff — duplicate skill name → Unknown skill(s) on this host
try:
    rc = subprocess.call(cmd)
except FileNotFoundError as e:
    write_status(phase="error", msg=f"hermes not found: {hermes} ({e})", rc=127)
    raise SystemExit(127)
write_status(phase="hermes_done", msg="hermes exited", rc=rc, hermes=hermes)
raise SystemExit(rc)
`,
    "utf8"
  );
}

export async function startJobFromRequest(
  req: AnalyzeRequest
): Promise<JobProgress> {
  stopPollingOnly();
  if (childProc) {
    killProcessTree(childProc);
    childProc = undefined;
  }
  phaseBeforePause = undefined;

  const targetId = (
    req.parsed.authorId ||
    req.parsed.handle ||
    (req.input || "").trim().replace(/^@/, "").split(/[\s|,]+/)[0] ||
    req.parsed.nick ||
    "unknown"
  )
    .trim()
    .replace(/^@/, "");
  const nick = (req.parsed.nick || "").trim() || undefined;
  const startedAt = new Date().toISOString();
  let steps = stepsTemplate();
  steps = setStep(steps, "queue", "done");
  steps = setStep(steps, "run", "active");

  controlPath = req.queuePath.replace(/-request\.json$/i, "-control.json");
  writeControl("run");

  const progress: JobProgress = {
    jobId: path.basename(req.queuePath).replace(/-request\.json$/i, ""),
    targetId,
    nick,
    phase: "running",
    steps,
    message:
      nick && nick !== targetId
        ? `${nick} (${targetId}) 분석을 시작했어요`
        : `${targetId} 분석을 시작했어요`,
    detail:
      "엔진을 띄우는 중… 출력은 보기 → 출력 → Kampff. 일시정지/중단은 진행 카드 버튼.",
    humanPhase: humanPhase("running"),
    elapsedSec: 0,
    promptPath: req.promptPath,
    queuePath: req.queuePath,
    startedAt,
    updatedAt: startedAt,
    pct: 12,
    live: true,
  };
  emit(progress);
  lastChildActivity = "";
  log(`JOB START target=${targetId} queue=${req.queuePath}`);
  showKampffLog(true);

  lastNotifPct = 0;
  void vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: `Kampff · ${nick || targetId}`,
      cancellable: true,
    },
    async (progressNotif, token) => {
      notifProgress = progressNotif;
      progressNotif.report({
        message: "분석을 시작했어요 · 취소 가능",
        increment: 10,
      });
      token.onCancellationRequested(() => {
        cancelActiveJob("notification");
      });
      await new Promise<void>((resolve) => {
        notifResolve = resolve;
        setTimeout(() => {
          if (notifResolve === resolve) {
            notifResolve = undefined;
            notifProgress = undefined;
            resolve();
          }
        }, 50 * 60 * 1000);
      });
    }
  );

  const cfg = getConfig();
  // Prefer skills checkout from settings / env (no host-hardcoded path).
  const skillsCandidates = [
    cfg.skillsDevRoot || "",
    process.env.KAMPFF_SKILLS || "",
  ].filter(Boolean);

  let skillsRunner = "";
  for (const root of skillsCandidates) {
    const cand = path.join(root, "scripts", "run_kampff_job.py");
    if (fs.existsSync(cand)) {
      skillsRunner = cand;
      break;
    }
  }
  const queueRunner = path.join(cfg.dataRoot, "queue", "_run_kampff_job.py");
  // Prefer skills pipeline (harvest → hermes --cli, skill inlined → render).
  // Fallback: thin queue copy for hosts without skills checkout.
  let runner = skillsRunner;
  if (skillsRunner) {
    log(`runner=skills ${skillsRunner}`);
  } else {
    writePipelineRunner(queueRunner);
    runner = queueRunner;
    log(`runner=queue-fallback ${queueRunner}`);
  }

  const hermes = resolveHermesCommand(cfg.hermesCommand || "hermes");
  const py = resolvePython(cfg.pythonPath || "python");
  log(`python=${py}`);
  log(`hermes=${hermes}`);
  log(`control=${controlPath}`);

  if (!fs.existsSync(req.promptPath)) {
    fail(progress, `prompt 파일 없음: ${req.promptPath}`);
    return active!;
  }

  // cwd must be skills-dev root so harvest/render relative paths work
  const cwd = skillsRunner
    ? path.dirname(path.dirname(skillsRunner))
    : cfg.skillsDevRoot || cfg.dataRoot || process.cwd();
  const delayMin = String(Math.round((cfg.harvestDelayMinSec ?? 2.8) * 1000));
    const delayMax = String(Math.round((cfg.harvestDelayMaxSec ?? 6.5) * 1000));
    let siteAuthPath = "";
    try {
      const sid = req.siteId || (req.site && req.site.id) || "";
      if (sid && cfg.dataRoot) {
        siteAuthPath = (await materializeSiteAuth(sid, cfg.dataRoot)) || "";
        if (siteAuthPath) log(`siteAuth=${siteAuthPath} (password not logged)`);
      }
    } catch (e) {
      log(
        `siteAuth skip: ${e instanceof Error ? e.message : String(e)}`
      );
    }
    try {
      childProc = spawn(
        py,
        [runner, req.queuePath, req.promptPath, hermes],
        {
          cwd,
          env: {
            ...process.env,
            PYTHONIOENCODING: "utf-8",
            PYTHONUTF8: "1",
            HERMES_ACCEPT_HOOKS: "1",
            KAMPFF_DATA: cfg.dataRoot || process.env.KAMPFF_DATA || "",
            KAMPFF_PEOPLE:
              cfg.peopleRoot || process.env.KAMPFF_PEOPLE || "",
            KAMPFF_WIKI: cfg.wikiRoot || process.env.KAMPFF_WIKI || "",
            KAMPFF_SKILLS:
              (skillsRunner
                ? path.dirname(path.dirname(skillsRunner))
                : cfg.skillsDevRoot) ||
              process.env.KAMPFF_SKILLS ||
              "",
            KAMPFF_LANG: cfg.uiLanguage || process.env.KAMPFF_LANG || "en",
            KAMPFF_JOB_CONTROL: controlPath || "",
            KAMPFF_HARVEST_POLITE: cfg.harvestPolite === false ? "0" : "1",
            KAMPFF_CLIEN_MIN_DELAY_MS: delayMin,
            KAMPFF_CLIEN_MAX_DELAY_MS: delayMax,
            KAMPFF_HARVEST_MIN_DELAY_MS: delayMin,
            KAMPFF_HARVEST_MAX_DELAY_MS: delayMax,
            KAMPFF_CLIEN_MAX_FETCH: String(cfg.harvestMaxFetch ?? 40),
            KAMPFF_CLIEN_BURST_EVERY: String(cfg.harvestBurstEvery ?? 6),
            KAMPFF_CLIEN_BURST_PAUSE_MS: String(
              Math.round((cfg.harvestBurstPauseSec ?? 10) * 1000)
            ),
            KAMPFF_SITE_ID: req.siteId || req.site?.id || "",
            KAMPFF_SITE_BASE_URL: req.site?.baseUrl || "",
            KAMPFF_SITE_LOGIN_URL: req.site?.loginUrl || "",
            KAMPFF_SITE_USER: req.site?.username || "",
            KAMPFF_SITE_KIND: req.site?.kind || "",
            KAMPFF_SITE_AUTH_FILE: siteAuthPath,
          },
          windowsHide: true,
          // Unix: new process group so cancel can signal -pid (wrapper + hermes tree).
          // Windows: taskkill /T covers the tree; detached changes session semantics — skip.
          detached: process.platform !== "win32",
        }
      );
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    fail(progress, `프로세스 시작 실패: ${msg}`);
    void vscode.window.showErrorMessage(`Kampff: ${msg}`);
    return active!;
  }

  childProc.stdout.on("data", (buf: Buffer) => {
    const t = buf.toString("utf8");
    for (const line of t.split('\n')) {
      const s = line.split('\r').join("").trim();
      if (s) {
        log(s);
        noteChildActivity(s);
      }
    }
  });
  childProc.stderr.on("data", (buf: Buffer) => {
    const t = buf.toString("utf8");
    for (const line of t.split('\n')) {
      const s = line.split('\r').join("").trim();
      if (s) {
        log(`ERR ${s}`);
        noteChildActivity(s);
      }
    }
  });
  childProc.on("error", (err) => {
    log(`spawn error: ${err.message}`);
    fail(active || progress, `실행 오류: ${err.message}`);
    void vscode.window.showErrorMessage(`Kampff: ${err.message}`);
  });
  childProc.on("close", (code) => {
    log(`process exit code=${code}`);
    // poller will pick analysis or error
  });

  emit({
    ...progress,
    detail:
      "엔진 실행 중 (python spawn)\n" +
      `hermes: ${hermes}\n` +
      "출력: Kampff 채널\n일시정지/중단 가능",
    pct: 18,
    updatedAt: new Date().toISOString(),
  });

  startPoll(targetId, req);
  return active!;
}

function stopPollingOnly(): void {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = undefined;
  }
}

function writeControl(action: "run" | "pause" | "cancel"): void {
  if (!controlPath) return;
  try {
    ensureDir(path.dirname(controlPath));
    fs.writeFileSync(
      controlPath,
      JSON.stringify(
        {
          action,
          ts: new Date().toISOString(),
          pid: childProc?.pid ?? null,
          targetId: active?.targetId ?? null,
        },
        null,
        2
      ),
      "utf8"
    );
  } catch (e) {
    log(`control write fail: ${e}`);
  }
}

/** Kill entire process tree (Windows taskkill /T; else SIGTERM). */
function killProcessTree(proc?: ChildProcessWithoutNullStreams): void {
  if (!proc || proc.killed) return;
  const pid = proc.pid;
  if (!pid) {
    try {
      proc.kill();
    } catch {
      /* ignore */
    }
    return;
  }
  try {
    if (process.platform === "win32") {
      spawnSync("taskkill", ["/PID", String(pid), "/T", "/F"], {
        windowsHide: true,
        timeout: 15000,
      });
    } else {
      // Negative PID = process group (requires spawn detached on non-win).
      try {
        process.kill(-pid, "SIGTERM");
      } catch {
        try {
          process.kill(pid, "SIGTERM");
        } catch {
          proc.kill("SIGTERM");
        }
      }
    }
  } catch (e) {
    log(`kill tree fail: ${e}`);
    try {
      proc.kill();
    } catch {
      /* ignore */
    }
  }
}

/**
 * Suspend/resume process tree. Windows: NtSuspendProcess via PowerShell.
 * Unix: SIGSTOP / SIGCONT on the group when possible.
 */
function setProcessTreeSuspended(pid: number, suspend: boolean): boolean {
  try {
    if (process.platform === "win32") {
      const mode = suspend ? "suspend" : "resume";
      const ps = `
$ErrorActionPreference = 'SilentlyContinue'
$root = ${pid}
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class KampffNt {
  [DllImport("ntdll.dll")] public static extern uint NtSuspendProcess(IntPtr p);
  [DllImport("ntdll.dll")] public static extern uint NtResumeProcess(IntPtr p);
  [DllImport("kernel32.dll", SetLastError=true)] public static extern IntPtr OpenProcess(uint a, bool b, int pid);
  [DllImport("kernel32.dll", SetLastError=true)] public static extern bool CloseHandle(IntPtr h);
}
"@
function Get-DescendantIds([int]$id) {
  $out = New-Object System.Collections.Generic.List[int]
  $out.Add($id) | Out-Null
  Get-CimInstance Win32_Process | ForEach-Object {
    if ($_.ParentProcessId -eq $id) {
      foreach ($c in (Get-DescendantIds $_.ProcessId)) { $out.Add($c) | Out-Null }
    }
  }
  return $out
}
$ids = Get-DescendantIds $root | Select-Object -Unique
foreach ($id in $ids) {
  $h = [KampffNt]::OpenProcess(0x800, $false, $id)
  if ($h -ne [IntPtr]::Zero) {
    if ('${mode}' -eq 'suspend') { [void][KampffNt]::NtSuspendProcess($h) }
    else { [void][KampffNt]::NtResumeProcess($h) }
    [void][KampffNt]::CloseHandle($h)
  }
}
Write-Output ("ok " + ($ids -join ','))
`;
      const r = spawnSync(
        "powershell.exe",
        ["-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
        { windowsHide: true, timeout: 20000, encoding: "utf8" }
      );
      log(
        `${mode} pid=${pid} status=${r.status} out=${(r.stdout || "").toString().trim()}`
      );
      return r.status === 0;
    }
    // Unix: stop/cont the child; best-effort on group
    try {
      process.kill(-pid, suspend ? "SIGSTOP" : "SIGCONT");
    } catch {
      process.kill(pid, suspend ? "SIGSTOP" : "SIGCONT");
    }
    return true;
  } catch (e) {
    log(`suspend/resume fail: ${e}`);
    return false;
  }
}

export function isJobCancellable(): boolean {
  if (!active) return false;
  return (
    active.live === true ||
    active.phase === "running" ||
    active.phase === "analysis" ||
    active.phase === "render" ||
    active.phase === "queued" ||
    active.phase === "paused"
  );
}

/** One control: running → pause, paused → resume. */
export function togglePauseJob(): JobProgress | null {
  if (active?.phase === "paused") return resumeActiveJob();
  return pauseActiveJob();
}

export function pauseActiveJob(): JobProgress | null {
  if (!active || !isJobCancellable()) return active;
  if (active.phase === "paused") return active;
  if (active.phase === "done" || active.phase === "error" || active.phase === "cancelled") {
    return active;
  }

  const pid = childProc?.pid;
  // Nothing to freeze → don't leave zombie "paused" that confuses the card
  if (!isInternalJobLive() || !pid) {
    log(`JOB PAUSE→CANCEL no live process target=${active.targetId} pid=${pid ?? "none"}`);
    return cancelActiveJob("pause-no-process");
  }

  phaseBeforePause = active.phase;
  stopPollingOnly();
  writeControl("pause");

  const suspended = setProcessTreeSuspended(pid, true);

  if (!suspended) {
    log(`JOB PAUSE suspend failed → cancel target=${active.targetId} pid=${pid}`);
    return cancelActiveJob("pause-suspend-failed");
  }

  emit({
    ...active,
    phase: "paused",
    live: false,
    humanPhase: humanPhase("paused"),
    message: "일시정지. 다시 누르면 재개.",
    detail: "토글 = 재개 · 중단 = kill (재개 불가)",
    updatedAt: new Date().toISOString(),
  });
  log(`JOB PAUSE target=${active.targetId} suspended=true pid=${pid}`);
  void vscode.window.setStatusBarMessage("Kampff: 일시정지", 2500);
  return active;
}

export function resumeActiveJob(): JobProgress | null {
  if (!active || active.phase !== "paused") return active;

  const pid = childProc?.pid;
  // Dead child after pause → cancel (don't flip to running+live ghost)
  if (!isInternalJobLive() || !pid) {
    log(
      `JOB RESUME→CANCEL no live process target=${active.targetId} pid=${pid ?? "none"}`
    );
    return cancelActiveJob("resume-no-process");
  }

  writeControl("run");
  const resumed = setProcessTreeSuspended(pid, false);
  if (!resumed) {
    log(`JOB RESUME suspend-off failed → cancel target=${active.targetId} pid=${pid}`);
    return cancelActiveJob("resume-failed");
  }

  const back =
    phaseBeforePause &&
    phaseBeforePause !== "paused" &&
    phaseBeforePause !== "cancelled"
      ? phaseBeforePause
      : "running";
  phaseBeforePause = undefined;

  emit({
    ...active,
    phase: back,
    live: true,
    humanPhase: humanPhase(back),
    message: "다시 진행합니다.",
    detail: "폴링 재개 · polite · rate-limit 주의",
    updatedAt: new Date().toISOString(),
  });
  log(`JOB RESUME target=${active.targetId} resumed=true phase=${back} pid=${pid}`);

  if (pollCtx) {
    startPoll(pollCtx.targetId, pollCtx.req, pollCtx.t0, pollCtx.maxMs);
  }
  return active;
}

export function cancelActiveJob(reason = "user"): JobProgress | null {
  if (!active && !childProc) return null;

  writeControl("cancel");
  stopPollingOnly();

  // If suspended, still kill
  if (childProc?.pid) {
    try {
      setProcessTreeSuspended(childProc.pid, false);
    } catch {
      /* ignore */
    }
  }
  killProcessTree(childProc);
  childProc = undefined;
  phaseBeforePause = undefined;
  pollCtx = undefined;

  const base = active || idleProgress();
  const now = new Date().toISOString();
  let steps = (base.steps || stepsTemplate()).map((s) =>
    s.state === "active" ? { ...s, state: "skip" as const } : s
  );

  emit({
    ...base,
    phase: "cancelled",
    live: false,
    steps,
    pct: base.pct || 0,
    humanPhase: humanPhase("cancelled"),
    message: "분석을 중단했습니다.",
    detail:
      reason === "notification"
        ? "알림에서 취소함"
        : "사용자 중단 · 프로세스를 종료했습니다. 이미 받은 raw는 남겨 둡니다.",
    error: undefined,
    updatedAt: now,
  });
  log(`JOB CANCEL reason=${reason} target=${base.targetId}`);
  void vscode.window.showInformationMessage(
    `Kampff: 중단 · ${base.targetId || "job"}`
  );
  return active;
}

export function cancelJobWatch(): void {
  cancelActiveJob("watch");
}

function startPoll(
  targetId: string,
  req: AnalyzeRequest,
  t0 = Date.now(),
  maxMs = 45 * 60 * 1000
): void {
  stopPollingOnly();
  pollCtx = { targetId, req, t0, maxMs };
  pollTimer = setInterval(() => {
    void tick(targetId, req, t0, maxMs);
  }, 1500);
  void tick(targetId, req, t0, maxMs);
}

async function tick(
  targetId: string,
  req: AnalyzeRequest,
  t0: number,
  maxMs: number
): Promise<void> {
  if (!active || active.targetId !== targetId) return;
  if (
    active.phase === "done" ||
    active.phase === "error" ||
    active.phase === "cancelled" ||
    active.phase === "paused"
  ) {
    if (active.phase !== "paused") stopPollingOnly();
    return;
  }

  const elapsedSec = (Date.now() - t0) / 1000;
  if (Date.now() - t0 > maxMs) {
    fail(
      active,
      "시간이 너무 오래 걸렸어요. 출력 채널 Kampff 로그를 확인해 주세요."
    );
    return;
  }

  const cfg = getConfig();
  let steps = active.steps.map((s) => ({ ...s }));
  let phase: JobPhase = active.phase;
  let message = active.message;
  let detail = active.detail;
  let analysisPath = active.analysisPath;
  let reportPath = active.reportPath;

  const runStatusPath = req.queuePath.replace(
    /-request\.json$/i,
    "-runstatus.json"
  );
  let hermesRc: number | undefined;
  let runPhase = "";
  let runMsg = "";
  let liveActivity = "";
  let liveMaterials: string[] = [];
  let liveHuman = "";
  if (fs.existsSync(runStatusPath)) {
    try {
      const st = JSON.parse(fs.readFileSync(runStatusPath, "utf8")) as {
        phase?: string;
        rc?: number;
        msg?: string;
        hermes?: string;
        activity?: string;
        current?: string;
      };
      runPhase = String(st.phase || "");
      if (st.phase === "error") {
        fail(active, st.msg || "분석 엔진을 시작하지 못했어요");
        return;
      }
      if (typeof st.rc === "number") hermesRc = st.rc;
      if (st.msg) runMsg = String(st.msg);
      if (st.activity || st.current) {
        lastChildActivity = String(st.activity || st.current).slice(0, 200);
      }
      if (st.hermes && elapsedSec < 5 && !runMsg) {
        detail = `hermes: ${st.hermes}`;
      }
    } catch {
      /* ignore */
    }
  }

  const aPath = findLatestAnalysis(targetId);
  if (aPath) {
    // only accept analysis newer than job start (60s skew for clock noise)
    try {
      const mt = fs.statSync(aPath).mtimeMs;
      const startMs = Date.parse(active.startedAt) - 60_000;
      if (Number.isFinite(startMs) && mt >= startMs) {
        analysisPath = aPath;
      } else if (hermesRc === 0) {
        // hermes finished successfully — reuse prior analysis if no fresher one
        analysisPath = aPath;
      }
      // else: keep waiting for a new analysis from this job
    } catch {
      /* ignore stale path */
    }
  }

  if (analysisPath) {
    steps = setStep(steps, "run", "done");
    steps = setStep(steps, "analysis", "done");
    if (phase === "running" || phase === "queued") {
      phase = "analysis";
      message = "dossier 데이터가 생겼어요";
      detail = path.basename(analysisPath);
    }
  } else {
    steps = setStep(steps, "run", "active");
    phase = "running";
    message = "자료를 모으고 분석하는 중이에요";
    if (hermesRc != null && hermesRc !== 0) {
      detail = `엔진이 코드 ${hermesRc}로 끝났어요. 아직 결과 파일이 없어요. (Kampff 출력 채널)`;
    } else {
      // filled below with inbox/runstatus live materials
      detail = "";
    }
  }

  if (!analysisPath && !(hermesRc != null && hermesRc !== 0)) {
    const inbox = scanInboxMaterials(targetId);
    const live = buildRunningDetail(runMsg, runPhase, inbox, elapsedSec);
    detail = live.detail;
    liveActivity = live.activity;
    liveMaterials = live.materials;
    liveHuman = live.human;
    message =
      inbox.postCount || inbox.textCount
        ? `자료 ${inbox.postCount || 0}글 · 텍스트 ${inbox.textCount || 0} · 분석 중`
        : "자료를 모으고 분석하는 중이에요";
  }

  if (analysisPath) {
    let rPath = findLatestReport(targetId);
    if (!rPath) {
      steps = setStep(steps, "report", "active");
      phase = "render";
      message = "읽기 쉬운 보고서로 정리하는 중";
      detail = "HTML dossier 생성…";
      try {
        rPath = await renderReportForTarget(targetId);
        reportPath = rPath;
        steps = setStep(steps, "report", "done");
      } catch (e) {
        detail = e instanceof Error ? e.message : String(e);
        if (hermesRc === 0 || analysisPath) {
          steps = setStep(steps, "report", "error");
          fail(active, `보고서 HTML 생성 실패: ${detail}`);
          return;
        }
      }
    } else {
      reportPath = rPath;
      steps = setStep(steps, "report", "done");
    }
  }

  if (reportPath) {
    steps = setStep(steps, "open", "done");
    steps = setStep(steps, "run", "done");
    steps = setStep(steps, "analysis", "done");
    steps = setStep(steps, "report", "done");

    let wikiPromotePath: string | undefined;
    if (cfg.wikiRoot) {
      const promo = promoteOutputsToWiki({
        targetId,
        platform: String(req.platform || "x"),
        nick: active.nick || req.parsed?.nick,
        analysisPath,
        reportPath,
        date: req.date,
        cfg,
      });
      if (promo.ok) {
        wikiPromotePath = promo.reportsDir || promo.wikiRoot;
        log(
          `WIKI PROMOTE ok → ${wikiPromotePath} (${promo.copied.length} files)`
        );
      } else {
        log(`WIKI PROMOTE skip/fail: ${promo.error || "unknown"}`);
      }
    }

    const done: JobProgress = {
      ...active,
      phase: "done",
      steps,
      message: wikiPromotePath
        ? "완료! 보고서 열림 · wiki에 복사함"
        : "완료! 보고서를 열었어요",
      detail: wikiPromotePath
        ? `${reportPath}\nwiki: ${wikiPromotePath}`
        : reportPath,
      humanPhase: humanPhase("done"),
      elapsedSec: Math.floor(elapsedSec),
      analysisPath,
      reportPath,
      wikiPromotePath,
      updatedAt: new Date().toISOString(),
      pct: 100,
      live: false,
      error: undefined,
    };
    emit(done);
    stopPollingOnly();
    log(`JOB DONE ${targetId} → ${reportPath}`);
    snapshotDepthTagged({
      analysisPath,
      reportPath,
      depth: pollCtx?.req.depth,
    });

    if (cfg.openReportOnComplete !== false) {
      try {
        await openReportForTarget(targetId);
      } catch {
        try {
          await vscode.commands.executeCommand(
            "kampff.openReportPath",
            reportPath
          );
        } catch {
          /* ignore */
        }
      }
    }
    return;
  }

  if (
    hermesRc != null &&
    hermesRc !== 0 &&
    !analysisPath &&
    elapsedSec > 15
  ) {
    fail(
      active,
      `분석 엔진 실패 (code ${hermesRc}). 보기 → 출력 → Kampff 로그 확인.`
    );
    return;
  }

  // hermes exited 0 but never wrote analysis.json (chat-only / TUI no-TTY / wrong out)
  const hermesFinishedClean =
    hermesRc === 0 ||
    runPhase === "hermes_done" ||
    runPhase === "done";
  if (hermesFinishedClean && !analysisPath && elapsedSec > 45) {
    fail(
      active,
      "Hermes는 끝났는데 analysis.json이 없어요. Output → Kampff 로그와 dataRoot/out·people 경로를 확인하세요. (TUI no-TTY면 --cli 누락일 수 있음)"
    );
    return;
  }

  // process died with no runstatus yet
  if (
    childProc &&
    childProc.exitCode != null &&
    childProc.exitCode !== 0 &&
    !analysisPath &&
    elapsedSec > 10
  ) {
    fail(
      active,
      `프로세스 종료 code=${childProc.exitCode}. Kampff 출력 채널을 열어 보세요.`
    );
    return;
  }

  // child exited 0, still no analysis after grace
  if (
    childProc &&
    childProc.exitCode === 0 &&
    !analysisPath &&
    elapsedSec > 45
  ) {
    fail(
      active,
      "작업 프로세스는 끝났는데 결과 파일이 없어요. Hermes 프롬프트가 analysis를 디스크에 쓰는지 확인하세요."
    );
    return;
  }

  emit({
    ...active,
    phase,
    steps,
    message,
    detail,
    activity: liveActivity || lastChildActivity || undefined,
    materials: liveMaterials.length ? liveMaterials : undefined,
    humanPhase: liveHuman || humanPhase(phase),
    elapsedSec: Math.floor(elapsedSec),
    analysisPath,
    reportPath,
    updatedAt: new Date().toISOString(),
    pct: livePct(phase, elapsedSec),
    live: phase === "running" || phase === "render",
    error: undefined,
  });
}

function fail(base: JobProgress, err: string): void {
  const steps = base.steps.map((s) =>
    s.state === "active" ? { ...s, state: "error" as const } : s
  );
  emit({
    ...base,
    phase: "error",
    steps,
    message: "문제가 생겼어요",
    detail: err,
    humanPhase: humanPhase("error"),
    error: err,
    updatedAt: new Date().toISOString(),
    pct: 100,
    live: false,
  });
  stopPollingOnly();
  log(`JOB FAIL: ${err}`);
  void vscode.window.showErrorMessage(`Kampff: ${err}`, "Kampff 로그 열기").then(
    (pick) => {
      if (pick) showKampffLog(true);
    }
  );
}

/** Map free-form phase strings from external progress writers → JobPhase */
function coercePhase(raw: unknown): JobPhase {
  const s = String(raw || "").toLowerCase();
  if (s === "done" || s === "complete" || s === "completed") return "done";
  if (s === "error" || s === "fail" || s === "failed") return "error";
  if (s === "idle" || s === "") return "idle";
  if (s === "queued" || s === "queue") return "queued";
  if (s === "analysis" || s === "analyze") return "analysis";
  if (s === "render" || s === "report") return "render";
  if (
    s === "running" ||
    s === "bodies" ||
    s === "index" ||
    s === "hermes" ||
    s === "clean" ||
    s === "stalled"
  ) {
    return "running";
  }
  return "running";
}

function isInternalJobLive(): boolean {
  // exitCode set ⇒ process already dead (don't block external watch / stale checks)
  return !!(
    childProc &&
    !childProc.killed &&
    childProc.exitCode == null &&
    childProc.signalCode == null
  );
}

let externalWatch: NodeJS.Timeout | undefined;
let lastExternalSig = "";

/**
 * Poll queue/*-progress.json written by external harvest/Hermes jobs
 * (when ① didn't own the child). Surfaces sticky card + status bar.
 * Internal startJobFromRequest still owns emit while its child is live.
 */
export function startExternalProgressWatch(): vscode.Disposable {
  if (externalWatch) {
    return new vscode.Disposable(() => undefined);
  }
  const tick = (): void => {
    try {
      if (isInternalJobLive()) return;
      const cfg = getConfig();
      const qDir = cfg.dataRoot
        ? path.join(cfg.dataRoot, "queue")
        : "";
      if (!qDir || !fs.existsSync(qDir)) return;

      const files = fs
        .readdirSync(qDir)
        .filter(
          (f) =>
            f.endsWith("-progress.json") || f.endsWith("-progress-live.json")
        )
        .map((f) => path.join(qDir, f))
        .filter((p) => {
          try {
            return fs.statSync(p).isFile();
          } catch {
            return false;
          }
        })
        .sort((a, b) => {
          try {
            return fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs;
          } catch {
            return 0;
          }
        });
      if (!files.length) return;

      const newest = files[0];
      const raw = fs.readFileSync(newest, "utf8");
      const sig = `${newest}:${fs.statSync(newest).mtimeMs}:${raw.length}`;
      if (sig === lastExternalSig) return;
      lastExternalSig = sig;

      let data: Record<string, unknown>;
      try {
        data = JSON.parse(raw) as Record<string, unknown>;
      } catch {
        return;
      }

      // Prefer JobProgress shape; accept live-dashboard shape too
      const metrics = (data.metrics || {}) as Record<string, unknown>;
      const stepsIn = Array.isArray(data.steps)
        ? (data.steps as JobStep[])
        : stepsTemplate();
      const targetId = String(
        data.targetId || data.target || metrics.target || ""
      ).trim();
      if (!targetId && !data.jobId && !data.job) return;

      let phase = coercePhase(data.phase);
      const updatedAt = String(
        data.updatedAt || new Date().toISOString()
      );
      // Prefer file mtime — rewriting progress used to freeze "running" forever.
      let ageMs = 0;
      try {
        ageMs = Date.now() - fs.statSync(newest).mtimeMs;
      } catch {
        try {
          ageMs = Date.now() - new Date(updatedAt.replace(/Z$/, "")).getTime();
        } catch {
          ageMs = 0;
        }
      }
      if (
        (phase === "done" ||
          phase === "idle" ||
          phase === "error" ||
          phase === "cancelled") &&
        ageMs > 120_000
      ) {
        if (
          !active ||
          active.phase === "done" ||
          active.phase === "idle" ||
          active.phase === "error" ||
          active.phase === "cancelled"
        ) {
          return;
        }
      }
      // Sibling runstatus: engine finished without product, progress still spinning
      if (
        (phase === "running" ||
          phase === "queued" ||
          phase === "analysis" ||
          phase === "render") &&
        !pollCtx
      ) {
        const rsPath = newest.replace(
          /-progress(-live)?\.json$/i,
          "-runstatus.json"
        );
        try {
          if (fs.existsSync(rsPath)) {
            const rs = JSON.parse(fs.readFileSync(rsPath, "utf8")) as {
              phase?: string;
              rc?: number;
              msg?: string;
            };
            const rp = String(rs.phase || "");
                        // hermes_done without product, hard error, or mid-flight runstatus
                        // abandoned (parent dead → never reaches hermes_done).
                        const midFlightStuck =
                          ageMs > 3 * 60_000 &&
                          /^(hermes|harvest|login|render|collect)$/i.test(rp);
                        const shouldFail =
                          rp === "error" ||
                          midFlightStuck ||
                          (rp === "hermes_done" && ageMs > 45_000) ||
                          (rp === "hermes_done" &&
                            typeof rs.rc === "number" &&
                            rs.rc !== 0);
                        if (shouldFail) {
                          phase = "error";
                          data = {
                            ...data,
                            phase: "error",
                            live: false,
                            message: "문제가 생겼어요",
                            detail:
                              rs.msg ||
                              (midFlightStuck
                                ? `엔진이 ${rp} 단계에서 멈춘 것으로 보여요 (진행 갱신 없음). 사이트 로그인·Go 다시.`
                                : rp === "hermes_done"
                                  ? "Hermes는 끝났는데 analysis.json이 없어요. 다시 시작해 주세요."
                                  : String(data.detail || "runstatus 종료")),
                            error: rs.msg || rp || "runstatus finished",
                            pct: 100,
                          };
              try {
                fs.writeFileSync(
                  newest,
                  JSON.stringify(data, null, 2),
                  "utf8"
                );
              } catch {
                /* ignore */
              }
              log(
                `runstatus→error: ${path.basename(newest)} phase=${rp} rc=${rs.rc}`
              );
            }
          }
        } catch {
          /* ignore */
        }
      }

      // Stale running/live with no owning poll (reload / dead job).
                  // 4 min when detail already says login-needed; else 8 min.
                  const loginHint = /로그인\s*필요|NEED_LOGIN|need_login/i.test(
                    `${data.detail || ""} ${data.activity || ""} ${data.message || ""}`
                  );
                  const staleMs = loginHint ? 4 * 60_000 : 8 * 60_000;
                  if (
                    (phase === "running" ||
                      phase === "queued" ||
                      phase === "analysis" ||
                      phase === "render") &&
                    ageMs > staleMs &&
                    !pollCtx
                  ) {
                    phase = "error";
                    data = {
                      ...data,
                      phase: "error",
                      live: false,
                      message: "문제가 생겼어요",
                      detail:
                        String(data.detail || "") ||
                        (loginHint
                          ? "로그인 세션 없이 멈춤 · 사이트 비밀번호 등록 후 다시 시작."
                          : "이전 분석이 중간에 멈춘 것으로 보여요 (진행 파일이 오래됨). 다시 시작해 주세요."),
                      error: loginHint ? "stale progress · login" : "stale progress",
                      pct: 100,
                    };
              try {
                fs.writeFileSync(newest, JSON.stringify(data, null, 2), "utf8");
              } catch {
                /* ignore */
              }
              log(
                `stale progress → error: ${path.basename(newest)} age=${Math.round(
                  ageMs / 1000
                )}s`
              );
            }

            // Zombie pause (reload / pid gone) — unlock Go
            if (phase === "paused" && !pollCtx && !isInternalJobLive()) {
              const pauseAgeOk = ageMs > 30_000;
              const detail = String(data.detail || "");
              const noPid = /pid=none/i.test(detail) || data.pid == null;
              if (pauseAgeOk || noPid) {
                phase = "cancelled";
                data = {
                  ...data,
                  phase: "cancelled",
                  live: false,
                  message: "분석을 중단했습니다.",
                  detail:
                    "좀비 일시정지 정리 (프로세스 없음). ① 다시 시작하면 됩니다.",
                  humanPhase: humanPhase("cancelled"),
                  pct: Number(data.pct) || 0,
                };
                try {
                  fs.writeFileSync(newest, JSON.stringify(data, null, 2), "utf8");
                } catch {
                  /* ignore */
                }
                log(
                  `zombie pause → cancelled: ${path.basename(newest)} age=${Math.round(
                    ageMs / 1000
                  )}s`
                );
              }
            }

      const queuePath = String(
        data.queuePath ||
          newest.replace(/-progress(-live)?\.json$/i, "-request.json")
      );
      const pct = Math.max(
        0,
        Math.min(100, Number(data.pct != null ? data.pct : 0) || 0)
      );
      const human =
        String(data.humanPhase || data.message || humanPhase(phase) || "").trim() ||
        humanPhase(phase);
      const posts = metrics.posts != null ? Number(metrics.posts) : undefined;
      const bodyHint =
        posts != null
          ? `본문 ${posts}` +
            (metrics.unique != null ? ` / ~${metrics.unique}` : "")
          : undefined;

      const p: JobProgress = {
        jobId: String(data.jobId || data.job || path.basename(newest)),
        targetId: targetId || "unknown",
        nick: data.nick ? String(data.nick) : undefined,
        phase,
        steps: stepsIn.map((s) => ({
          id: String((s as JobStep).id || ""),
          label: String((s as JobStep).label || (s as JobStep).id || ""),
          hint: (s as JobStep).hint,
          state: (["pending", "active", "done", "error", "skip"] as const).includes(
            (s as JobStep).state as JobStep["state"]
          )
            ? (s as JobStep).state
            : "pending",
        })),
        message: String(data.message || human),
        detail: String(
          data.detail || bodyHint || data.note || "외부 job progress 파일"
        ),
        humanPhase: human,
        elapsedSec:
          data.elapsedSec != null ? Number(data.elapsedSec) : undefined,
        analysisPath: data.analysisPath
          ? String(data.analysisPath)
          : undefined,
        reportPath: data.reportPath ? String(data.reportPath) : undefined,
        promptPath: data.promptPath ? String(data.promptPath) : undefined,
        queuePath,
        startedAt: String(data.startedAt || updatedAt),
        updatedAt,
        error: data.error ? String(data.error) : undefined,
        pct,
        live: data.live != null ? !!data.live : phase === "running" || phase === "render",
      };
      emit(p, { persist: false });
    } catch (e) {
      log(`external progress watch: ${e}`);
    }
  };

  externalWatch = setInterval(tick, 1500);
  tick();
  log("external progress watch ON (queue/*-progress.json)");
  return new vscode.Disposable(() => {
    if (externalWatch) {
      clearInterval(externalWatch);
      externalWatch = undefined;
    }
  });
}
