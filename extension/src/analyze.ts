import * as fs from "fs";
import * as https from "https";
import * as http from "http";
import * as path from "path";
import * as vscode from "vscode";
import {
  detectPlatformFromUrl,
  getConfig,
  inboxDir,
  peopleDir,
  PlatformId,
  platformById,
  PLATFORMS,
  queueDir,
  wikiReportsDir,
  wikiRoot,
} from "./config";
import {
  analysisPlatformForSite,
  getSite,
  materializeSiteAuth,
} from "./sites";
import { startJobFromRequest } from "./jobRunner";
import {
  findPriorEvidence,
  PriorHit,
  priorPathsForPrompt,
} from "./wikiStore";

export type AnalyzeMode = "auto" | "member" | "thread" | "profile";
export type AnalyzeDepth = "quick" | "full";

export interface AnalyzeLink {
  platform: string;
  handle?: string;
  url: string;
}

export interface AnalyzeRequest {
  input: string;
  platform: PlatformId | string;
  /** Registered site key (selection list id). */
  siteId?: string;
  /** Non-secret site snapshot for job/harvest. */
  site?: {
    id: string;
    label: string;
    baseUrl: string;
    loginUrl?: string;
    username?: string;
    kind: string;
    hasPassword?: boolean;
  };
  mode: AnalyzeMode;
  depth: AnalyzeDepth;
  note?: string;
  /** multi-platform handles/urls attached to same subject */
  links: AnalyzeLink[];
  customUrl?: string;
  /**
   * Optional single-post URL kept as trigger/context only.
   * When mode=member + author id, this must NOT replace the subject.
   */
  triggerUrl?: string;
  createdAt: string;
  date: string;
  parsed: ParsedTarget;
  seedPath?: string;
  queuePath: string;
  promptPath: string;
  /** Prior evidence paths (wiki + runtime) to merge on re-analyze. */
  prior?: PriorHit[];
  priorPaths?: string[];
}

export interface ParsedTarget {
  kind: "url" | "author" | "nick" | "handle" | "raw";
  platform: string;
  url?: string;
  board?: string;
  sn?: string;
  authorId?: string;
  nick?: string;
  handle?: string;
  display: string;
  /** Optional trigger thread when subject is a member id. */
  triggerUrl?: string;
  triggerBoard?: string;
  triggerSn?: string;
}

const BOARD_POST = /(?!)/;
/** Member axes — ID-only member jobs must cover all four (or mark n/a with evidence). */
export const MEMBER_AXES = [
  "posts (게시글 · 본인이 쓴 글)",
  "comments (댓글 · 본인이 쓴 댓글)",
  "liked_posts (공감글 · 본인이 공감한 글)",
  "liked_comments (공감댓글 · 본인이 공감한 댓글)",
] as const;

export function parseAnalyzeInput(
  raw: string,
  platformHint: PlatformId | string = "auto"
): ParsedTarget {
  const input = raw.trim();
  if (!input) {
    return { kind: "raw", platform: "x", display: "" };
  }

  // Full URL → detect platform
  if (/^https?:\/\//i.test(input)) {
    const plat =
      platformHint !== "auto" && platformHint
        ? String(platformHint)
        : detectPlatformFromUrl(input);
    return {
      kind: "url",
      platform: plat,
      url: input,
      handle: input,
      display: input.replace(/^https?:\/\/(www\.)?/i, "").slice(0, 64),
    };
  }

  const plat =
    platformHint && platformHint !== "auto"
      ? String(platformHint)
       : "x";


  // Social handle → profile URL
  const def = platformById(plat as PlatformId);
  if (def?.urlFromHandle) {
    const url = def.urlFromHandle(input);
    return {
      kind: "handle",
      platform: plat,
      handle: input.replace(/^@/, ""),
      url,
      display: `${def.label}:${input}`,
    };
  }

  // custom platforms from settings
  const custom = getConfig().customPlatforms.find((c) => c.id === plat);
  if (custom) {
    const url = custom.urlTemplate.replace(/\{handle\}/gi, encodeURIComponent(input.replace(/^@/, "")));
    return {
      kind: "handle",
      platform: plat,
      handle: input,
      url,
      display: `${custom.label}:${input}`,
    };
  }

  return { kind: "raw", platform: plat, display: input, handle: input };
}

