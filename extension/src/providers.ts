import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";
import { getConfig, inboxDir, reportScanDirs } from "./config";

export type KampffItemKind =
  | "report"
  | "html"
  | "graph"
  | "analysis"
  | "bundle"
  | "raw"
  | "dir"
  | "file";

export class KampffItem extends vscode.TreeItem {
  constructor(
    public readonly label: string,
    public readonly fsPath: string,
    public readonly kind: KampffItemKind,
    public readonly collapsible: vscode.TreeItemCollapsibleState,
    public readonly meta?: {
      distance?: string;
      confidence?: string;
      tldr?: string;
      id?: string;
      nick?: string;
    }
  ) {
    super(label, collapsible);
    this.resourceUri = vscode.Uri.file(fsPath);
    this.contextValue = `kampff.${kind}`;

        if (kind === "report" || kind === "html") {
          this.iconPath = distanceThemeIcon(meta?.distance);
          this.command = {
            command: "kampff.openReport",
            title: "Open Report",
            arguments: [this],
          };
          const d = meta?.distance || "?";
          const conf = meta?.confidence || "";
          this.description = conf ? `${d} · ${conf}` : d;
          this.tooltip = meta?.tldr ? `${fsPath}\n\n${meta.tldr}` : fsPath;
        } else if (kind === "analysis") {
          this.iconPath = new vscode.ThemeIcon("json");
          this.command = {
            command: "kampff.openAnalysisJson",
            title: "Open analysis",
            arguments: [this],
          };
          this.tooltip = new vscode.MarkdownString(
            [
              "**analysis.json** — 분석 원본 데이터",
              "엔진이 남긴 JSON. HTML 보고서의 재료입니다.",
              "",
              `\`${fsPath.replace(/\\/g, "/")}\``,
            ].join("\n\n")
          );
        } else if (kind === "graph") {
          this.iconPath = new vscode.ThemeIcon("type-hierarchy");
          this.command = {
            command: "kampff.openGraph",
            title: "Open graph",
            arguments: [this],
          };
          this.description = "relation";
          this.tooltip = new vscode.MarkdownString(
            [
              "**관계 그래프** — 사람들 · 엣지 · 레벨 필터",
              "한 사람 도셔가 아닙니다. Hide/Dim · 선 두께는 HTML 안에서.",
              "",
              `\`${fsPath.replace(/\\/g, "/")}\``,
            ].join("\n\n")
          );
        } else if (kind === "bundle") {
          this.iconPath = new vscode.ThemeIcon("package");
          this.command = {
            command: "vscode.open",
            title: "Open",
            arguments: [vscode.Uri.file(fsPath)],
          };
          this.tooltip = new vscode.MarkdownString(
            [
              "**bundle** — Inbox 수집 묶음",
              "아직 보고서로 안 만든 원본 재료에 가깝습니다.",
              "",
              `\`${fsPath.replace(/\\/g, "/")}\``,
            ].join("\n\n")
          );
        } else if (kind === "dir") {
          this.iconPath = new vscode.ThemeIcon("folder");
          this.tooltip = fsPath;
        } else if (kind === "raw") {
          this.iconPath = new vscode.ThemeIcon("database");
          this.tooltip = new vscode.MarkdownString(
            [
              "**raw** — 원시 수집 트리",
              "사이트에서 긁어 온 원본. 디버깅·재분석용.",
              "",
              `\`${fsPath.replace(/\\/g, "/")}\``,
            ].join("\n\n")
          );
        } else {
          this.iconPath = new vscode.ThemeIcon("file");
          this.command = {
            command: "vscode.open",
            title: "Open",
            arguments: [vscode.Uri.file(fsPath)],
          };
          this.tooltip = fsPath;
        }
  }
}

/** Colored distance badge icon for tree rows (Linear-ish status chroma). */
export function distanceThemeIcon(distance?: string): vscode.ThemeIcon {
  const d = (distance || "").toLowerCase();
  let colorId = "charts.blue";
  let icon = "circle-large-outline";
  if (d.includes("align") || d === "close" || d === "near") {
    colorId = "charts.green";
    icon = "pass-filled";
  } else if (d.includes("neutral")) {
    colorId = "charts.blue";
    icon = "circle-filled";
  } else if (d.includes("caution") || d.includes("watch")) {
    colorId = "charts.yellow";
    icon = "warning";
  } else if (
    d.includes("hostile") ||
    d.includes("far") ||
    d.includes("danger") ||
    d.includes("high")
  ) {
    colorId = "charts.red";
    icon = "error";
  }
  return new vscode.ThemeIcon(icon, new vscode.ThemeColor(colorId));
}

