import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";
import { updateConfig } from "./config";

/** URL-first sites only (no regional board adapter). */
export type SiteKind = "generic";

export interface SiteRecord {
  id: string;
  label: string;
  baseUrl: string;
  loginUrl?: string;
  username?: string;
  kind: SiteKind;
  enabled: boolean;
  /** True when a password is stored in SecretStorage (never the password itself). */
  hasPassword: boolean;
}

export interface SiteOption {
  id: string;
  label: string;
  placeholder: string;
  baseUrl: string;
  loginUrl?: string;
  kind: SiteKind;
  hasPassword: boolean;
  hasUsername: boolean;
}

const SETTINGS_KEY = "sites";
const SECRET_PREFIX = "kampff.site.pw.";

const DEFAULT_SITES: SiteRecord[] = [
  {
    id: "x",
    label: "X",
    baseUrl: "https://x.com",
    loginUrl: "https://x.com/i/flow/login",
    username: "",
    kind: "generic",
    enabled: true,
    hasPassword: false,
  },
];

let extCtx: vscode.ExtensionContext | undefined;

export function initSites(context: vscode.ExtensionContext): void {
  extCtx = context;
}

function secretKey(id: string): string {
  return SECRET_PREFIX + id.replace(/[^\w.-]+/g, "_");
}

export function slugifySiteId(raw: string): string {
  const s = (raw || "")
    .trim()
    .toLowerCase()
    .replace(/^https?:\/\//, "")
    .replace(/^www\./, "")
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 40);
  return s || "site";
}

export function inferSiteKind(_baseUrl: string): SiteKind {
  return "generic";
}