function todayKst(): string {
  try {
    return new Intl.DateTimeFormat("en-CA", {
      timeZone: "Asia/Seoul",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(new Date());
  } catch {
    return new Date().toISOString().slice(0, 10);
  }
}

function stamp(): string {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return (
    `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}_` +
    `${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`
  );
}

function ensureDir(p: string): void {
  fs.mkdirSync(p, { recursive: true });
}

function fetchText(url: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const lib = url.startsWith("https") ? https : http;
    const req = lib.get(
      url,
      {
        headers: {
          "User-Agent":
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
          Accept: "text/html,application/xhtml+xml",
        },
        timeout: 25000,
      },
      (res) => {
        if (
          res.statusCode &&
          res.statusCode >= 300 &&
          res.statusCode < 400 &&
          res.headers.location
        ) {
          const next = res.headers.location.startsWith("http")
            ? res.headers.location
            : new URL(res.headers.location, url).toString();
          fetchText(next).then(resolve, reject);
          return;
        }
        if (!res.statusCode || res.statusCode >= 400) {
          reject(new Error(`HTTP ${res.statusCode} for ${url}`));
          res.resume();
          return;
        }
        const chunks: Buffer[] = [];
        res.on("data", (c) => chunks.push(c));
        res.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
      }
    );
    req.on("error", reject);
    req.on("timeout", () => {
      req.destroy();
      reject(new Error("timeout"));
    });
  });
}

function normalizeLinks(
  links: { platform?: string; handle?: string; url?: string }[] | undefined,
  primary: ParsedTarget
): AnalyzeLink[] {
  const out: AnalyzeLink[] = [];
  const seen = new Set<string>();

  const add = (platform: string, handle: string | undefined, url: string) => {
    const key = url.toLowerCase();
    if (!url || seen.has(key)) return;
    seen.add(key);
    out.push({ platform, handle, url });
  };

  if (primary.url) {
    add(primary.platform, primary.handle || primary.authorId || primary.nick, primary.url);
  }

  for (const L of links || []) {
    const plat = (L.platform || "custom").toLowerCase();
    let url = (L.url || "").trim();
    let handle = (L.handle || "").trim();
    if (!url && handle) {
      const def = platformById(plat as PlatformId);
      if (def?.urlFromHandle) url = def.urlFromHandle(handle);
      else {
        const custom = getConfig().customPlatforms.find((c) => c.id === plat);
        if (custom) {
          url = custom.urlTemplate.replace(/\{handle\}/gi, encodeURIComponent(handle.replace(/^@/, "")));
        }
      }
    }
    if (!url && handle && /^https?:\/\//i.test(handle)) {
      url = handle;
      handle = "";
    }
    if (url) add(plat, handle || undefined, url);
  }

  return out;
}

function memberScopeBlock(req: AnalyzeRequest): string[] {
  const p = req.parsed;
  if (req.mode !== "member" || !p.authorId) {
    return [];
  }
  const trigger =
    req.triggerUrl || p.triggerUrl || (p.kind === "url" ? p.url : undefined);
  return [
    "",
    "MEMBER SCOPE (ID-only — not a single post)",
    `- Subject author_id: ${p.authorId}${p.nick ? ` · nick: ${p.nick}` : ""}`,
    "- Operator entered the member id (not a post URL as the subject).",
    "- You MUST collect and analyze this person across ALL four axes (site-parity honesty):",
    ...MEMBER_AXES.map((a, i) => `  ${i + 1}) ${a}`),
    "- Do NOT stop after one trigger thread. A single post URL is optional context only.",
    trigger
      ? `- Optional trigger URL (context only, not the whole job): ${trigger}`
      : "- Optional trigger URL: (none)",
    "- Collect path (lawful / agent Edge session when login required):",
    "  · posts: search/v2 or board?sk=id&sv={author_id} (+ multi-board)",
    "  · comments: search/v2 or board?sk=commenter&sv={author_id}",
    "  · liked posts / liked comments: member mypage / 공감 surfaces if available; else document exact blocker and mark axis n/a with evidence",
    "  · helper: scripts/harvest helper (if available) {author_id} {nick}  (polite pacing built-in)",
    "- Write COLLECTION_HONESTY with posts / comments / liked_posts / liked_comments counts (or n/a + why).",
    "- Presence of tab label text ≠ collected. Incomplete axis ⇒ say so; do not claim full member done.",
    req.depth === "quick"
      ? "- Depth=quick still requires all four axes sampled (smaller page caps OK); do not drop an axis silently."
      : "- Depth=full: page deeper on each axis; still document platform caps.",
  ];
}

