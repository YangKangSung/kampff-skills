/**
 * Bundle → graph.json → graph.html (relation layer).
 * With an ID: ego graph from that harvest (posts / comments / likes).
 * Without an ID: board bundle. Not the Distance Desk.
 */
import * as fs from "fs";
import * as path from "path";
import { spawn } from "child_process";
import * as vscode from "vscode";
import { getConfig, inboxDir, outDir } from "./config";

function spawnPy(script: string, args: string[]): Promise<void> {
  const cfg = getConfig();
  if (!cfg.skillsDevRoot) {
    throw new Error("skillsDevRoot 없음 — Kampff: Setup에서 이 repo 루트를 지정하세요");
  }
  const full = path.join(cfg.skillsDevRoot, "scripts", script);
  if (!fs.existsSync(full)) {
    throw new Error(`graph script 없음: ${full}`);
  }
  const py = cfg.pythonPath || "python";
  return new Promise<void>((resolve, reject) => {
    const child = spawn(py, [full, ...args], {
      cwd: cfg.skillsDevRoot,
      windowsHide: true,
      env: { ...process.env, KAMPFF_LANG: cfg.uiLanguage },
    });
    let err = "";
    child.stderr.on("data", (d) => (err += String(d)));
    child.stdout.on("data", (d) => (err += String(d)));
    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) resolve();
      else reject(new Error(err.trim() || `${script} exit ${code}`));
    });
  });
}

export function sampleBundlePath(): string {
  const root = getConfig().skillsDevRoot;
  return root ? path.join(root, "docs", "sample-relation-bundle.json") : "";
}

export function sampleGraphHtmlPath(): string {
  const root = getConfig().skillsDevRoot;
  return root ? path.join(root, "docs", "sample-graph.html") : "";
}

export function graphPathsForSeed(
  seed: string,
  harvestDate: string
): { bundle: string; json: string; html: string } {
  const out = outDir();
  const tag = `${harvestDate}-${seed}`;
  const base = out || path.join(inboxDir() || "", harvestDate);
  if (base) fs.mkdirSync(base, { recursive: true });
  return {
    bundle: path.join(base, `${tag}-relation-bundle.json`),
    json: path.join(base, `${tag}-graph.json`),
    html: path.join(base, `${tag}-graph.html`),
  };
}

export function graphPathsFromBundle(bundlePath: string): { json: string; html: string } {
  if (/sample-relation-bundle\.json$/i.test(bundlePath)) {
    const out = outDir();
    const dir = out || path.dirname(bundlePath);
    if (out) fs.mkdirSync(out, { recursive: true });
    return {
      json: path.join(dir, "sample-graph.json"),
      html: path.join(dir, "sample-graph.html"),
    };
  }
  const out = outDir();
  const day = path.basename(path.dirname(bundlePath));
  const stem = path.basename(bundlePath, ".json");
  const tag =
    stem === "bundle" || stem === "bundle.json"
      ? day
      : `${day}-${stem.replace(/^bundle-?/i, "") || "board"}`;
  const base = out || path.dirname(bundlePath);
  return {
    json: path.join(base, `${tag}-graph.json`),
    html: path.join(base, `${tag}-graph.html`),
  };
}

function bundleHasPerson(bundlePath: string, id: string): boolean {
  try {
    const j = JSON.parse(fs.readFileSync(bundlePath, "utf8")) as {
      people?: Array<{ id?: string }>;
    };
    return (j.people || []).some((p) => String(p.id || "") === id);
  } catch {
    return false;
  }
}

function personCount(bundlePath: string): number {
  try {
    const j = JSON.parse(fs.readFileSync(bundlePath, "utf8")) as {
      people?: unknown[];
    };
    return (j.people || []).length;
  } catch {
    return 0;
  }
}

