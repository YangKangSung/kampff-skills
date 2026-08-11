import * as fs from "fs";
import * as path from "path";
import { getConfig, inboxDir, outDir, peopleDir, PlatformId, wikiReportsDir } from "./config";

export interface TargetOption {
  id: string;
  label: string;
  /** platform hint when known */
  platform: string;
  source: "raw" | "report" | "bundle" | "manual" | "wiki";
  /** extra: nick if found */
  nick?: string;
  /** path hint */
  path?: string;
  date?: string;
}

const SKIP_RAW = new Set([
  "seed",
  "indexes",
  "posts",
  "raw",
  ".agent-edge-profile",
  "agent-edge-profile",
]);

function isLikelyMemberId(name: string): boolean {
  if (!name || name.startsWith(".") || name.startsWith("_")) return false;
  if (SKIP_RAW.has(name.toLowerCase())) return false;
  if (name.startsWith("seed_") || name.startsWith("member_seed")) return false;
  if (name.endsWith(".html") || name.endsWith(".json")) return false;
  // author ids + simple nicks
  return /^[a-zA-Z0-9_]{2,40}$/.test(name) || /[가-힣]/.test(name);
}

function readJsonSafe(p: string): Record<string, unknown> | undefined {
  try {
    return JSON.parse(fs.readFileSync(p, "utf8")) as Record<string, unknown>;
  } catch {
    return undefined;
  }
}

function pickSubject(j: Record<string, unknown>): { id?: string; nick?: string; platform?: string } {
  const subject = (j.subject || j.target || j.identity || {}) as Record<string, unknown>;
  const id =
    (subject.id as string) ||
    (subject.author_id as string) ||
    (subject.authorId as string) ||
    (j.author_id as string) ||
    (j.authorId as string) ||
    (j.id as string);
  const nick =
    (subject.nick as string) ||
    (subject.nickname as string) ||
    (j.nick as string) ||
    (j.nickname as string);
  const platform =
    (subject.platform as string) ||
    (j.platform as string) ||
    (Array.isArray(j.platforms) ? String((j.platforms as string[])[0]) : undefined) ||
    "x";
  return {
    id: id ? String(id) : undefined,
    nick: nick ? String(nick) : undefined,
    platform: platform ? String(platform).toLowerCase() : "x",
  };
}