/** Ban / rate-limit avoidance — always when platform is member-style. */
function harvestSafetyBlock(req: AnalyzeRequest): string[] {
  const cfg = getConfig();
  const polite = cfg.harvestPolite !== false;
  const minD = cfg.harvestDelayMinSec ?? 2.8;
  const maxD = Math.max(minD + 0.5, cfg.harvestDelayMaxSec ?? 6.5);
  const maxFetch =
    req.depth === "quick"
      ? Math.min(cfg.harvestMaxFetch ?? 40, 24)
      : cfg.harvestMaxFetch ?? 40;
  const every = cfg.harvestBurstEvery ?? 6;
  const burst = cfg.harvestBurstPauseSec ?? 10;

  return [
    "",
    "HARVEST SAFETY / RATE LIMITS (all sites — non-negotiable)",
    "- X and major SNS rate-limit (429). Prefer official API/export when available.",
    "- Large accounts (demo handle form @elonmusk): depth=quick; do not full-crawl demos.",
    "- On 429/captcha/block: stop, backoff, reuse prior raw. Do not hammer.",
    "- Operator uses a real logged-in browser profile. You are NOT a headless bot farm.",
    "- NEVER parallel-fetch target pages. One page/request at a time, sequential only.",
    polite
      ? `- Between navigations: sleep random ${minD}–${maxD}s (env KAMPFF_HARVEST_MIN/MAX_DELAY_MS (legacy KAMPFF_CLIEN_* ok)).`
      : "- harvestPolite=false: still avoid sub-second hammering; prefer ≥1.2s gaps.",
    `- Every ${every} page loads: longer pause ~${burst}s+ and small human scroll.`,
    `- Cap fresh HTML fetches ≈ ${maxFetch}. Prefer PRIOR EVIDENCE / existing inbox/raw over re-download.`,
    "- If 429, captcha, '비정상', empty challenge, forced login, or sudden empty search: STOP.",
    "  Back off 10–20+ minutes, write blocker into COLLECTION_HONESTY. Do not retry in a tight loop.",
    "- Prefer harvest helpers with polite pacing; never sub-second loops.",
    "  Do NOT use tight loops (e.g. 0.2s sleeps) — robotic on any site.",
    "- No multi-tab storms, no curl/wget floods, no stripped User-Agent spam.",
    "- Job control file KAMPFF_JOB_CONTROL: action=cancel → exit cleanly; action=pause → wait until run.",
    "- If operator hits 일시정지/중단 in the extension, respect process stop — do not fight it.",
  ];
}