/** Newest inbox date/raw/id folder that has posts HTML or a relation bundle. */
export function findLatestHarvestRaw(targetId?: string): string | undefined {
  const id = (targetId || "").trim();
  if (!id) return undefined;
  const inbox = inboxDir();
  if (!inbox || !fs.existsSync(inbox)) return undefined;
  const hits: Array<{ p: string; mt: number }> = [];
  const idLower = id.toLowerCase();
  for (const date of fs.readdirSync(inbox)) {
    const rawRoot = path.join(inbox, date, "raw");
    let names: string[] = [];
    try {
      names = fs.readdirSync(rawRoot);
    } catch {
      continue;
    }
    for (const name of names) {
      const raw = path.join(rawRoot, name);
      try {
        if (!fs.statSync(raw).isDirectory()) continue;
      } catch {
        continue;
      }
      let nickHit = name.toLowerCase() === idLower;
      if (!nickHit) {
        try {
          const st = JSON.parse(fs.readFileSync(path.join(raw, "STATE.json"), "utf8")) as {
            author_id?: string;
            nick?: string;
          };
          nickHit =
            String(st.author_id || "").toLowerCase() === idLower ||
            String(st.nick || "") === id;
        } catch {
          /* ignore */
        }
      }
      if (!nickHit) continue;
      const posts = path.join(raw, "posts");
      let has = false;
      try {
        has =
          fs.existsSync(path.join(raw, "relation_bundle.json")) ||
          fs.existsSync(path.join(raw, "thread_actors.json")) ||
          (fs.existsSync(posts) &&
            fs.readdirSync(posts).some((f) => f.endsWith(".html")));
      } catch {
        has = false;
      }
      if (!has) continue;
      try {
        hits.push({ p: raw, mt: fs.statSync(raw).mtimeMs });
      } catch {
        /* ignore */
      }
    }
  }
  hits.sort((a, b) => b.mt - a.mt);
  return hits[0]?.p;
}

/** Newest inbox bundle*.json; prefer one that contains targetId. */
export function findLatestBundle(targetId?: string): string | undefined {
  const inbox = inboxDir();
  if (!inbox || !fs.existsSync(inbox)) return undefined;
  const id = (targetId || "").trim();
  const found: Array<{ p: string; mt: number; hit: boolean; n: number }> = [];
  for (const date of fs.readdirSync(inbox)) {
    const day = path.join(inbox, date);
    try {
      if (!fs.statSync(day).isDirectory()) continue;
    } catch {
      continue;
    }
    for (const f of fs.readdirSync(day)) {
      if (!f.startsWith("bundle") || !f.endsWith(".json")) continue;
      const p = path.join(day, f);
      try {
        const st = fs.statSync(p);
        if (!st.isFile()) continue;
        found.push({
          p,
          mt: st.mtimeMs,
          hit: id ? bundleHasPerson(p, id) || f.includes(id) : false,
          n: personCount(p),
        });
      } catch {
        /* ignore */
      }
    }
  }
  if (!found.length) return undefined;
  const hits = id ? found.filter((x) => x.hit) : [];
  const pool = hits.length ? hits : found.filter((x) => x.n >= 2);
  const use = (pool.length ? pool : found).sort((a, b) => b.mt - a.mt);
  return use[0]?.p;
}