/** Plain-language KO for tree hover (distance / confidence jargon). */
export function distanceExplainKo(distance?: string): string {
  const d = (distance || "").toLowerCase();
  if (!d) return "distance: 나와의 관계·태도 거리 요약(가설).";
  if (d.includes("align") || d === "close" || d === "near")
    return `distance \`${distance}\` — 가깝거나 결이 맞음(가설).`;
  if (d.includes("neutral"))
    return `distance \`${distance}\` — 중간·중립.`;
  if (d.includes("caution") || d.includes("watch"))
    return `distance \`${distance}\` — 주의해서 볼 만함.`;
  if (
    d.includes("hostile") ||
    d.includes("far") ||
    d.includes("danger") ||
    d.includes("high")
  )
    return `distance \`${distance}\` — 멀거나 적대 쪽 신호.`;
  return `distance \`${distance}\` — 관계 거리 라벨(가설).`;
}

function readAnalysisMeta(htmlPath: string): {
  distance?: string;
  confidence?: string;
  tldr?: string;
  analysisPath?: string;
  id?: string;
  nick?: string;
} {
  const base = htmlPath.replace(/-report\.html$/i, "");
  const analysisPath = `${base}-analysis.json`;
  if (!fs.existsSync(analysisPath)) {
    const dir = path.dirname(htmlPath);
    const stem = path.basename(htmlPath, ".html").replace(/-report$/, "");
    const alt = path.join(dir, `${stem}-analysis.json`);
    if (!fs.existsSync(alt)) return {};
    return loadMeta(alt);
  }
  return loadMeta(analysisPath);
}

function loadMeta(analysisPath: string): {
  distance?: string;
  confidence?: string;
  tldr?: string;
  analysisPath: string;
  id?: string;
  nick?: string;
} {
  try {
    const j = JSON.parse(fs.readFileSync(analysisPath, "utf8")) as {
      distance?: string;
      confidence?: string;
      tldr?: string;
      target?: { id?: string; nick?: string };
    };
    const id = j.target?.id;
    const nick = j.target?.nick;
    return {
      distance: j.distance,
      confidence: j.confidence,
      tldr: j.tldr,
      analysisPath,
      id,
      nick,
    };
  } catch {
    return { analysisPath };
  }
}

/** Human label: nick · id (filename fallback) */
export function reportDisplayLabel(
  filePath: string,
  meta?: { id?: string; nick?: string }
): string {
  const base = path.basename(filePath);
  const m = base.match(/^(\d{4}-\d{2}-\d{2})-(.+?)-report\.html$/i);
  const fileId = m?.[2];
  const id = meta?.id || fileId || base;
  const nick = (meta?.nick || "").trim();
  if (nick && id && nick !== id) return `${nick} · ${id}`;
  if (nick) return nick;
  if (id) return id;
  return base;
}

export class ReportsProvider implements vscode.TreeDataProvider<KampffItem> {
  private _onDidChange = new vscode.EventEmitter<KampffItem | undefined | void>();
  readonly onDidChangeTreeData = this._onDidChange.event;

  refresh(): void {
    this._onDidChange.fire();
  }

  getTreeItem(e: KampffItem): vscode.TreeItem {
    return e;
  }

  getChildren(element?: KampffItem): KampffItem[] {
    if (element) return [];
    const roots = reportScanDirs();
    if (!roots.length) return [];
    const max = getConfig().maxReportsListed;
    const files: string[] = [];
    const seen = new Set<string>();
    for (const root of roots) {
      if (!root || !fs.existsSync(root)) continue;
      try {
        for (const f of fs.readdirSync(root)) {
          if (
            !(
              f.endsWith("-report.html") ||
              f.endsWith("-graph.html") ||
              (f.endsWith(".html") && f.includes("report"))
            )
          ) {
            continue;
          }
          const p = path.join(root, f);
          try {
            if (!fs.statSync(p).isFile()) continue;
          } catch {
            continue;
          }
          const key = path.basename(p).toLowerCase();
          // Prefer runtime out/ first (roots order); skip wiki dup basename
          if (seen.has(key)) continue;
          seen.add(key);
          files.push(p);
        }
      } catch {
        /* ignore */
      }
    }
    files.sort((a, b) => reportSortKey(b) - reportSortKey(a));
    const sliced = files.slice(0, max);

    return sliced.map((p) => {
      if (p.toLowerCase().endsWith("-graph.html")) {
        const base = path.basename(p);
        const item = new KampffItem(
          base.replace(/-graph\.html$/i, " · graph"),
          p,
          "graph",
          vscode.TreeItemCollapsibleState.None
        );
        return item;
      }
      const meta = readAnalysisMeta(p);
      const label = reportDisplayLabel(p, meta);
      const item = new KampffItem(
        label,
        p,
        "report",
        vscode.TreeItemCollapsibleState.None,
        meta
      );
      const d = meta?.distance || "?";
      const conf = meta?.confidence || "";
      const base = path.basename(p);
      const inWiki = roots.length > 1 && p.startsWith(roots[1]);
      item.description = conf
        ? `${d} · ${conf}${inWiki ? " · wiki" : ""}`
        : `${d}${inWiki ? " · wiki" : ""}`;
      item.iconPath = distanceThemeIcon(meta?.distance);
      item.tooltip = new vscode.MarkdownString(
              [
                `**${label}**`,
                `\`${base}\``,
                inWiki ? "출처: LLM Wiki `reports/`" : "출처: runtime `out/`",
                meta?.distance
                  ? distanceExplainKo(meta.distance)
                  : "distance: (없음) — 나와의 관계·태도 거리 요약",
                meta?.confidence
                  ? `confidence \`${meta.confidence}\` — 이 판단이 얼마나 단단한지`
                  : "",
                meta?.tldr ? `TL;DR — ${meta.tldr}` : "",
                "",
                "보고서 HTML · 클릭하면 엽니다.",
                p.replace(/\\/g, "/"),
              ]
                .filter(Boolean)
                .join("\n\n")
            );
      item.tooltip.isTrusted = false;
      item.tooltip.supportThemeIcons = true;
      return item;
    });
  }