function buildHermesPrompt(req: AnalyzeRequest): string {
  const cfg = getConfig();
  const p = req.parsed;
  const isMemberJob = req.mode === "member" && !!p.authorId;
  const depthNote =
    req.depth === "quick"
      ? isMemberJob
        ? "Depth=quick: member axes required (smaller caps OK); no silent axis skip."
        : "Depth=quick: public/seed first; no bulk private harvest unless needed."
      : "Depth=full: full lawful collect + cross-platform correlation when links present.";

  const linkLines = req.links.map(
    (L, i) => `  ${i + 1}. [${L.platform}] ${L.handle ? L.handle + " → " : ""}${L.url}`
  );

  const targetLines: string[] = [
      `- primary platform: ${req.platform}`,
      req.siteId ? `- siteId: ${req.siteId}` : "",
      req.site?.baseUrl ? `- site baseUrl: ${req.site.baseUrl}` : "",
      req.site?.username ? `- site login user: ${req.site.username}` : "",
      `- input: ${req.input}`,
      `- mode: ${req.mode}`,
    ].filter(Boolean);
  if (isMemberJob) {
    targetLines.push(`- subject kind: member (author_id) — full 4-axis dossier`);
    targetLines.push(`- author_id: ${p.authorId}`);
    if (p.nick) targetLines.push(`- nick: ${p.nick}`);
    const trig = req.triggerUrl || p.triggerUrl;
    if (trig) {
      targetLines.push(`- trigger URL (context only): ${trig}`);
      if (p.triggerBoard && p.triggerSn) {
        targetLines.push(`- trigger board/sn: ${p.triggerBoard}/${p.triggerSn}`);
      }
    }
  } else {
    if (p.url) targetLines.push(`- primary URL: ${p.url}`);
    if (p.board && p.sn) targetLines.push(`- board/sn: ${p.board}/${p.sn}`);
    if (p.authorId) targetLines.push(`- author_id: ${p.authorId}`);
    if (p.nick) targetLines.push(`- nick: ${p.nick}`);
  }
  if (p.handle) targetLines.push(`- handle: ${p.handle}`);
  if (req.customUrl) targetLines.push(`- custom URL: ${req.customUrl}`);
  if (req.seedPath) targetLines.push(`- seed HTML: ${req.seedPath}`);
  targetLines.push(`- queue: ${req.queuePath}`);
  targetLines.push(`- KAMPFF_DATA (runtime scratch): ${cfg.dataRoot}`);
  targetLines.push(`- people store (durable): ${peopleDir(cfg)}`);
  if (wikiRoot(cfg)) {
    targetLines.push(`- LLM Wiki shelf: ${wikiRoot(cfg)}`);
    targetLines.push(`- wiki reports (final): ${wikiReportsDir(cfg)}`);
  }
  targetLines.push(`- date folder: ${req.date}`);

  const prior = req.prior || [];
  if (prior.length) {
    targetLines.push(`- prior evidence files: ${prior.length}`);
  }

  const lensLines: string[] = [
    "- L1–L5 + MBTI + CIA-SAT defaults for community.",
  ];
  if (cfg.promptIncludeClinical) {
    lensLines.push(
      "- clinical_psych ON (public-text formulation only — NOT diagnosis)."
    );
  }
  if (cfg.promptIncludeAuthorship) {
    lensLines.push(
      "- After analyze: run authorship_integrity.py on target (+ cohort if org/ID-trade suspected)."
    );
  }
  if (cfg.promptIncludeAccumulate) {
    lensLines.push(
      `- accumulate_person.py → ${peopleDir(cfg)}/{platform}/{id}/ (stack same id; read NOTES first if exists).`
    );
  }

  const priorBlock =
    prior.length > 0
      ? [
          "",
          "PRIOR EVIDENCE (merge — do not discard)",
          "- Read these first. Treat as earlier pass on the same subject.",
          "- Update judgments with new collect; keep stable history; note drift explicitly.",
          "- Prefer vault people NOTES / history over stale one-off HTML when they conflict on biography facts.",
          ...prior.slice(0, 24).map((h, i) => {
            const kind = h.kind || "other";
            const label = h.label ? ` (${h.label})` : "";
            return `  ${i + 1}. [${kind}]${label} ${h.path}`;
          }),
        ]
      : [
          "",
          "PRIOR EVIDENCE",
          "- None found under wiki people/reports or runtime out/ for this id.",
        ];

  const skillHint = isMemberJob
    ? "Load skills: kampff, community-member-dossier / community-member-dossier. Mode=member with author_id ⇒ full 4-axis member pipeline (posts/comments/liked_posts/liked_comments)."
    : "Load skills: kampff-ops, kampff (if available), community-member-dossier / community-thread-network as appropriate.";

  return [
    "You are running a Kampff multi-source analysis job from the VS Code extension queue.",
    skillHint,
    "For Facebook / X / Instagram / Reddit / LinkedIn / custom: lawful OSINT only — public pages, no bypass of auth/paywall, no credential stuffing.",
    "",
    "TARGET",
    ...targetLines,
    `- ${depthNote}`,
    req.note ? `- operator note: ${req.note}` : "",
    ...memberScopeBlock(req),
        ...harvestSafetyBlock(req),
        "",
        "LINKED PROFILES / URLS",
    ...(linkLines.length ? linkLines : ["  (none beyond primary)"]),
    ...priorBlock,
    "",
    "LENSES / POST-PROCESS",
    ...lensLines,
    "",
    "RULES",
    "- OP id = nick or by-author data-author-id only. NEVER full-HTML id ⇒ OP.",
    "- Cross-platform: separate identity tiers CONFIRMED/PROBABLE/SPECULATIVE/NOT FOUND.",
    "- Same-person claims need evidence; do not merge accounts on weak nick collision alone.",
    "- Write analysis.json + HTML via render_kampff_report.py under KAMPFF_DATA/out (runtime).",
    "- People accumulate + final copies belong in the durable people store / wiki reports paths above.",
    isMemberJob
      ? "- Honesty: posts / comments / liked_posts / liked_comments (four axes). No public dump of private harvest / session cookies."
      : "- Honesty triad; no public dump of private harvest / session cookies.",
    "",
    "DELIVER",
    `1) inbox/${req.date}/ bundle + raw as needed (runtime dataRoot)`,
    isMemberJob
      ? `2) COLLECTION_HONESTY covering 게시글/댓글/공감글/공감댓글 for author_id=${p.authorId}`
      : undefined,
    `3) out/${req.date}-…-analysis.json + …-report.html (runtime; extension will promote to wiki)`,
    `4) people accumulate under: ${peopleDir(cfg)}/{platform}/{id}/ when enabled`,
    "5) Absolute paths when done.",
  ]
    .filter(Boolean)
    .join("\n");
}