export function findLatestGraphHtml(targetId?: string): string | undefined {
  const out = outDir();
  if (!out || !fs.existsSync(out)) return undefined;
  const id = (targetId || "").trim();
  const files = fs
    .readdirSync(out)
    .filter((f) => f.endsWith("-graph.html"))
    .map((f) => path.join(out, f))
    .sort((a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs);
  if (id) {
    const strict = files.filter((p) => path.basename(p).includes(id));
    if (strict.length) return strict[0];
  }
  return files[0];
}

function analysisArgsForJoin(): string[] {
  const out = outDir();
  if (!out || !fs.existsSync(out)) return [];
  return fs
    .readdirSync(out)
    .filter((f) => f.endsWith("-analysis.json"))
    .map((f) => path.join(out, f))
    .sort((a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs)
    .slice(0, 24)
    .flatMap((p) => ["-a", p]);
}

export async function renderGraphFromJson(
  graphJsonPath: string,
  openAfter = true
): Promise<string> {
  if (!fs.existsSync(graphJsonPath)) {
    throw new Error(`graph.json 없음: ${graphJsonPath}`);
  }
  const html = graphJsonPath.replace(/-graph\.json$/i, "-graph.html");
  await spawnPy("render_kampff_graph.py", [
    "-g",
    graphJsonPath,
    "-o",
    html,
    "--lang",
    getConfig().uiLanguage,
  ]);
  if (!fs.existsSync(html)) {
    throw new Error(`graph HTML 없음: ${html}`);
  }
  if (openAfter) await openGraphHtml(html);
  return html;
}

export async function renderGraphFromBundle(
  bundlePath: string,
  openAfter = true,
  seed?: string
): Promise<string> {
  if (!fs.existsSync(bundlePath)) {
    throw new Error(`bundle 없음: ${bundlePath}`);
  }
  const dest = graphPathsFromBundle(bundlePath);
  const parent = path.dirname(dest.html);
  if (parent) fs.mkdirSync(parent, { recursive: true });
  const seedArgs = seed ? ["--seed", seed] : [];
  await spawnPy("build_kampff_graph.py", [
    "-b",
    bundlePath,
    "-o",
    dest.json,
    ...seedArgs,
    ...analysisArgsForJoin(),
  ]);
  await spawnPy("render_kampff_graph.py", [
    "-g",
    dest.json,
    "-o",
    dest.html,
    "--lang",
    getConfig().uiLanguage,
  ]);
  if (!fs.existsSync(dest.html)) {
    throw new Error(`graph HTML 없음: ${dest.html}`);
  }
  if (openAfter) await openGraphHtml(dest.html);
  return dest.html;
}

function seedFromRaw(rawDir: string, fallback: string): string {
  try {
    const st = JSON.parse(
      fs.readFileSync(path.join(rawDir, "STATE.json"), "utf8")
    ) as { author_id?: string };
    const aid = String(st.author_id || "").trim();
    return aid || fallback;
  } catch {
    return fallback;
  }
}

export async function renderEgoGraphFromHarvest(
  seed: string,
  rawDir: string,
  openAfter = true
): Promise<string> {
  const graphSeed = seedFromRaw(rawDir, seed);
  const harvestDate = path.basename(path.dirname(path.dirname(rawDir)));
  const dest = graphPathsForSeed(graphSeed, harvestDate || "graph");
  await spawnPy("build_relation_bundle.py", [
    "--seed",
    graphSeed,
    "--raw",
    rawDir,
    "-o",
    dest.bundle,
  ]);
  if (!fs.existsSync(dest.bundle)) {
    throw new Error(`relation bundle 없음: ${dest.bundle}`);
  }
  await spawnPy("build_kampff_graph.py", [
    "-b",
    dest.bundle,
    "-o",
    dest.json,
    "--seed",
    graphSeed,
    ...analysisArgsForJoin(),
  ]);
  await spawnPy("render_kampff_graph.py", [
    "-g",
    dest.json,
    "-o",
    dest.html,
    "--lang",
    getConfig().uiLanguage,
  ]);
  if (!fs.existsSync(dest.html)) {
    throw new Error(`graph HTML 없음: ${dest.html}`);
  }
  if (openAfter) await openGraphHtml(dest.html);
  return dest.html;
}

export async function openGraphHtml(htmlPath: string): Promise<void> {
  const mode = getConfig().reportOpenMode;
  if (mode === "browser" || mode === "both") {
    await vscode.env.openExternal(vscode.Uri.file(htmlPath));
  }
  if (mode === "panel" || mode === "both") {
    await vscode.commands.executeCommand("kampff.openReportPath", htmlPath);
  }
}

export async function openGraphForTarget(targetId?: string): Promise<string> {
  const id = (targetId || "").trim();
  if (id) {
    const raw = findLatestHarvestRaw(id);
    if (raw) {
      return renderEgoGraphFromHarvest(id, raw, true);
    }
    throw new Error(
      `이 ID(${id})의 글/댓글 수집이 없습니다.\nAnalyze로 먼저 수확하세요 → inbox/*/raw/${id}/posts`
    );
  }
  const bundle = findLatestBundle();
  if (bundle) {
    return renderGraphFromBundle(bundle, true);
  }
  const existing = findLatestGraphHtml();
  if (existing) {
    await openGraphHtml(existing);
    return existing;
  }
  const sample = sampleBundlePath();
  if (sample && fs.existsSync(sample)) {
    void vscode.window.showInformationMessage(
      "Kampff: inbox bundle 없음 — 합성 sample 그래프를 엽니다"
    );
    return renderGraphFromBundle(sample, true);
  }
  const sampleHtml = sampleGraphHtmlPath();
  if (sampleHtml && fs.existsSync(sampleHtml)) {
    await openGraphHtml(sampleHtml);
    return sampleHtml;
  }
  throw new Error(
    "관계 그래프 재료 없음\n→ ID를 넣고 Analyze로 수확하거나 inbox/*/bundle.json"
  );
}