  latest(): KampffItem | undefined {
    const kids = this.getChildren();
    return kids[0];
  }
}

function reportSortKey(htmlPath: string): number {
  try {
    const htmlMt = fs.statSync(htmlPath).mtimeMs;
    const base = htmlPath.replace(/-report\.html$/i, "");
    const analysisPath = `${base}-analysis.json`;
    let analysisMt = 0;
    if (fs.existsSync(analysisPath)) {
      analysisMt = fs.statSync(analysisPath).mtimeMs;
    }
    // Primary: newer analysis (actual dossier work). Secondary: html.
    // Filename date bump so same-second batch ties don't stick on loop order.
    const name = path.basename(htmlPath);
    const dm = name.match(/^(\d{4})-(\d{2})-(\d{2})/);
    const day =
      dm != null
        ? Date.UTC(+dm[1], +dm[2] - 1, +dm[3]) / 1000
        : 0;
    return Math.max(analysisMt, htmlMt) + day * 0.0001;
  } catch {
    return 0;
  }
}

export class InboxProvider implements vscode.TreeDataProvider<KampffItem> {
  private _onDidChange = new vscode.EventEmitter<KampffItem | undefined | void>();
  readonly onDidChangeTreeData = this._onDidChange.event;

  refresh(): void {
    this._onDidChange.fire();
  }

  getTreeItem(e: KampffItem): vscode.TreeItem {
    return e;
  }

  getChildren(element?: KampffItem): KampffItem[] {
    const root = inboxDir();
    if (!root || !fs.existsSync(root)) return [];

    if (!element) {
      return fs
        .readdirSync(root)
        .map((d) => path.join(root, d))
        .filter((p) => fs.statSync(p).isDirectory())
        .sort()
        .reverse()
        .map((p) => new KampffItem(path.basename(p), p, "dir", vscode.TreeItemCollapsibleState.Collapsed));
    }

    // list bundles in date folder
    const entries = fs.readdirSync(element.fsPath);
    const items: KampffItem[] = [];
    for (const name of entries) {
      const p = path.join(element.fsPath, name);
      const st = fs.statSync(p);
      if (st.isFile() && name.startsWith("bundle") && name.endsWith(".json")) {
        items.push(new KampffItem(name, p, "bundle", vscode.TreeItemCollapsibleState.None));
      }
    }
    return items.sort((a, b) => a.label.localeCompare(b.label));
  }
}

export class RawProvider implements vscode.TreeDataProvider<KampffItem> {
  private _onDidChange = new vscode.EventEmitter<KampffItem | undefined | void>();
  readonly onDidChangeTreeData = this._onDidChange.event;

  refresh(): void {
    this._onDidChange.fire();
  }

  getTreeItem(e: KampffItem): vscode.TreeItem {
    return e;
  }

  getChildren(element?: KampffItem): KampffItem[] {
    if (!element) {
      const root = inboxDir();
      if (!root || !fs.existsSync(root)) return [];
      const items: KampffItem[] = [];
      for (const date of fs.readdirSync(root).sort().reverse()) {
        const raw = path.join(root, date, "raw");
        if (fs.existsSync(raw) && fs.statSync(raw).isDirectory()) {
          items.push(new KampffItem(`${date}/raw`, raw, "dir", vscode.TreeItemCollapsibleState.Collapsed));
        }
      }
      return items;
    }

    // one level of members / files
    try {
      return fs
        .readdirSync(element.fsPath)
        .map((n) => {
          const p = path.join(element.fsPath, n);
          const st = fs.statSync(p);
          if (st.isDirectory()) {
            return new KampffItem(n, p, "raw", vscode.TreeItemCollapsibleState.Collapsed);
          }
          return new KampffItem(n, p, "file", vscode.TreeItemCollapsibleState.None);
        })
        .sort((a, b) => a.label.localeCompare(b.label));
    } catch {
      return [];
    }
  }
}

export function analysisPathForReport(reportHtml: string): string | undefined {
  const meta = readAnalysisMeta(reportHtml);
  return meta.analysisPath;
}

export function getConfigDataRoot(): string {
  return getConfig().dataRoot;
}