export async function submitAnalyze(opts: {
  input: string;
  platform?: PlatformId | string;
  mode?: AnalyzeMode;
  depth?: AnalyzeDepth;
  note?: string;
  links?: { platform?: string; handle?: string; url?: string }[];
  customUrl?: string;
  /** Explicit author id (preferred subject when set). */
  authorId?: string;
  nick?: string;
  /**
   * Optional post URL. Used as subject only when mode=thread / no author id.
   * For member jobs it becomes trigger context only.
   */
  triggerUrl?: string;
}): Promise<AnalyzeRequest> {
  const cfg = getConfig();
  if (!cfg.dataRoot) throw new Error("kampff.dataRoot is empty");
  const inputRaw = (opts.input || "").trim();
  const customUrl = (opts.customUrl || "").trim();
  const explicitId = (opts.authorId || "").trim().split(/[\s|,]+/)[0] || "";
  const explicitNick = (opts.nick || "").trim();
  const triggerUrlIn = (opts.triggerUrl || "").trim();

  if (!inputRaw && !customUrl && !explicitId && !(opts.links && opts.links.length) && !triggerUrlIn) {
    throw new Error("empty input — need handle/URL or linked profiles");
  }

  const platformHint = opts.platform || cfg.defaultPlatform || "x";
      const registered = getSite(String(platformHint));
      const boardLike = false;
      const adapterPlatform = analysisPlatformForSite(
        registered,
        String(platformHint)
      );
      let mode: AnalyzeMode = opts.mode || "auto";
      const depth: AnalyzeDepth = opts.depth || "quick";

      // Soft warn only: agent Edge profile login is enough for harvest.
          // Hard-block was killing Go when hasPassword=false even after edge login.
          if (
            boardLike &&
            mode !== "thread" &&
            registered &&
            !registered.hasPassword &&
            !(registered.username || "").trim()
          ) {
            void vscode.window.showWarningMessage(
              `Kampff: "${registered.label || registered.id}" 사이트 비밀번호 없음 → agent Edge 세션으로 수집 시도. 실패 시 사이트 등록에 ID/비번.`
            );
          }

      // Prefer explicit author id as subject for member-style member analysis.
    // Do NOT let a leftover post URL become the primary subject when id is present.
    let primaryInput = inputRaw;
    if (
      boardLike &&
      explicitId &&
      !/^https?:\/\//i.test(explicitId)
    ) {
      primaryInput = explicitNick ? `${explicitId} ${explicitNick}` : explicitId;
    } else if (!primaryInput) {
      primaryInput =
        customUrl ||
        triggerUrlIn ||
        opts.links?.[0]?.url ||
        opts.links?.[0]?.handle ||
        explicitId ||
        "";
    }

    let parsed = parseAnalyzeInput(
      primaryInput,
      platformHint === "auto" ? "auto" : adapterPlatform
    );

    // Overlay explicit id/nick when parse only got a URL or raw free text.
    if (explicitId && boardLike) {
      if (!parsed.authorId || parsed.kind === "url") {
        parsed = {
          ...parsed,
          kind: "author",
          platform: adapterPlatform,
          authorId: explicitId,
          nick: explicitNick || parsed.nick,
          display: explicitNick
            ? `${explicitId} (${explicitNick})`
            : explicitId,
        };
      } else if (explicitNick && !parsed.nick) {
        parsed = {
          ...parsed,
          nick: explicitNick,
          display: `${parsed.authorId} (${explicitNick})`,
        };
      }
    } else if (explicitNick && false && !parsed.nick) {
      parsed = { ...parsed, nick: explicitNick };
    }

    // Keep adapter platform on parsed for people/harvest paths.
    if (registered && adapterPlatform) {
      parsed = { ...parsed, platform: adapterPlatform };
    }

  // Attach optional trigger post URL without replacing member subject.
  let triggerUrl = "";
  if (triggerUrlIn) {
    triggerUrl = triggerUrlIn;
  } else if (
    inputRaw &&
    /^https?:\/\//i.test(inputRaw) &&
    parsed.authorId &&
    mode !== "thread"
  ) {
    // input was URL but we forced author subject elsewhere — keep as trigger
    triggerUrl = inputRaw;
  }

  if (triggerUrl) {
    const tm = triggerUrl.match(BOARD_POST);
    if (tm) {
      parsed = {
        ...parsed,
        triggerUrl: triggerUrl,
        triggerBoard: tm[1],
        triggerSn: tm[2],
      };
      triggerUrl = parsed.triggerUrl || triggerUrl;
    } else {
      parsed = { ...parsed, triggerUrl };
    }
  }

  // Member subject = author id. Strip primary post url so normalizeLinks won't treat it as subject.
  if (parsed.authorId && parsed.kind === "author") {
    const keepTrigger = parsed.triggerUrl || triggerUrl;
    parsed = {
      ...parsed,
      url: undefined,
      board: undefined,
      sn: undefined,
      triggerUrl: keepTrigger || parsed.triggerUrl,
    };
  }

  if (mode === "auto") {
      if (false && parsed.authorId) mode = "member";
      else if (false && parsed.kind === "url") mode = "thread";
            else mode = "profile";
    }

    // Member-style + author id + mode member is the 4-axis path even if UI left mode=thread by mistake
    // when only id was filled (no url). Keep thread only when no author id or explicit thread+url.
    if (
      false &&
      parsed.authorId &&
      mode === "thread" &&
      !triggerUrl &&
      !parsed.url
    ) {
      mode = "member";
    }

  // merge custom URL into links
  const linkIn = [...(opts.links || [])];
  if (customUrl) {
    linkIn.push({ platform: "custom", url: customUrl });
  }

  // For member jobs, do not inject trigger post as primary link subject via primary.url
  const links = normalizeLinks(linkIn, parsed);
  const date = todayKst();
  const id = stamp();
  const qDir = queueDir(cfg);
  ensureDir(qDir);
  ensureDir(path.join(inboxDir(cfg), date, "raw", "seed"));

  let seedPath: string | undefined;
  // Seed: trigger thread if any, else post subject for thread mode.
  const seedUrl =
    mode === "thread" && parsed.url
      ? parsed.url
      : parsed.triggerUrl || triggerUrl || undefined;
  const seedMatch = seedUrl ? seedUrl.match(BOARD_POST) : null;
  if (seedMatch) {
    try {
      const seedCanon = (seedUrl || "");
      const html = await fetchText(seedCanon);
      seedPath = path.join(
        inboxDir(cfg),
        date,
        "raw",
        "seed",
        `${seedMatch[1]}_${seedMatch[2]}.html`
      );
      fs.writeFileSync(seedPath, html, "utf8");
    } catch (e) {
      seedPath = undefined;
      void vscode.window.setStatusBarMessage(
        `Kampff: seed fetch failed (${e instanceof Error ? e.message : e}) — queued anyway`,
        5000
      );
    }
  }

  const queuePath = path.join(qDir, `${id}-request.json`);
  const promptPath = path.join(qDir, `${id}-hermes-prompt.txt`);

  const subjectId =
    parsed.authorId || parsed.handle || parsed.nick || primaryInput.split(/\s+/)[0] || "";
  const subjectNick = parsed.nick && parsed.nick !== subjectId ? parsed.nick : undefined;
  const prior = findPriorEvidence({
    platform: parsed.platform,
    id: subjectId,
    nick: subjectNick || parsed.nick,
    cfg,
  });
  const priorPaths = priorPathsForPrompt(prior);

  const siteSnap = registered
      ? {
          id: registered.id,
          label: registered.label,
          baseUrl: registered.baseUrl,
          loginUrl: registered.loginUrl,
          username: registered.username || undefined,
          kind: registered.kind,
          hasPassword: !!registered.hasPassword,
        }
      : undefined;

    const req: AnalyzeRequest = {
      input: primaryInput,
      platform: adapterPlatform || parsed.platform,
      siteId: registered?.id || String(platformHint),
      site: siteSnap,
      mode,
      depth,
      note: opts.note,
      links,
      customUrl: customUrl || undefined,
      triggerUrl: parsed.triggerUrl || triggerUrl || undefined,
      createdAt: new Date().toISOString(),
      date,
      parsed,
      seedPath,
      queuePath,
      promptPath,
      prior,
      priorPaths,
    };

    fs.writeFileSync(queuePath, JSON.stringify(req, null, 2), "utf8");
    fs.writeFileSync(promptPath, buildHermesPrompt(req), "utf8");
    // Job-local auth file (password never lands in request.json / logs).
    if (registered && cfg.dataRoot) {
      try {
        await materializeSiteAuth(registered.id, cfg.dataRoot);
      } catch {
        /* ignore */
      }
    }
    fs.writeFileSync(
      path.join(qDir, "LATEST.txt"),
      [
        `created: ${req.createdAt}`,
        `platform: ${req.platform}`,
        `siteId: ${req.siteId || ""}`,
        req.site?.baseUrl ? `siteUrl: ${req.site.baseUrl}` : "",
        `input: ${req.input}`,
        `subject: ${subjectId}${subjectNick ? " / " + subjectNick : ""}`,
        `links: ${links.length}`,
        ...links.map((L) => `  - ${L.platform}: ${L.url}`),
        `mode: ${mode} depth: ${depth}`,
        mode === "member" && parsed.authorId && false
          ? `member_axes: posts, comments, liked_posts, liked_comments`
          : "",
        req.triggerUrl ? `trigger: ${req.triggerUrl}` : "trigger: (none)",
        `queue: ${queuePath}`,
        `prompt: ${promptPath}`,
        seedPath ? `seed: ${seedPath}` : "seed: (none)",
        `people: ${peopleDir(cfg)}`,
        wikiRoot(cfg) ? `wiki: ${wikiRoot(cfg)}` : "wiki: (none)",
        `prior: ${prior.length}`,
        ...priorPaths.slice(0, 12).map((p) => `  - ${p}`),
      ]
        .filter(Boolean)
        .join("\n"),
      "utf8"
    );

  await launchAfterQueue(req);
  return req;
}

