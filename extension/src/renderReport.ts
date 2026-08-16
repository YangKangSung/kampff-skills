/**
 * Resolve analysis/report for a target id and run render_kampff_report.py
 */
import * as fs from "fs";
import * as path from "path";
import { spawn } from "child_process";
import * as vscode from "vscode";
import { getConfig, outDir } from "./config";

/** Strict match: `YYYY-MM-DD-{id}-analysis.json` preferred over loose includes. */
export function findLatestAnalysis(targetId: string): string | undefined {
  const out = outDir();
  if (!out || !fs.existsSync(out)) return undefined;
  const id = targetId.trim();
  if (!id) return undefined;

  const all = fs
    .readdirSync(out)
    .filter((f) => f.endsWith("-analysis.json"))
    .map((f) => path.join(out, f))
    .filter((p) => fs.existsSync(p));

  const strict = all.filter((p) => {
    const base = path.basename(p, ".json"); // date-id-analysis
    return base.endsWith(`-${id}-analysis`) || base === `${id}-analysis`;
  });
  const pool = (strict.length ? strict : all.filter((p) => path.basename(p).includes(id))).sort(
    (a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs
  );
  return pool[0];
}

export function findLatestReport(targetId: string): string | undefined {
  const a = findLatestAnalysis(targetId);
  if (a) {
    const r = analysisToReportPath(a);
    if (fs.existsSync(r)) return r;
  }
  const out = outDir();
  if (!out || !fs.existsSync(out)) return undefined;
  const id = targetId.trim();
  const files = fs
    .readdirSync(out)
    .filter((f) => f.endsWith("-report.html"))
    .filter((f) => {
      const base = f.replace(/-report\.html$/i, "");
      return base.endsWith(`-${id}`) || base === id;
    })
    .map((f) => path.join(out, f))
    .sort((a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs);
  return files[0];
}

export function analysisToReportPath(analysisPath: string): string {
  return analysisPath.replace(/-analysis\.json$/i, "-report.html");
}

export type ReportDepth = "quick" | "full";

export interface DepthReport {
  depth: ReportDepth;
  reportPath: string;
  analysisPath?: string;
  mtimeMs: number;
}

function isTaggedName(p: string): boolean {
  const b = path.basename(p);
  return /-(quick|full)-(analysis\.json|report\.html)$/i.test(b);
}

export function insertDepthTag(filePath: string, depth: ReportDepth): string {
  if (isTaggedName(filePath)) return filePath;
  return filePath
    .replace(/-analysis\.json$/i, `-${depth}-analysis.json`)
    .replace(/-report\.html$/i, `-${depth}-report.html`);
}

export function readAnalysisDepth(analysisPath: string): ReportDepth | undefined {
  try {
    const j = JSON.parse(fs.readFileSync(analysisPath, "utf8")) as {
      meta?: { depth?: string };
      depth?: string;
    };
    const d = String(j.meta?.depth || j.depth || "").toLowerCase();
    if (d === "quick" || d === "full") return d;
  } catch {
    /* ignore */
  }
  const b = path.basename(analysisPath);
  if (/-quick-analysis\.json$/i.test(b)) return "quick";
  if (/-full-analysis\.json$/i.test(b)) return "full";
  return undefined;
}

/** Copy latest untagged files to `{date}-{id}-{depth}-*` so quick/full both stay. */
export function snapshotDepthTagged(opts: {
  analysisPath?: string;
  reportPath?: string;
  depth?: ReportDepth;
}): void {
  const depth =
    opts.depth ||
    (opts.analysisPath ? readAnalysisDepth(opts.analysisPath) : undefined);
  if (!depth) return;
  const copies: Array<[string | undefined, string]> = [
    [opts.analysisPath, "analysis"],
    [opts.reportPath, "report"],
  ];
  for (const [src] of copies) {
    if (!src || !fs.existsSync(src)) continue;
    const dest = insertDepthTag(src, depth);
    if (dest === src) continue;
    try {
      const newer =
        !fs.existsSync(dest) ||
        fs.statSync(src).mtimeMs >= fs.statSync(dest).mtimeMs;
      if (newer) fs.copyFileSync(src, dest);
    } catch {
      /* ignore */
    }
  }
}

function idMatchesReport(fileName: string, id: string): boolean {
  const base = fileName.replace(/-report\.html$/i, "");
  return (
    base === id ||
    base.endsWith(`-${id}`) ||
    base.endsWith(`-${id}-quick`) ||
    base.endsWith(`-${id}-full`)
  );
}

export function findReportsByDepth(targetId: string): DepthReport[] {
  const out = outDir();
  const id = targetId.trim();
  if (!out || !id || !fs.existsSync(out)) return [];
  const byDepth = new Map<ReportDepth, DepthReport>();

  const consider = (reportPath: string, depth: ReportDepth) => {
    const st = fs.statSync(reportPath);
    const prev = byDepth.get(depth);
    if (!prev || st.mtimeMs >= prev.mtimeMs) {
      const analysisPath = reportPath.replace(/-report\.html$/i, "-analysis.json");
      byDepth.set(depth, {
        depth,
        reportPath,
        analysisPath: fs.existsSync(analysisPath) ? analysisPath : undefined,
        mtimeMs: st.mtimeMs,
      });
    }
  };

  for (const f of fs.readdirSync(out)) {
    if (!f.endsWith("-report.html")) continue;
    if (!idMatchesReport(f, id)) continue;
    const p = path.join(out, f);
    if (/-quick-report\.html$/i.test(f)) consider(p, "quick");
    else if (/-full-report\.html$/i.test(f)) consider(p, "full");
    else {
      const a = p.replace(/-report\.html$/i, "-analysis.json");
      const d = fs.existsSync(a) ? readAnalysisDepth(a) : undefined;
      if (d) {
        snapshotDepthTagged({ analysisPath: a, reportPath: p, depth: d });
        consider(p, d);
      }
    }
  }
  return [...byDepth.values()].sort((a, b) => b.mtimeMs - a.mtimeMs);
}

export async function openReportInBrowser(
  targetId: string,
  depth?: ReportDepth
): Promise<string> {
  const id = targetId.trim();
  if (!id) throw new Error("ID 없음");
  snapshotDepthTagged({
    analysisPath: findLatestAnalysis(id),
    reportPath: findLatestReport(id),
  });
  const all = findReportsByDepth(id);
  const hit = depth ? all.find((r) => r.depth === depth) : all[0];
  if (!hit) {
    throw new Error(
      depth
        ? `${id} · ${depth === "full" ? "FULL" : "빠른"} 리포트 없음\n그 깊이로 한 번 돌린 뒤에 열 수 있음`
        : `리포트 없음: ${id}`
    );
  }
  await vscode.env.openExternal(vscode.Uri.file(hit.reportPath));
  return hit.reportPath;
}

export function targetHasAnalysis(targetId: string): boolean {
  return !!findLatestAnalysis(targetId);
}

export function targetHasReport(targetId: string): boolean {
  return !!findLatestReport(targetId);
}

export async function renderReportFromAnalysis(
  analysisPath: string,
  openAfter = true
): Promise<string> {
  const cfg = getConfig();
  if (!fs.existsSync(analysisPath)) {
    throw new Error(`analysis 없음: ${analysisPath}`);
  }
  const reportPath = analysisToReportPath(analysisPath);
  const script = path.join(cfg.skillsDevRoot, "scripts", "render_kampff_report.py");
  if (!fs.existsSync(script)) {
    throw new Error(`renderer 없음: ${script}`);
  }
  const py = cfg.pythonPath || "python";

  await new Promise<void>((resolve, reject) => {
    const child = spawn(
      py,
      [script, "-a", analysisPath, "-o", reportPath, "--lang", cfg.uiLanguage],
      {
        cwd: cfg.skillsDevRoot,
        windowsHide: true,
        env: { ...process.env, KAMPFF_LANG: cfg.uiLanguage },
      }
    );
    let err = "";
    child.stderr.on("data", (d) => (err += String(d)));
    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) resolve();
      else reject(new Error(err || `renderer exit ${code}`));
    });
  });

  snapshotDepthTagged({
    analysisPath,
    reportPath,
    depth: readAnalysisDepth(analysisPath),
  });

  if (openAfter && fs.existsSync(reportPath)) {
    const mode = cfg.reportOpenMode;
    if (mode === "browser" || mode === "both") {
      await vscode.env.openExternal(vscode.Uri.file(reportPath));
    }
    if (mode === "panel" || mode === "both") {
      await vscode.commands.executeCommand("kampff.openReportPath", reportPath);
    }
  }
  return reportPath;
}

export async function renderReportForTarget(targetId: string): Promise<string> {
  const a = findLatestAnalysis(targetId);
  if (!a) {
    throw new Error(
      `analysis.json 없음: ${targetId}\n→ 먼저 「① 큐에 넣기」로 수집·분석 후, analysis가 생기면 ②`
    );
  }
  return renderReportFromAnalysis(a, true);
}

export async function openReportForTarget(targetId: string): Promise<string> {
  const id = targetId.trim();
  if (!id) throw new Error("ID 없음");
  let report = findLatestReport(id);
  if (!report) {
    // try render if analysis exists
    if (findLatestAnalysis(id)) {
      report = await renderReportForTarget(id);
    } else {
      throw new Error(
        `리포트 없음: ${id}\n(out/*-${id}-report.html)\n→ 이 ID로 분석이 끝난 뒤에만 열 수 있음. out 최신(다른 사람)이 아님.`
      );
    }
  } else {
    await vscode.commands.executeCommand("kampff.openReportPath", report);
  }
  return report;
}