/** Scan KAMPFF_DATA for selectable analysis targets */
export function listTargets(): TargetOption[] {
  const cfg = getConfig();
  const byKey = new Map<string, TargetOption>();

  const upsert = (t: TargetOption) => {
    const key = `${t.platform}::${t.id.toLowerCase()}`;
    const prev = byKey.get(key);
    if (!prev) {
      byKey.set(key, t);
      return;
    }
    // prefer nick + newer date
    if (!prev.nick && t.nick) prev.nick = t.nick;
    if (t.date && (!prev.date || t.date > prev.date)) {
      prev.date = t.date;
      prev.path = t.path || prev.path;
      prev.source = t.source;
    }
    if (t.label && t.label.length > prev.label.length) prev.label = t.label;
  };

  // 1) inbox/*/raw/{memberId}
  const inbox = inboxDir(cfg);
  if (inbox && fs.existsSync(inbox)) {
    try {
      for (const date of fs.readdirSync(inbox)) {
        const rawRoot = path.join(inbox, date, "raw");
        if (!fs.existsSync(rawRoot) || !fs.statSync(rawRoot).isDirectory()) continue;
        for (const name of fs.readdirSync(rawRoot)) {
          const p = path.join(rawRoot, name);
          try {
            if (!fs.statSync(p).isDirectory()) continue;
          } catch {
            continue;
          }
          if (!isLikelyMemberId(name)) continue;
          // try STATE.json for nick
          let nick: string | undefined;
          const stateP = path.join(p, "STATE.json");
          const st = readJsonSafe(stateP);
          if (st) {
            nick = (st.nick as string) || (st.nickname as string) || undefined;
          }
          upsert({
            id: name,
            label: nick ? `${name} · ${nick}` : name,
            platform: "x",
            source: "raw",
            nick,
            path: p,
            date,
          });
        }
      }
    } catch {
      /* ignore */
    }
  }

  // 2) out/*-analysis.json + wiki reports/*-analysis.json
  const outRoots = [outDir(cfg), wikiReportsDir(cfg)].filter(Boolean);
  for (const out of outRoots) {
    if (!out || !fs.existsSync(out)) continue;
    try {
      for (const f of fs.readdirSync(out)) {
        if (!f.endsWith("-analysis.json") && !f.endsWith("analysis.json")) continue;
        const fp = path.join(out, f);
        const j = readJsonSafe(fp);
        if (!j) continue;
        const s = pickSubject(j);
        const fromWiki = out === wikiReportsDir(cfg);
        if (!s.id) {
          // filename: 2026-07-21-camp1234-analysis.json
          const m = f.match(
            /(\d{4}-\d{2}-\d{2})-([a-zA-Z0-9_]+)-(?:analysis|report)/i
          );
          if (m) {
            upsert({
              id: m[2],
              label: m[2],
              platform: "x",
              source: fromWiki ? "wiki" : "report",
              path: fp,
              date: m[1],
            });
          }
          continue;
        }
        upsert({
          id: s.id,
          label: s.nick ? `${s.id} · ${s.nick}` : s.id,
          platform: s.platform || "x",
          source: fromWiki ? "wiki" : "report",
          nick: s.nick,
          path: fp,
        });
      }
    } catch {
      /* ignore */
    }
  }

  // 3) inbox/*/bundle*.json
  if (inbox && fs.existsSync(inbox)) {
    try {
      for (const date of fs.readdirSync(inbox)) {
        const day = path.join(inbox, date);
        if (!fs.statSync(day).isDirectory()) continue;
        for (const f of fs.readdirSync(day)) {
          if (!f.startsWith("bundle") || !f.endsWith(".json")) continue;
          const fp = path.join(day, f);
          const j = readJsonSafe(fp);
          if (!j) continue;
          const s = pickSubject(j);
          // bundle-camp1234.json
          const bm = f.match(/bundle-([a-zA-Z0-9_]+)\.json/i);
          const id = s.id || (bm ? bm[1] : undefined);
          if (!id) continue;
          upsert({
            id,
            label: s.nick ? `${id} · ${s.nick}` : id,
            platform: s.platform || "x",
            source: "bundle",
            nick: s.nick,
            path: fp,
            date,
          });
        }
      }
    } catch {
      /* ignore */
    }
  }

  // 4) people/{platform}/{id} (wiki-first via peopleDir)
  const peopleRoot = peopleDir(cfg);
  if (peopleRoot && fs.existsSync(peopleRoot)) {
    try {
      for (const plat of fs.readdirSync(peopleRoot)) {
        const pp = path.join(peopleRoot, plat);
        if (!fs.statSync(pp).isDirectory()) continue;
        for (const id of fs.readdirSync(pp)) {
          const ip = path.join(pp, id);
          if (!fs.statSync(ip).isDirectory()) continue;
          if (!isLikelyMemberId(id) && !/^[a-zA-Z0-9_.-]{2,40}$/.test(id)) continue;
          let nick: string | undefined;
          const prof = readJsonSafe(path.join(ip, "profile.json"));
          if (prof) {
            nick =
              (prof.primary_nick as string) ||
              (prof.nick as string) ||
              undefined;
          }
          const isWikiPeople =
            !!cfg.wikiRoot &&
            peopleRoot.replace(/\\/g, "/").startsWith(cfg.wikiRoot.replace(/\\/g, "/"));
          upsert({
            id,
            label: nick ? `${id} · ${nick}` : id,
            platform: plat.toLowerCase(),
            source: isWikiPeople ? "wiki" : "manual",
            nick,
            path: ip,
          });
        }
      }
    } catch {
      /* ignore */
    }
  }

  return Array.from(byKey.values()).sort((a, b) =>
    a.label.localeCompare(b.label, "en", { sensitivity: "base" })
  );
}

export function targetsForPlatform(
  platform: string,
  all = listTargets()
): TargetOption[] {
  const p = (platform || "").toLowerCase();
  if (!p || p === "custom" || p === "auto") return all;
  // social platforms may not have local ids yet — still show all as optional cross-link
  // Prefer same-platform first
  const same = all.filter((t) => t.platform === p);
  if (p === "x") return same.length ? same : all.filter((t) => t.platform === "x");
  return same.length ? same : all;
}

export function formatIdInput(t: TargetOption, platform: PlatformId | string): string {
  if (platform === "x" || t.platform === "x") {
    return t.nick ? `${t.id} ${t.nick}` : t.id;
  }
  return t.id;
}
