/**
 * Durable LLM Wiki shelf vs runtime KAMPFF_DATA.
 * Runtime: inbox / queue / out (scratch + job poll)
 * Wiki: people/ + reports/ (prior evidence + final promote)
 */
import * as fs from "fs";
import * as path from "path";
import {
  getConfig,
  KampffConfig,
  outDir,
  peopleDir,
  wikiReportsDir,
  wikiRoot,
} from "./config";

export type PriorKind =
  | "people_dir"
  | "notes"
  | "profile"
  | "history"
  | "analysis"
  | "report_md"
  | "report_html"
  | "other";

export interface PriorHit {
  kind: PriorKind;
  path: string;
  mtimeMs?: number;
  label?: string;
}

export interface PromoteResult {
  ok: boolean;
  wikiRoot?: string;
  reportsDir?: string;
  peopleDir?: string;
  copied: string[];
  skipped: string[];
  error?: string;
}

function existsDir(p: string): boolean {
  try {
    return !!(p && fs.existsSync(p) && fs.statSync(p).isDirectory());
  } catch {
    return false;
  }
}

function existsFile(p: string): boolean {
  try {
    return !!(p && fs.existsSync(p) && fs.statSync(p).isFile());
  } catch {
    return false;
  }
}

function mtime(p: string): number | undefined {
  try {
    return fs.statSync(p).mtimeMs;
  } catch {
    return undefined;
  }
}

function ensureDir(p: string): void {
  if (!p) return;
  fs.mkdirSync(p, { recursive: true });
}

function safeCopy(src: string, dest: string): boolean {
  if (!existsFile(src)) return false;
  ensureDir(path.dirname(dest));
  fs.copyFileSync(src, dest);
  return true;
}

function idTokens(platform: string, id: string, nick?: string): string[] {
  const out = new Set<string>();
  const add = (s?: string) => {
    const t = (s || "").trim();
    if (t) out.add(t.toLowerCase());
  };
  add(id);
  add(nick);
  add(platform);
  return Array.from(out).filter(Boolean);
}

function nameLooksLikeTarget(name: string, tokens: string[]): boolean {
  const n = name.toLowerCase();
  return tokens.some((t) => t.length >= 2 && n.includes(t));
}

/** Collect prior evidence for merge-into-next-analysis. */
export function findPriorEvidence(opts: {
  platform?: string;
  id?: string;
  nick?: string;
  cfg?: KampffConfig;
}): PriorHit[] {
  const cfg = opts.cfg || getConfig();
  const platform = (opts.platform || "x").toLowerCase();
  const id = (opts.id || "").trim();
  const nick = (opts.nick || "").trim();
  if (!id && !nick) return [];

  const tokens = idTokens(platform, id, nick);
  const hits: PriorHit[] = [];
  const seen = new Set<string>();

  const push = (kind: PriorKind, p: string, label?: string) => {
    const abs = path.resolve(p);
    const key = process.platform === "win32" ? abs.toLowerCase() : abs;
    if (seen.has(key)) return;
    if (!existsFile(abs) && !existsDir(abs)) return;
    seen.add(key);
    hits.push({ kind, path: abs, mtimeMs: mtime(abs), label });
  };

  // 1) durable people store (wiki-preferred via peopleDir())
  const pRoot = peopleDir(cfg);
  if (id && existsDir(pRoot)) {
    const person = path.join(pRoot, platform, id);
    if (existsDir(person)) {
      push("people_dir", person, `${platform}/${id}`);
      for (const name of [
        "NOTES.md",
        "notes.md",
        "profile.json",
        "history.json",
        "authorship_integrity.json",
      ]) {
        const fp = path.join(person, name);
        if (!existsFile(fp)) continue;
        const kind: PriorKind =
          name.toLowerCase().startsWith("notes")
            ? "notes"
            : name.startsWith("profile")
              ? "profile"
              : name.startsWith("history")
                ? "history"
                : "other";
        push(kind, fp, name);
      }
      // any prior analysis copies dropped into people folder
      try {
        for (const f of fs.readdirSync(person)) {
          if (f.endsWith("-analysis.json") || f === "analysis.json") {
            push("analysis", path.join(person, f), f);
          }
          if (f.endsWith("-report.md") || f.endsWith("-report.html")) {
            push(
              f.endsWith(".md") ? "report_md" : "report_html",
              path.join(person, f),
              f
            );
          }
        }
      } catch {
        /* ignore */
      }
    }
  }

  // 2) wiki reports/
  const wReports = wikiReportsDir(cfg);
  if (existsDir(wReports)) {
    try {
      for (const f of fs.readdirSync(wReports)) {
        if (!nameLooksLikeTarget(f, tokens)) continue;
        const fp = path.join(wReports, f);
        if (!existsFile(fp)) continue;
        if (f.endsWith("-analysis.json") || f.endsWith("analysis.json")) {
          push("analysis", fp, f);
        } else if (f.endsWith("-report.md") || f.endsWith(".md")) {
          push("report_md", fp, f);
        } else if (f.endsWith("-report.html") || f.endsWith(".html")) {
          push("report_html", fp, f);
        } else {
          push("other", fp, f);
        }
      }
    } catch {
      /* ignore */
    }
  }

  // 3) runtime out/ (scratch priors — still useful if wiki empty)
  const out = outDir(cfg);
  if (existsDir(out)) {
    try {
      for (const f of fs.readdirSync(out)) {
        if (!nameLooksLikeTarget(f, tokens)) continue;
        const fp = path.join(out, f);
        if (!existsFile(fp)) continue;
        if (f.endsWith("-analysis.json") || f.endsWith("analysis.json")) {
          push("analysis", fp, f);
        } else if (f.endsWith("-report.md")) {
          push("report_md", fp, f);
        } else if (f.endsWith("-report.html")) {
          push("report_html", fp, f);
        }
      }
    } catch {
      /* ignore */
    }
  }

  // newest first
  hits.sort((a, b) => (b.mtimeMs || 0) - (a.mtimeMs || 0));
  return hits;
}

