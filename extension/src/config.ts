import * as path from "path";
import * as vscode from "vscode";

export type AnalyzeLaunch = "terminal" | "hermes" | "none" | "auto";
export type ReportOpenMode = "panel" | "browser" | "both";
export type StatusBarClick = "analyze" | "latestReport" | "menu";
export type AnalyzeModeDefault = "auto" | "member" | "thread" | "profile";
export type AnalyzeDepthDefault = "quick" | "full";

export type PlatformId =
  | "facebook"
  | "x"
  | "instagram"
  | "reddit"
  | "linkedin"
  | "custom";

export interface PlatformDef {
  id: PlatformId;
  label: string;
  placeholder: string;
  urlFromHandle?: (handle: string) => string;
  matchUrl?: RegExp;
}

export const PLATFORMS: PlatformDef[] = [
  {
    id: "facebook",
    label: "Facebook",
    placeholder: "profile URL or username",
    urlFromHandle: (h) =>
      `https://www.facebook.com/${h.replace(/^@/, "").replace(/^https?:\/\/(www\.)?facebook\.com\//i, "")}`,
    matchUrl: /(facebook\.com|fb\.com)/i,
  },
  {
    id: "x",
    label: "X",
    placeholder: "@elonmusk or https://x.com/elonmusk (example only)",
    urlFromHandle: (h) => `https://x.com/${h.replace(/^@/, "")}`,
    matchUrl: /(^https?:\/\/)?(x\.com|twitter\.com)\//i,
  },
  {
    id: "instagram",
    label: "Instagram",
    placeholder: "@handle or profile URL",
    urlFromHandle: (h) => `https://www.instagram.com/${h.replace(/^@/, "")}/`,
    matchUrl: /instagram\.com/i,
  },
  {
    id: "reddit",
    label: "Reddit",
    placeholder: "u/name or profile/post URL",
    urlFromHandle: (h) => {
      const u = h.replace(/^\/?u\//i, "").replace(/^@/, "");
      return `https://www.reddit.com/user/${u}/`;
    },
    matchUrl: /reddit\.com/i,
  },
  {
    id: "linkedin",
    label: "LinkedIn",
    placeholder: "in/slug or profile URL",
    urlFromHandle: (h) => {
      const s = h.replace(/^\/?in\//i, "").replace(/^@/, "");
      return `https://www.linkedin.com/in/${s}/`;
    },
    matchUrl: /linkedin\.com/i,
  },
  {
    id: "custom",
    label: "Custom URL",
    placeholder: "https://…",
    matchUrl: /^https?:\/\//i,
  },
];

export interface KampffConfig {
  /** Runtime KAMPFF_DATA: inbox / queue / out (scratch + job poll). */
  dataRoot: string;
  skillsDevRoot: string;
  /**
   * Durable LLM Wiki shelf (people/ + reports/).
   * Empty = no wiki promote / no wiki prior scan beyond peopleRoot override.
   */
  wikiRoot: string;
  /**
   * People accumulate store.
   * Empty → `{wikiRoot}/people` if wikiRoot set, else `{dataRoot}/people`.
   */
  peopleRoot: string;
  /**
   * Final report copies under wiki.
   * Empty → `{wikiRoot}/reports` if wikiRoot set, else "".
   */
  wikiReportsRoot: string;
  autoRefreshMs: number;
  showStatusBar: boolean;
  statusBarClick: StatusBarClick;
  pythonPath: string;
  hermesCommand: string;
  analyzeLaunch: AnalyzeLaunch;
  enabledPlatforms: PlatformId[];
  customPlatforms: { id: string; label: string; urlTemplate: string }[];
  defaultPlatform: PlatformId;
  defaultMode: AnalyzeModeDefault;
  defaultDepth: AnalyzeDepthDefault;
  autoOpenPrompt: boolean;
  openReportOnComplete: boolean;
  reportOpenMode: ReportOpenMode;
  showPeopleView: boolean;
  maxReportsListed: number;
  uiLanguage: "ko" | "en";
  promptIncludeClinical: boolean;
  promptIncludeAuthorship: boolean;
  promptIncludeAccumulate: boolean;
    notifyOnQueue: boolean;
    /** Harvest pacing (all sites). Default true. */
    harvestPolite: boolean;
    harvestDelayMinSec: number;
    harvestDelayMaxSec: number;
    harvestMaxFetch: number;
    harvestBurstEvery: number;
    harvestBurstPauseSec: number;
  }

function parsePlatformList(raw: unknown): PlatformId[] {
  const all = PLATFORMS.map((p) => p.id);
  if (!Array.isArray(raw) || raw.length === 0) return all;
  const set = new Set(all);
  const out = raw
    .map((x) => String(x).toLowerCase())
    .filter((x): x is PlatformId => set.has(x as PlatformId));
  return out.length ? out : all;
}

export function getConfig(): KampffConfig {
  const c = vscode.workspace.getConfiguration("kampff");
  const launch = (c.get<string>("analyzeLaunch") || "auto").toLowerCase();
  const defPlat = (c.get<string>("defaultPlatform") || "x").toLowerCase();
  const defMode = (c.get<string>("defaultMode") || "member").toLowerCase();
  const defDepth = (c.get<string>("defaultDepth") || "quick").toLowerCase();
  const reportMode = (c.get<string>("reportOpenMode") || "panel").toLowerCase();
  const sbClick = (c.get<string>("statusBarClick") || "menu").toLowerCase();
  const uiLang = (c.get<string>("uiLanguage") || "ko").toLowerCase();
  const dataRoot = (c.get<string>("dataRoot") || "").trim();
  const wikiRootRaw = (c.get<string>("wikiRoot") || "").trim();
  const peopleRootRaw = (c.get<string>("peopleRoot") || "").trim();
  const wikiReportsRaw = (c.get<string>("wikiReportsRoot") || "").trim();

  const customRaw = c.get<{ id?: string; label?: string; urlTemplate?: string }[]>(
    "customPlatforms"
  );
  const customPlatforms = (customRaw || [])
    .filter((x) => x && (x.urlTemplate || x.label))
    .map((x, i) => ({
      id: (x.id || `custom_${i}`).replace(/\s+/g, "_"),
      label: x.label || x.id || `Custom ${i + 1}`,
      urlTemplate: x.urlTemplate || "https://{handle}",
    }));

  const peopleRoot =
    peopleRootRaw ||
    (wikiRootRaw
      ? path.join(wikiRootRaw, "people")
      : dataRoot
        ? path.join(dataRoot, "people")
        : "");
  const wikiReportsRoot =
    wikiReportsRaw ||
    (wikiRootRaw ? path.join(wikiRootRaw, "reports") : "");

  return {
    dataRoot,
    skillsDevRoot: (c.get<string>("skillsDevRoot") || "").trim(),
    wikiRoot: wikiRootRaw,
    peopleRoot,
    wikiReportsRoot,
    autoRefreshMs: c.get<number>("autoRefreshMs") ?? 15000,
    showStatusBar: c.get<boolean>("showStatusBar") !== false,
    statusBarClick:
      sbClick === "analyze"
        ? "analyze"
        : sbClick === "latestreport" || sbClick === "latestReport"
          ? "latestReport"
          : "menu",
    pythonPath: (c.get<string>("pythonPath") || "python").trim(),
    hermesCommand: (() => {
          const v = (c.get<string>("hermesCommand") || "").trim();
          if (v) return v;
          // Empty setting → jobRunner.resolveHermesCommand picks a real path.
          // Never build Windows paths with `\\h`/`\\v` in template strings (\v = VT).
          return "";
        })(),
    analyzeLaunch:
          launch === "none"
            ? "none"
            : launch === "terminal"
              ? "terminal"
              : launch === "hermes"
                ? "hermes"
                : "auto",
    enabledPlatforms: parsePlatformList(c.get("enabledPlatforms")),
    customPlatforms,
    defaultPlatform: (PLATFORMS.some((p) => p.id === defPlat)
      ? defPlat
      : "x") as PlatformId,
    defaultMode: (["auto", "member", "thread", "profile"].includes(defMode)
      ? defMode
      : "auto") as AnalyzeModeDefault,
    defaultDepth: defDepth === "full" ? "full" : "quick",
    autoOpenPrompt: c.get<boolean>("autoOpenPrompt") === true,
    openReportOnComplete: c.get<boolean>("openReportOnComplete") !== false,
    reportOpenMode:
      reportMode === "browser"
        ? "browser"
        : reportMode === "both"
          ? "both"
          : "panel",
    showPeopleView: c.get<boolean>("showPeopleView") !== false,
    maxReportsListed: Math.max(10, Math.min(500, c.get<number>("maxReportsListed") ?? 80)),
    uiLanguage: uiLang === "en" ? "en" : "ko",
    promptIncludeClinical: c.get<boolean>("promptIncludeClinical") !== false,
    promptIncludeAuthorship: c.get<boolean>("promptIncludeAuthorship") !== false,
    promptIncludeAccumulate: c.get<boolean>("promptIncludeAccumulate") !== false,
        notifyOnQueue: c.get<boolean>("notifyOnQueue") === true,
        harvestPolite: c.get<boolean>("harvestPolite") !== false,
        harvestDelayMinSec: Math.max(
          1,
          Math.min(30, (c.get<number>("harvestDelayMinSec") ?? c.get<number>("clienDelayMinSec")) ?? 2.8)
        ),
        harvestDelayMaxSec: Math.max(
          2,
          Math.min(60, (c.get<number>("harvestDelayMaxSec") ?? c.get<number>("clienDelayMaxSec")) ?? 6.5)
        ),
        harvestMaxFetch: Math.max(
          5,
          Math.min(200, (c.get<number>("harvestMaxFetch") ?? c.get<number>("clienMaxFetch")) ?? 40)
        ),
        harvestBurstEvery: Math.max(
          2,
          Math.min(50, (c.get<number>("harvestBurstEvery") ?? c.get<number>("clienBurstEvery")) ?? 6)
        ),
        harvestBurstPauseSec: Math.max(
          3,
          Math.min(120, (c.get<number>("harvestBurstPauseSec") ?? c.get<number>("clienBurstPauseSec")) ?? 10)
        ),
      };
    }

export async function updateConfig(
  key: string,
  value: unknown,
  target: vscode.ConfigurationTarget = vscode.ConfigurationTarget.Global
): Promise<void> {
  await vscode.workspace.getConfiguration("kampff").update(key, value, target);
}

export function outDir(cfg = getConfig()): string {
  return cfg.dataRoot ? path.join(cfg.dataRoot, "out") : "";
}

export function inboxDir(cfg = getConfig()): string {
  return cfg.dataRoot ? path.join(cfg.dataRoot, "inbox") : "";
}

export function queueDir(cfg = getConfig()): string {
  return cfg.dataRoot ? path.join(cfg.dataRoot, "queue") : "";
}

/** Durable people store (wiki-first when wikiRoot set). */
export function peopleDir(cfg = getConfig()): string {
  if (cfg.peopleRoot) return cfg.peopleRoot;
  if (cfg.wikiRoot) return path.join(cfg.wikiRoot, "people");
  return cfg.dataRoot ? path.join(cfg.dataRoot, "people") : "";
}

export function wikiRoot(cfg = getConfig()): string {
  return (cfg.wikiRoot || "").trim();
}

/** Final durable reports under LLM Wiki. Empty if wiki not configured. */
export function wikiReportsDir(cfg = getConfig()): string {
  if (cfg.wikiReportsRoot) return cfg.wikiReportsRoot;
  return cfg.wikiRoot ? path.join(cfg.wikiRoot, "reports") : "";
}

/** All roots that may hold report HTML (runtime out first, then wiki). */
export function reportScanDirs(cfg = getConfig()): string[] {
  const dirs: string[] = [];
  const o = outDir(cfg);
  const w = wikiReportsDir(cfg);
  if (o) dirs.push(o);
  if (w && w !== o) dirs.push(w);
  return dirs;
}

export function platformById(id: string): PlatformDef | undefined {
  return PLATFORMS.find((p) => p.id === id);
}

export function detectPlatformFromUrl(url: string): PlatformId {
  for (const p of PLATFORMS) {
    if (p.id === "custom") continue;
    if (p.matchUrl && p.matchUrl.test(url)) return p.id;
  }
  if (/^https?:\/\//i.test(url)) return "custom";
  return "custom";
}