async function launchAfterQueue(req: AnalyzeRequest): Promise<void> {
  const cfg = getConfig();
  // none = files only (power users). Everything else = one-click job + progress.
  if (cfg.analyzeLaunch === "none") return;

  if (cfg.analyzeLaunch === "terminal") {
    const term = vscode.window.createTerminal({
      name: "Kampff · Analyze",
      cwd: cfg.skillsDevRoot || cfg.dataRoot,
    });
    term.show(false);
    const py = shellPy(cfg.pythonPath);
    const helper = path.join(cfg.dataRoot, "queue", "_analyze_helper.py");
    writeAnalyzeHelper(helper);
    term.sendText(`${py} "${helper}" "${req.queuePath}" "${cfg.skillsDevRoot}"`);
    return;
  }

  // auto | hermes → full job (Hermes + poll analysis/report + open)
  await startJobFromRequest(req);
}

function shellPy(pythonPath: string): string {
  return pythonPath.includes(" ") ? `"${pythonPath}"` : pythonPath;
}

function writeAnalyzeHelper(p: string): void {
  ensureDir(path.dirname(p));
  fs.writeFileSync(
    p,
    `#!/usr/bin/env python3
from __future__ import annotations
import json, sys
from pathlib import Path
qpath = Path(sys.argv[1])
skills = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(r"C:\\prjs\\kampff-skills-dev")
req = json.loads(qpath.read_text(encoding="utf-8"))
p = req.get("parsed") or {}
print("=" * 60)
print("KAMPFF ANALYZE QUEUED")
print("=" * 60)
print("platform:", req.get("platform"))
print("input   :", req.get("input"))
print("mode    :", req.get("mode"), " depth:", req.get("depth"))
print("links   :", len(req.get("links") or []))
for L in req.get("links") or []:
    print("  -", L.get("platform"), L.get("url"))
print("queue   :", req.get("queuePath"))
print("prompt  :", req.get("promptPath"))
print("seed    :", req.get("seedPath") or "(none)")
print()
print("Next:")
print("  hermes chat -q @prompt   OR  kampff.analyzeLaunch=hermes")
print("  prompt:", req.get("promptPath"))
aid = p.get("authorId") or ""
nick = p.get("nick") or ""
harv = skills / "scripts" / "harvest helper (if available)"
if aid:
    print(f"  python {harv} {aid} {nick!r}")
print("=" * 60)
`,
    "utf8"
  );
}