function normalizeBaseUrl(u: string): string {
  let s = (u || "").trim();
  if (!s) return "";
  if (!/^https?:\/\//i.test(s)) s = "https://" + s;
  return s.replace(/\/+$/, "");
}

function normalizeLoginUrl(_baseUrl: string, loginUrl?: string): string | undefined {
  const L = (loginUrl || "").trim();
  if (L) return normalizeBaseUrl(L);
  return undefined;
}

function coerceSite(raw: unknown, i: number): SiteRecord | undefined {
  if (!raw || typeof raw !== "object") return undefined;
  const o = raw as Record<string, unknown>;
  const baseUrl = normalizeBaseUrl(String(o.baseUrl || o.url || ""));
  if (!baseUrl && !o.id && !o.label) return undefined;
  const label = String(o.label || o.id || `Site ${i + 1}`).trim();
  let id = String(o.id || slugifySiteId(label || baseUrl)).trim();
  id = slugifySiteId(id);
  if (!id) id = `site_${i}`;
  return {
    id,
    label: label || id,
    baseUrl: baseUrl || "",
    loginUrl: normalizeLoginUrl(
      baseUrl || "",
      o.loginUrl != null ? String(o.loginUrl) : undefined
    ),
    username: o.username != null ? String(o.username) : "",
    kind: "generic",
    enabled: o.enabled !== false,
    hasPassword: o.hasPassword === true,
  };
}

/** Non-secret site rows from settings (password never stored here). */
export function listSites(): SiteRecord[] {
  const c = vscode.workspace.getConfiguration("kampff");
  const raw = c.get<unknown[]>(SETTINGS_KEY);
  const out: SiteRecord[] = [];
  const seen = new Set<string>();
  if (Array.isArray(raw)) {
    raw.forEach((row, i) => {
      const s = coerceSite(row, i);
      if (!s || seen.has(s.id)) return;
      seen.add(s.id);
      out.push(s);
    });
  }
  if (!out.length) {
    return DEFAULT_SITES.map((s) => ({ ...s }));
  }
  return out;
}

export function listEnabledSites(): SiteRecord[] {
  return listSites().filter((s) => s.enabled !== false);
}

export function getSite(id: string): SiteRecord | undefined {
  const key = (id || "").trim().toLowerCase();
  if (!key) return undefined;
  return listSites().find((s) => s.id.toLowerCase() === key);
}

/** Always false — regional board adapter removed from product. */
export function siteIsClien(_platformOrSiteId: string): boolean {
  return false;
}

/** Adapter id for harvest / people paths. */
export function analysisPlatformForSite(site: SiteRecord | undefined, fallbackId: string): string {
  return (site?.id || fallbackId || "custom").toLowerCase();
}

export function sitesAsPlatformOptions(): SiteOption[] {
  return listEnabledSites().map((s) => ({
    id: s.id,
    label: s.label,
    placeholder:
      s.id === "x" || /x\.com|twitter\.com/i.test(s.baseUrl || "")
        ? "@elonmusk or https://x.com/elonmusk (example only)"
        : s.baseUrl
          ? `${s.baseUrl} · handle or URL`
          : "handle or profile URL",
    baseUrl: s.baseUrl,
    loginUrl: s.loginUrl,
    kind: s.kind,
    hasPassword: !!s.hasPassword,
    hasUsername: !!(s.username && s.username.trim()),
  }));
}

async function persistSites(sites: SiteRecord[]): Promise<void> {
  const cleaned = sites.map((s) => ({
    id: s.id,
    label: s.label,
    baseUrl: s.baseUrl,
    loginUrl: s.loginUrl || "",
    username: s.username || "",
    kind: s.kind,
    enabled: s.enabled !== false,
    hasPassword: !!s.hasPassword,
  }));
  await updateConfig(SETTINGS_KEY, cleaned);
}

export async function getSitePassword(id: string): Promise<string | undefined> {
  if (!extCtx) return undefined;
  const v = await extCtx.secrets.get(secretKey(id));
  return v && v.length ? v : undefined;
}

export async function setSitePassword(id: string, password: string | undefined): Promise<boolean> {
  if (!extCtx) {
    void vscode.window.showWarningMessage(
      "Kampff: extension context missing — password not stored"
    );
    return false;
  }
  const key = secretKey(id);
  if (password == null || password === "") {
    try {
      await extCtx.secrets.delete(key);
    } catch {
      /* ignore */
    }
    return false;
  }
  await extCtx.secrets.store(key, password);
  return true;
}

export async function upsertSite(
  partial: Partial<SiteRecord> & { id: string },
  password?: string | null
): Promise<SiteRecord> {
  const sites = listSites();
  const idx = sites.findIndex((s) => s.id === partial.id);
  const prev = idx >= 0 ? sites[idx] : undefined;
  const baseUrl = normalizeBaseUrl(partial.baseUrl ?? prev?.baseUrl ?? "");
  const kind =
    partial.kind ||
    prev?.kind ||
    inferSiteKind(baseUrl || partial.id);

  let hasPassword = prev?.hasPassword === true;
  if (password !== undefined) {
    if (password === null || password === "") {
      await setSitePassword(partial.id, undefined);
      hasPassword = false;
    } else {
      hasPassword = await setSitePassword(partial.id, password);
    }
  }

  const next: SiteRecord = {
    id: slugifySiteId(partial.id),
    label: (partial.label ?? prev?.label ?? partial.id).trim() || partial.id,
    baseUrl: baseUrl || "",
    loginUrl: normalizeLoginUrl(
      baseUrl || prev?.baseUrl || "",
      partial.loginUrl !== undefined ? partial.loginUrl : prev?.loginUrl
    ),
    username:
      partial.username !== undefined
        ? String(partial.username)
        : prev?.username || "",
    kind,
    enabled: partial.enabled !== undefined ? partial.enabled : prev?.enabled !== false,
    hasPassword,
  };

  if (idx >= 0) sites[idx] = next;
  else sites.push(next);
  await persistSites(sites);
  return next;
}

export async function removeSite(id: string): Promise<void> {
  const sites = listSites().filter((s) => s.id !== id);
  await setSitePassword(id, undefined);
  if (!sites.length) {
    await persistSites(DEFAULT_SITES.map((s) => ({ ...s })));
    return;
  }
  await persistSites(sites);
}

/**
 * Write one-shot auth blob for job child (not logged).
 * Path: {dataRoot}/queue/.site-auth/{id}.json
 */
export async function materializeSiteAuth(
  siteId: string,
  dataRoot: string
): Promise<string | undefined> {
  const site = getSite(siteId);
  if (!site || !dataRoot) return undefined;
  const password = (await getSitePassword(site.id)) || "";
  if (!site.username && !password && !site.baseUrl) return undefined;
  const dir = path.join(dataRoot, "queue", ".site-auth");
  fs.mkdirSync(dir, { recursive: true });
  const out = path.join(dir, `${site.id}.json`);
  const payload = {
    id: site.id,
    label: site.label,
    baseUrl: site.baseUrl,
    loginUrl: site.loginUrl || "",
    username: site.username || "",
    password,
    kind: site.kind,
    writtenAt: new Date().toISOString(),
  };
  fs.writeFileSync(out, JSON.stringify(payload, null, 2), { encoding: "utf8" });
  try {
    fs.chmodSync(out, 0o600);
  } catch {
    /* win may ignore */
  }
  return out;
}

export async function ensureSitesSeeded(): Promise<void> {
  // Default: X only (no password). User can add more sites.
  const c = vscode.workspace.getConfiguration("kampff");
  const raw = c.get<unknown[]>(SETTINGS_KEY);
  if (Array.isArray(raw) && raw.length > 0) return;
  await persistSites(DEFAULT_SITES.map((s) => ({ ...s })));
}

async function promptNewSite(): Promise<void> {
  const label = await vscode.window.showInputBox({
    title: "Kampff · 사이트 이름",
    placeHolder: "My forum · community name",
    validateInput: (v) => (v.trim() ? undefined : "이름을 입력하세요"),
  });
  if (label === undefined) return;

  const baseUrl = await vscode.window.showInputBox({
    title: "Kampff · 사이트 URL",
    placeHolder: "https://forum.example",
    value: "https://",
    validateInput: (v) => {
      const t = v.trim();
      if (!t || t === "https://") return "URL을 입력하세요";
      return undefined;
    },
  });
  if (baseUrl === undefined) return;
  const norm = normalizeBaseUrl(baseUrl);

  const idIn = await vscode.window.showInputBox({
    title: "Kampff · 사이트 ID (선택 목록 키)",
    value: slugifySiteId(label) || slugifySiteId(norm),
    placeHolder: "my_forum",
    validateInput: (v) => {
      const id = slugifySiteId(v);
      if (!id) return "id 필요";
      if (getSite(id)) return `이미 있음: ${id}`;
      return undefined;
    },
  });
  if (idIn === undefined) return;
  const id = slugifySiteId(idIn);

  const kindPick = await vscode.window.showQuickPick(
    [
      {
        label: "generic",
        description: "URL-first site",
        siteKind: "generic" as SiteKind,
      },
      {
        label: "generic",
        description: "일반 URL/핸들",
        siteKind: "generic" as SiteKind,
      },
    ],
    {
      title: "사이트 종류",
      placeHolder: inferSiteKind(norm),
    }
  );
  const kind = kindPick?.siteKind || inferSiteKind(norm);

  const username = await vscode.window.showInputBox({
    title: "Kampff · 로그인 ID (선택)",
    placeHolder: "비우면 세션/게스트만",
    value: "",
  });
  if (username === undefined) return;

  const password = await vscode.window.showInputBox({
    title: "Kampff · 로그인 비밀번호 (선택)",
    placeHolder: "SecretStorage에만 저장 · settings에 안 씀",
    password: true,
    value: "",
  });
  if (password === undefined) return;

  const loginUrl = await vscode.window.showInputBox({
    title: "Kampff · 로그인 URL (선택)",
    value: normalizeLoginUrl(norm) || "",
    placeHolder: "비우면 baseUrl 기준 추정",
  });
  if (loginUrl === undefined) return;

  await upsertSite(
    {
      id,
      label: label.trim(),
      baseUrl: norm,
      loginUrl: loginUrl.trim() || undefined,
      username: username.trim(),
      kind,
      enabled: true,
    },
    password.trim() ? password : null
  );
  void vscode.window.showInformationMessage(
    `Kampff: 사이트 등록 · ${label.trim()} (${id})`
  );
}

async function promptEditSite(site: SiteRecord): Promise<void> {
  const field = await vscode.window.showQuickPick(
    [
      { label: "이름(label)", id: "label" },
      { label: "URL(baseUrl)", id: "baseUrl" },
      { label: "로그인 URL", id: "loginUrl" },
      { label: "로그인 ID", id: "username" },
      { label: "비밀번호 설정/변경", id: "password" },
      { label: "비밀번호 삭제", id: "clearPassword" },
      { label: "종류(kind)", id: "kind" },
      {
        label: site.enabled ? "비활성화" : "활성화",
        id: "toggleEnabled",
      },
    ],
    { title: `편집 · ${site.label} (${site.id})` }
  );
  if (!field) return;

  if (field.id === "toggleEnabled") {
    await upsertSite({ id: site.id, enabled: !site.enabled });
    return;
  }
  if (field.id === "clearPassword") {
    await upsertSite({ id: site.id }, null);
    void vscode.window.showInformationMessage(`Kampff: ${site.id} 비밀번호 삭제`);
    return;
  }
  if (field.id === "kind") {
    const k = await vscode.window.showQuickPick(
      [
        { label: "generic", siteKind: "generic" as SiteKind },
        { label: "generic", siteKind: "generic" as SiteKind },
      ],
      { title: "종류" }
    );
    if (k) await upsertSite({ id: site.id, kind: k.siteKind });
    return;
  }
  if (field.id === "password") {
    const password = await vscode.window.showInputBox({
      title: `비밀번호 · ${site.id}`,
      password: true,
      placeHolder: "새 비밀번호",
    });
    if (password === undefined) return;
    await upsertSite({ id: site.id }, password.trim() ? password : null);
    void vscode.window.showInformationMessage(
      password.trim()
        ? `Kampff: ${site.id} 비밀번호 저장`
        : `Kampff: ${site.id} 비밀번호 비움`
    );
    return;
  }

  const cur =
    field.id === "label"
      ? site.label
      : field.id === "baseUrl"
        ? site.baseUrl
        : field.id === "loginUrl"
          ? site.loginUrl || ""
          : site.username || "";
  const v = await vscode.window.showInputBox({
    title: `${field.label} · ${site.id}`,
    value: cur,
  });
  if (v === undefined) return;
  if (field.id === "label") await upsertSite({ id: site.id, label: v.trim() || site.id });
  else if (field.id === "baseUrl") await upsertSite({ id: site.id, baseUrl: v });
  else if (field.id === "loginUrl") await upsertSite({ id: site.id, loginUrl: v.trim() });
  else if (field.id === "username") await upsertSite({ id: site.id, username: v });
}

/** Interactive register / edit / remove. Used by Setup + command. */
export async function runManageSitesWizard(): Promise<void> {
  await ensureSitesSeeded();
  for (;;) {
    const sites = listSites();
    const items: (vscode.QuickPickItem & { id: string })[] = [
      {
        label: "$(add) 사이트 추가",
        description: "URL + 로그인 ID/비밀번호",
        id: "__add",
      },
      ...sites.map((s) => ({
        label: `${s.enabled === false ? "$(circle-slash) " : "$(globe) "}${s.label}`,
        description: `${s.id} · ${s.baseUrl || "(no url)"}${s.hasPassword ? " · 🔑" : ""}${s.username ? " · " + s.username : ""}`,
        detail: `kind=${s.kind}${s.enabled === false ? " · disabled" : ""}`,
        id: s.id,
      })),
      { label: "$(check) 완료", description: "선택 목록에 반영", id: "__done" },
    ];
    const pick = await vscode.window.showQuickPick(items, {
      title: "Kampff · 등록 사이트 (Analyze 선택 목록)",
      placeHolder: "추가하거나 항목을 골라 편집/삭제",
      matchOnDescription: true,
    });
    if (!pick || pick.id === "__done") break;
    if (pick.id === "__add") {
      await promptNewSite();
      continue;
    }
    const site = getSite(pick.id);
    if (!site) continue;
    const act = await vscode.window.showQuickPick(
      [
        { label: "편집", id: "edit" },
        { label: "삭제", id: "del" },
        { label: "뒤로", id: "back" },
      ],
      { title: `${site.label} (${site.id})` }
    );
    if (!act || act.id === "back") continue;
    if (act.id === "del") {
      const ok = await vscode.window.showWarningMessage(
        `사이트 삭제: ${site.label} (${site.id})?`,
        { modal: true },
        "삭제"
      );
      if (ok === "삭제") {
        await removeSite(site.id);
        void vscode.window.showInformationMessage(`Kampff: 삭제 · ${site.id}`);
      }
      continue;
    }
    await promptEditSite(site);
  }
}