export function ensureWikiLayout(cfg = getConfig()): void {
  const root = wikiRoot(cfg);
  if (!root) return;
  ensureDir(root);
  ensureDir(path.join(root, "people"));
  ensureDir(path.join(root, "reports"));
  const readme = path.join(root, "README.md");
  if (!existsFile(readme)) {
    fs.writeFileSync(
      readme,
      [
        "# Kampff · LLM Wiki shelf",
        "",
        "Durable Kampff outputs (not runtime scratch).",
        "",
        "| Path | Role |",
        "|------|------|",
        "| `people/{platform}/{id}/` | accumulate SoT (NOTES, profile, history) |",
        "| `reports/` | final analysis.json + report.html/.md copies |",
        "",
        "Runtime harvest lives under `kampff.dataRoot` (`inbox/`, `queue/`, `out/`).",
        "Re-analyze merges priors from this shelf + runtime out/.",
        "",
      ].join("\n"),
      "utf8"
    );
  }
}

/**
 * Copy finished job artifacts into wiki shelf.
 * people/ is only touched lightly (latest pointers); accumulate still owns deep merge.
 */
export function promoteOutputsToWiki(opts: {
  targetId: string;
  platform?: string;
  nick?: string;
  analysisPath?: string;
  reportPath?: string;
  date?: string;
  cfg?: KampffConfig;
}): PromoteResult {
  const cfg = opts.cfg || getConfig();
  const root = wikiRoot(cfg);
  if (!root) {
    return {
      ok: false,
      copied: [],
      skipped: [],
      error: "wikiRoot empty — skip promote",
    };
  }

  try {
    ensureWikiLayout(cfg);
    const reports = wikiReportsDir(cfg);
    const people = peopleDir(cfg);
    const platform = (opts.platform || "x").toLowerCase();
    const id = (opts.targetId || "").trim();
    const date =
      opts.date ||
      new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Seoul" });
    const base = `${date}-${id || "unknown"}`;
    const copied: string[] = [];
    const skipped: string[] = [];

    const copyNamed = (src: string | undefined, destName: string) => {
      if (!src || !existsFile(src)) {
        if (src) skipped.push(src);
        return;
      }
      const dest = path.join(reports, destName);
      if (safeCopy(src, dest)) copied.push(dest);
      else skipped.push(src);
    };

    if (opts.analysisPath) {
      const bn = path.basename(opts.analysisPath);
      copyNamed(
        opts.analysisPath,
        bn.includes(id) ? bn : `${base}-analysis.json`
      );
    }
    if (opts.reportPath) {
      const bn = path.basename(opts.reportPath);
      copyNamed(opts.reportPath, bn.includes(id) ? bn : `${base}-report.html`);
      // sibling md if present next to html
      if (opts.reportPath.endsWith(".html")) {
        const md = opts.reportPath.replace(/\.html$/i, ".md");
        if (existsFile(md)) {
          copyNamed(md, path.basename(md));
        }
      }
    }

    // people pointer folder + LATEST stubs (accumulate still does real merge)
    if (id && people) {
      const personDir = path.join(people, platform, id);
      ensureDir(personDir);
      const latest = {
        updatedAt: new Date().toISOString(),
        platform,
        id,
        nick: opts.nick || undefined,
        analysisPath: opts.analysisPath,
        reportPath: opts.reportPath,
        wikiReports: reports,
        promoted: copied,
      };
      const latestPath = path.join(personDir, "LATEST.json");
      fs.writeFileSync(latestPath, JSON.stringify(latest, null, 2), "utf8");
      copied.push(latestPath);

      // convenience copies under people for vault browsing
      if (opts.analysisPath && existsFile(opts.analysisPath)) {
        const dest = path.join(personDir, path.basename(opts.analysisPath));
        if (safeCopy(opts.analysisPath, dest)) copied.push(dest);
      }
      if (opts.reportPath && existsFile(opts.reportPath)) {
        const dest = path.join(personDir, path.basename(opts.reportPath));
        if (safeCopy(opts.reportPath, dest)) copied.push(dest);
      }
    }

    // vault-friendly index line (append, simple)
    const indexPath = path.join(root, "Index.md");
    const line = `- ${date} · ${platform}/${id}${opts.nick ? ` · ${opts.nick}` : ""} · reports/${base}-*`;
    if (!existsFile(indexPath)) {
      fs.writeFileSync(
        indexPath,
        ["# Kampff reports index", "", line, ""].join("\n"),
        "utf8"
      );
      copied.push(indexPath);
    } else {
      const prev = fs.readFileSync(indexPath, "utf8");
      if (!prev.includes(line)) {
        fs.appendFileSync(indexPath, `\n${line}\n`, "utf8");
      }
    }

    return {
      ok: true,
      wikiRoot: root,
      reportsDir: reports,
      peopleDir: people,
      copied,
      skipped,
    };
  } catch (e) {
    return {
      ok: false,
      wikiRoot: root,
      copied: [],
      skipped: [],
      error: e instanceof Error ? e.message : String(e),
    };
  }
}

/** Absolute paths only — for prompt / queue JSON. */
export function priorPathsForPrompt(hits: PriorHit[], max = 24): string[] {
  return hits.slice(0, max).map((h) => h.path);
}