export async function analyzeFromPalette(): Promise<void> {
  const { listTargets } = await import("./catalog");
  const cfg = getConfig();

  const platItems = [
    ...PLATFORMS.map((p) => ({
      label: p.label,
      description: p.id,
      id: p.id as string,
    })),
    ...getConfig().customPlatforms.map((c) => ({
      label: c.label,
      description: c.id,
      id: c.id,
    })),
  ];

  const plat = await vscode.window.showQuickPick(platItems, {
    title: "Kampff · 1 Site",
    placeHolder: "Select platform / site",
    ignoreFocusOut: true,
  });
  if (!plat) return;

  const targets = listTargets();
  const filtered =
    plat.id === "x"
      ? targets.filter((t) => t.platform === "x")
      : targets;

  type IdPick = vscode.QuickPickItem & {
    id?: string;
    nick?: string;
    manual?: boolean;
  };

  const idItems: IdPick[] = [
    {
      label: "$(edit) Type ID / URL…",
      description: "manual",
      manual: true,
    },
    ...filtered.map((t) => ({
      label: t.id,
      description: [t.nick, t.source, t.date].filter(Boolean).join(" · "),
      detail: t.path,
      id: t.id,
      nick: t.nick,
    })),
  ];

  const picked = await vscode.window.showQuickPick(idItems, {
    title: `Kampff · 2 Target ID (${plat.label})`,
    placeHolder: filtered.length
      ? `${filtered.length} known — pick or type`
      : "No known ids — choose Type…",
    matchOnDescription: true,
    matchOnDetail: true,
    ignoreFocusOut: true,
  });
  if (!picked) return;

  let input = "";
  if (picked.manual) {
    const typed = await vscode.window.showInputBox({
      title: `Kampff · ${plat.label} ID`,
      prompt: "Handle / URL / author id",
      placeHolder: platformById(plat.id as PlatformId)?.placeholder || "https://…",
      ignoreFocusOut: true,
    });
    if (typed === undefined) return;
    input = typed;
  } else if (picked.id) {
    input =
      plat.id === "x" && picked.nick
        ? `${picked.id} ${picked.nick}`
        : picked.id;
  }

  const more = await vscode.window.showQuickPick(
    [
      { label: "Analyze now", id: "go" },
      { label: "Add linked profiles first…", id: "links" },
    ],
    { title: "Links", ignoreFocusOut: true }
  );

  const links: { platform: string; handle?: string; url?: string }[] = [];
  if (more?.id === "links") {
    for (const p of ["facebook", "x", "instagram", "reddit", "linkedin", "custom"]) {
      const v = await vscode.window.showInputBox({
        title: `Link · ${p} (empty = skip)`,
        placeHolder: p === "custom" ? "https://…" : "@handle or URL",
        ignoreFocusOut: true,
      });
      if (v?.trim()) {
        if (/^https?:\/\//i.test(v.trim())) {
          links.push({ platform: p, url: v.trim() });
        } else {
          links.push({ platform: p, handle: v.trim() });
        }
      }
    }
  }

  const modePick = await vscode.window.showQuickPick(
    [
      { label: "auto", description: cfg.defaultMode === "auto" ? "default" : "" },
      { label: "profile" },
      { label: "thread" },
      { label: "member" },
    ],
    {
      title: "Mode",
      ignoreFocusOut: true,
      placeHolder: `default: ${cfg.defaultMode}`,
    }
  );
  const depthPick = await vscode.window.showQuickPick(
    [
      { label: "quick", description: cfg.defaultDepth === "quick" ? "default" : "" },
      { label: "full", description: cfg.defaultDepth === "full" ? "default" : "" },
    ],
    {
      title: "Depth",
      ignoreFocusOut: true,
      placeHolder: `default: ${cfg.defaultDepth}`,
    }
  );

  try {
    const req = await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: "Kampff: queueing analysis…",
        cancellable: false,
      },
      async () =>
        submitAnalyze({
          input: input || "",
          platform: plat.id,
          mode: (modePick?.label as AnalyzeMode) || cfg.defaultMode || "auto",
          depth: (depthPick?.label as AnalyzeDepth) || cfg.defaultDepth || "quick",
          links,
        })
    );
    if (cfg.autoOpenPrompt) {
      const doc = await vscode.workspace.openTextDocument(req.promptPath);
      await vscode.window.showTextDocument(doc, { preview: true });
    }
    if (!cfg.notifyOnQueue) return;
    const choice = await vscode.window.showInformationMessage(
      `Kampff queued: ${req.parsed.display || req.input} · ${req.links.length} link(s)`,
      "Open Prompt",
      "Open Queue",
      "Analyze view"
    );
    if (choice === "Open Prompt") {
      const doc = await vscode.workspace.openTextDocument(req.promptPath);
      await vscode.window.showTextDocument(doc, { preview: true });
    } else if (choice === "Open Queue") {
      await vscode.commands.executeCommand(
        "revealFileInOS",
        vscode.Uri.file(req.queuePath)
      );
    } else if (choice === "Analyze view") {
      await vscode.commands.executeCommand("kampff.analyze.focus");
    }
  } catch (e) {
    void vscode.window.showErrorMessage(
      `Kampff analyze failed: ${e instanceof Error ? e.message : e}`
    );
  }
}
