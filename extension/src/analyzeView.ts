import * as vscode from "vscode";
import { AnalyzeDepth, AnalyzeMode, submitAnalyze } from "./analyze";
import { listTargets, TargetOption } from "./catalog";
import { getConfig, PLATFORMS, updateConfig } from "./config";
import {
  sitesAsPlatformOptions,
} from "./sites";
import {
  cancelActiveJob,
  getActiveJob,
  idleProgress,
  JobProgress,
  onJobProgress,
  togglePauseJob,
} from "./jobRunner";
import { ReportsProvider, reportDisplayLabel } from "./providers";
import {
  findLatestAnalysis,
  findLatestReport,
  openReportForTarget,
  openReportInBrowser,
  openDeskForTarget,
  renderReportForTarget,
  targetHasAnalysis,
  targetHasReport,
  ReportDepth,
} from "./renderReport";
import { openGraphForTarget } from "./renderGraph";
import {
  formatTarget,
  getActiveTarget,
  setActiveTarget,
} from "./sessionContext";

/**
 * One-click dossier panel.
 * ① starts Hermes job + live progress (default). Scoped to form ID only.
 */
export class AnalyzeViewProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = "kampff.analyze";
  private view?: vscode.WebviewView;

  constructor(private readonly context: vscode.ExtensionContext) {
    context.subscriptions.push(
      onJobProgress((p) => {
        this.pushProgress(p);
      })
    );
  }

  resolveWebviewView(webviewView: vscode.WebviewView): void {
    this.view = webviewView;
    webviewView.description = "원클릭 dossier · 진행 표시";
    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [
        vscode.Uri.joinPath(this.context.extensionUri, "media"),
      ],
    };
    webviewView.webview.html = this.html(webviewView.webview);

    webviewView.webview.onDidReceiveMessage(async (msg) => {
      if (!msg || typeof msg !== "object") return;
      try {
              const fs = await import("fs");
              const path = await import("path");
              const { getConfig } = await import("./config");
              const root = getConfig().dataRoot;
              if (root) {
                const line =
                  new Date().toISOString() +
                  " " +
                  JSON.stringify({
                    type: msg.type,
                    id: msg.authorId || msg.targetId || "",
                  }) +
                  String.fromCharCode(10);
                fs.appendFileSync(
                  path.join(root, "queue", "_webview.log"),
                  line,
                  "utf8"
                );
              }
            } catch {
              /* ignore */
            }
      switch (msg.type) {
        case "ping":
        case "clientError":
          this.status(
            msg.type !== "clientError",
            msg.type === "clientError"
              ? `웹뷰 오류: ${msg.text || "?"}`
              : `ping ok · ${msg.id || ""} · 확장 수신됨`
          );
          break;
        case "ready":
        case "refreshCatalog":
          this.postAll();
          {
            const j = getActiveJob();
            this.pushProgress(j || idleProgress());
          }
          break;
        case "analyze":
          await this.onAnalyze(msg);
          break;
        case "renderReport":
          await this.onRender(msg);
          break;
        case "openThisReport":
          await this.onOpenThis(msg);
          break;
        case "openDesk":
          await this.onOpenDesk(msg);
          break;
        case "openGraph":
          await this.onOpenGraph(msg);
          break;
        case "openThisReportBrowser":
          await this.onOpenThisBrowser(msg);
          break;
        case "openOutLatest":
          await this.onOpenOutLatest();
          break;
        case "communityThis":
          await this.onCommunityThis(msg);
          break;
        case "openSettings":
          await vscode.commands.executeCommand(
            "workbench.action.openSettings",
            "@ext:YangKangSung.kampff"
          );
          break;
        case "openSetup":
                  await vscode.commands.executeCommand("kampff.setup");
                  break;
                case "manageSites":
                  await vscode.commands.executeCommand("kampff.manageSites");
                  this.postAll();
                  break;
        case "openQueue":
                  await vscode.commands.executeCommand("kampff.openQueue");
                  break;
                case "cancelJob":
                  cancelActiveJob("webview");
                  break;
                case "togglePauseJob":
                case "pauseJob":
                case "resumeJob":
                  togglePauseJob();
                  break;
                case "probe": {
          const id = String(msg.authorId || msg.targetId || "").trim();
          this.view?.webview.postMessage({
            type: "probeResult",
            data: {
              id,
              hasAnalysis: id ? targetHasAnalysis(id) : false,
              hasReport: id ? targetHasReport(id) : false,
            },
          });
          break;
        }
        case "setConfig": {
          const key = String(msg.key || "").replace(/^kampff\./, "");
          const allowed = new Set([
            "analyzeLaunch",
            "defaultDepth",
            "defaultMode",
            "defaultPlatform",
            "reportOpenMode",
          ]);
          if (!allowed.has(key)) break;
          try {
            await updateConfig(key, msg.value);
            this.postAll();
          } catch (e) {
            void vscode.window.showErrorMessage(
              `Config: ${e instanceof Error ? e.message : e}`
            );
          }
          break;
        }
        default:
          break;
      }
    });
  }

  refresh(opts?: { focusId?: boolean }): void {
      this.postAll({ focusId: !!opts?.focusId });
    }

    /**
     * Dev live-reload: rebuild webview HTML so media/* scripts/css pick up
     * without restarting the extension host. Cache-bust query defeats webview cache.
     */
    rebuildHtml(): void {
      if (!this.view) return;
      this.view.webview.html = this.html(this.view.webview);
    }

  private resolveId(msg: {
      authorId?: string;
      targetId?: string;
      input?: string;
      url?: string;
    }): string {
      const raw = (msg.authorId || msg.targetId || "").trim();
      // URL pasted into ID box is not an author id
      if (raw && !/^https?:\/\//i.test(raw)) {
        return raw.split(/[\s|,]+/)[0];
      }
      const free = (msg.input || "").trim();
      if (free && !/^https?:\/\//i.test(free)) return free.split(/[\s|,]+/)[0];
      return "";
    }

  private postAll(opts?: { focusId?: boolean }): void {
      const c = getConfig();
      // Registered sites drive the Analyze site dropdown (not fixed PLATFORMS alone).
      let platforms = sitesAsPlatformOptions().map((p) => ({
        id: p.id,
        label: p.label,
        placeholder: p.placeholder,
        baseUrl: p.baseUrl,
        kind: p.kind,
        hasPassword: p.hasPassword,
        hasUsername: p.hasUsername,
      }));
      // Legacy customPlatforms still appended if not already registered as sites.
      const seen = new Set(platforms.map((p) => p.id));
      for (const x of c.customPlatforms || []) {
        if (!x?.id || seen.has(x.id)) continue;
        seen.add(x.id);
        platforms.push({
          id: x.id,
          label: x.label || x.id,
          placeholder: x.urlTemplate || "https://…",
          baseUrl: x.urlTemplate || "",
          kind: "generic",
          hasPassword: false,
          hasUsername: false,
        });
      }
      if (!platforms.length) {
        platforms = PLATFORMS.filter((p) => p.id === "x").map((p) => ({
          id: p.id,
          label: p.label,
          placeholder: p.placeholder,
          baseUrl: "",
          kind: "generic" as const,
          hasPassword: false,
          hasUsername: false,
        }));
      }
      let targets: TargetOption[] = [];
      try {
        targets = listTargets();
      } catch {
        targets = [];
      }

      let outLatestLabel = "";
      let outLatestPath = "";
      try {
        const latest = new ReportsProvider().latest();
        if (latest) {
          outLatestLabel = reportDisplayLabel(latest.fsPath, latest.meta);
          outLatestPath = latest.fsPath;
        }
      } catch {
        /* ignore */
      }

      const active = getActiveTarget();
      const activeId = active?.id || "";
      const activeLabel = formatTarget(active);
      const activeHasA = activeId ? targetHasAnalysis(activeId) : false;
      const activeHasR = activeId ? targetHasReport(activeId) : false;

      const defPlat =
        platforms.some((p) => p.id === c.defaultPlatform)
          ? c.defaultPlatform
          : platforms[0]?.id || "x";

      this.view?.webview.postMessage({
        type: "config",
        data: {
          dataRoot: c.dataRoot,
          dataRootOk: !!c.dataRoot,
          wikiRoot: c.wikiRoot,
          wikiRootOk: !!(c.wikiRoot && c.wikiRoot.length),
          peopleRoot: c.peopleRoot,
          analyzeLaunch: c.analyzeLaunch,
          defaultPlatform: defPlat,
          defaultMode: c.defaultMode,
          defaultDepth: c.defaultDepth,
          reportOpenMode: c.reportOpenMode,
          platforms,
          targets,
          focusId: !!opts?.focusId,
          outLatestLabel,
          outLatestPath,
          activeId,
          activeLabel,
          activeHasAnalysis: activeHasA,
          activeHasReport: activeHasR,
          activeNick: active?.nick || "",
        },
      });
    }

  private buildInput(msg: {
      platform?: string;
      authorId?: string;
      nick?: string;
      input?: string;
      targetId?: string;
      targetNick?: string;
      url?: string;
      mode?: string;
    }): string {
      const url = (msg.url || "").trim();
      const free = (msg.input || "").trim();
      const id =
        (msg.authorId || msg.targetId || "").trim().split(/[\s|,]+/)[0] || "";
      const nick = (msg.nick || msg.targetNick || "").trim();

      if (url) return url;
      // free text URL only — never fold nick into handle string
      if (free && /^https?:\/\//i.test(free)) return free;
      if (id) return id;
      if (free) return free.trim().split(/[\s|,]+/)[0] || free;
      if (nick) return nick;
      return free;
    }

  private remember(msg: {
    authorId?: string;
    targetId?: string;
    nick?: string;
    targetNick?: string;
    platform?: string;
    input?: string;
  }, action: string): string {
    const id = this.resolveId(msg);
    const nick = (msg.nick || msg.targetNick || "").trim();
    if (id) {
      setActiveTarget({
        id,
        nick: nick || undefined,
        platform: msg.platform || "x",
        lastAction: action,
      });
      void vscode.commands.executeCommand("kampff.refreshStatus");
    }
    return id;
  }

  private async onRender(msg: Record<string, string>): Promise<void> {
    const id = this.remember(msg, "render");
    if (!id) {
      this.status(false, "대상 ID를 입력하세요 (이 ID만 렌더합니다)");
      return;
    }
    this.status(true, `② HTML dossier · ${id}\nanalysis → report …`);
    try {
      const report = await renderReportForTarget(id);
      this.status(true, `② 완료 · ${id}\n${report}\n(이 ID 리포트 — out 최신 아님)`);
      this.postAll();
    } catch (e) {
      const t = e instanceof Error ? e.message : String(e);
      this.status(false, t);
    }
  }

  private async onOpenGraph(msg: Record<string, string>): Promise<void> {
    const id = this.remember(msg, "graph");
    this.status(true, id ? `관계 그래프 · ${id}` : "관계 그래프 · 보드");
    try {
      const p = await openGraphForTarget(id || undefined);
      this.status(true, `그래프 · ${p}`);
      this.postAll();
    } catch (e) {
      const t = e instanceof Error ? e.message : String(e);
      this.status(false, t);
    }
  }

  private async onOpenDesk(msg: Record<string, string>): Promise<void> {
    const id = this.remember(msg, "desk");
    if (!id) {
      this.status(false, "대상 ID를 입력하세요");
      return;
    }
    this.status(true, `거리 책상 · ${id}`);
    try {
      const p = await openDeskForTarget(id);
      this.status(true, `책상 · ${id}\n${p}`);
      this.postAll();
    } catch (e) {
      const t = e instanceof Error ? e.message : String(e);
      this.status(false, t);
    }
  }

  private async onOpenThis(msg: Record<string, string>): Promise<void> {
    const id = this.remember(msg, "open");
    if (!id) {
      this.status(false, "대상 ID를 입력하세요");
      return;
    }
    this.status(true, `이 사람 리포트 열기 · ${id}`);
    try {
      const p = await openReportForTarget(id);
      this.status(true, `열림 · ${id}\n${p}`);
      this.postAll();
    } catch (e) {
      const t = e instanceof Error ? e.message : String(e);
      this.status(false, t);
    }
  }

  private async onOpenThisBrowser(msg: Record<string, string>): Promise<void> {
    const id = this.remember(msg, "open-browser");
    if (!id) {
      this.status(false, "대상 ID를 입력하세요");
      return;
    }
    const raw = String(msg.depth || "").toLowerCase();
    const depth: ReportDepth | undefined =
      raw === "quick" || raw === "full" ? raw : undefined;
    const label = depth === "full" ? "FULL" : depth === "quick" ? "빠른" : "있는 것";
    this.status(true, `브라우저 · ${label} · ${id}`);
    try {
      const p = await openReportInBrowser(id, depth);
      this.status(true, `브라우저 · ${label}\n${p}`);
    } catch (e) {
      const t = e instanceof Error ? e.message : String(e);
      this.status(false, t);
    }
  }

  private async onOpenOutLatest(): Promise<void> {
    const latest = new ReportsProvider().latest();
    if (!latest) {
      this.status(false, "out/ 에 리포트 없음");
      return;
    }
    const label = reportDisplayLabel(latest.fsPath, latest.meta);
    this.status(
      true,
      `out 최신(mtime) 연다 — 지금 폼 대상과 무관할 수 있음\n→ ${label}\n${latest.fsPath}`
    );
    await vscode.commands.executeCommand("kampff.openReportPath", latest.fsPath);
  }

  private async onCommunityThis(msg: Record<string, string>): Promise<void> {
    const id = this.remember(msg, "community");
    if (!id) {
      this.status(false, "대상 ID를 입력하세요");
      return;
    }
    const a = findLatestAnalysis(id);
    if (!a) {
      this.status(
        false,
        `게시 초안 불가 · ${id}\nanalysis.json 없음 — 먼저 ① 회원 전반 분석`
      );
      return;
    }
    // pass analysis path via openReportPath-equivalent command args
    const report = findLatestReport(id);
    if (report) {
      await vscode.commands.executeCommand("kampff.generateCommunityPost", {
        fsPath: report,
        label: id,
        kind: "report",
      });
    } else {
      await vscode.commands.executeCommand("kampff.generateCommunityPost", {
        fsPath: a,
        label: id,
        kind: "analysis",
      });
    }
    this.status(true, `게시 초안(선택) · ${id}\n※ 전반 분석 결과에서 뽑은 draft`);
  }

  private async onAnalyze(msg: {
    platform?: string;
    authorId?: string;
    nick?: string;
    input?: string;
    targetId?: string;
    targetNick?: string;
    url?: string;
    mode?: string;
    depth?: string;
    note?: string;
    customUrl?: string;
    links?: { platform?: string; handle?: string; url?: string }[];
  }): Promise<void> {
    const cfg = getConfig();
    const input = this.buildInput(msg);
    const customUrl = (msg.customUrl || "").trim();
    const links = msg.links || [];
    if (!input && !customUrl && !links.some((l) => l.handle || l.url)) {
      this.status(false, "대상 ID(또는 URL)를 입력하세요");
      this.pushProgress(idleProgress());
      return;
    }
    const idHint = this.resolveId(msg) || input.split(/[\s|,]+/)[0] || "";
    this.status(true, `시작 · ${idHint || input}\n접수 중…`);
    this.pushProgress({
      ...idleProgress(),
      phase: "queued",
      targetId: idHint,
      message: "접수 중…",
      humanPhase: "접수했어요",
      pct: 5,
      live: true,
      steps: idleProgress().steps.map((s) =>
        s.id === "queue" ? { ...s, state: "active" as const } : s
      ),
      startedAt: new Date().toISOString(),
    });

    try {
      await vscode.commands.executeCommand("kampff.analyze.focus");
    } catch {
      /* ignore */
    }

    try {
          const authorId = this.resolveId(msg);
                    const nickIn = (msg.nick || msg.targetNick || "").trim();
                    const triggerUrl = (msg.url || "").trim();
                    let mode = (msg.mode as AnalyzeMode) || cfg.defaultMode || "member";
                    const siteKey = (msg.platform || cfg.defaultPlatform || "x").toLowerCase();
                    if (
                      authorId &&
                      !/^https?:\/\//i.test(authorId) &&
                      mode !== "profile"
                    ) {
                      if (mode === "thread" && !triggerUrl) mode = "member";
                      if (mode === "auto") mode = "member";
                    }
                    const req = await submitAnalyze({
                      input,
                      platform: siteKey || cfg.defaultPlatform || "x",
                      mode,
                      depth: (msg.depth as AnalyzeDepth) || cfg.defaultDepth || "quick",
                      note: msg.note,
                      customUrl,
                      links,
                      authorId: authorId || undefined,
                      nick: nickIn || undefined,
                      triggerUrl: triggerUrl || undefined,
                    });
                    const tid = (
                      authorId ||
                      msg.authorId ||
                      msg.targetId ||
                      req.parsed.authorId ||
                      idHint ||
                      ""
                    ).trim();
                    const nick = (nickIn || req.parsed.nick || "").trim();
                    if (tid) {
                      setActiveTarget({
                        id: tid,
                        nick: nick || undefined,
                        platform: req.platform,
                        lastAction: "analyze",
                      });
                      void vscode.commands.executeCommand("kampff.refreshStatus");
                    }

                    const axisHint =
                      req.mode === "member" && req.parsed.authorId
                        ? " · member"
                        : "";

          if (cfg.analyzeLaunch === "none") {
            this.status(
              true,
              [
                "큐만 저장됨 (analyzeLaunch=none)",
                `대상: ${tid || req.parsed.display}${axisHint}`,
                req.queuePath,
                "",
                "자동 실행: 설정 kampff.analyzeLaunch = auto",
              ].join(String.fromCharCode(10))
            );
          } else {
            this.status(
              true,
              [
                `분석 시작 · ${req.parsed.display || tid}${axisHint}`,
                "위 진행 카드 · 상태바 · 알림 · 출력(Kampff) 확인",
              ].join(String.fromCharCode(10))
            );
          }
          this.postAll();
          const j = getActiveJob();
          if (j) this.pushProgress(j);
    } catch (e) {
      const err = e instanceof Error ? e.message : String(e);
      this.status(false, err);
      void vscode.window.showErrorMessage(`Kampff 시작 실패: ${err}`);
      this.pushProgress({
        ...idleProgress(),
        phase: "error",
        targetId: idHint,
        message: "시작 실패",
        humanPhase: "문제 발생",
        error: err,
        detail: err,
        pct: 100,
        live: false,
        startedAt: new Date().toISOString(),
      });
    }
  }

  private pushProgress(p: JobProgress): void {
        this.view?.webview.postMessage({ type: "progress", data: p });
        const ok = p.phase !== "error";
        const busy =
          p.phase !== "done" && p.phase !== "error" && p.phase !== "idle";
        this.view?.webview.postMessage({
          type: "status",
          data: {
            ok: p.phase === "error" ? false : ok,
            busy,
            text: [p.message, p.detail, p.error]
              .filter(Boolean)
              .join(String.fromCharCode(10)),
          },
        });

        // Title strip: always glanceable even when webview scrolled/collapsed
        if (this.view) {
          if (p.phase === "idle") {
            this.view.description = "원클릭 dossier · 진행 표시";
            this.view.badge = undefined;
          } else if (p.phase === "done") {
            this.view.description = `완료 · ${p.targetId}`;
            this.view.badge = { value: 100, tooltip: p.message };
          } else if (p.phase === "error") {
            this.view.description = `실패 · ${p.targetId}`;
            this.view.badge = { value: 0, tooltip: p.error || p.message };
          } else {
            const el =
              p.elapsedSec != null && p.elapsedSec > 0
                ? `${Math.floor(p.elapsedSec / 60)}:${String(
                    p.elapsedSec % 60
                  ).padStart(2, "0")}`
                : "";
            this.view.description = `${p.pct}% ${p.humanPhase || ""}${
              el ? " · " + el : ""
            }`.trim();
            this.view.badge = {
              value: Math.max(1, Math.min(99, p.pct || 1)),
              tooltip: [p.message, p.detail].filter(Boolean).join("\n"),
            };
          }
        }
      }

  private status(ok: boolean, text: string): void {
        this.view?.webview.postMessage({
          type: "status",
          data: { ok, text },
        });
      }

  private html(webview: vscode.Webview): string {
        const nonce = getNonce();
        // Bust webview cache on every rebuild (dev soft-reload + first open).
        const bust = `v=${Date.now()}`;
        const cssUri = webview.asWebviewUri(
          vscode.Uri.joinPath(this.context.extensionUri, "media", "analyze.css")
        );
        const glossUri = webview.asWebviewUri(
          vscode.Uri.joinPath(this.context.extensionUri, "media", "glossary.js")
        );
        const jsUri = webview.asWebviewUri(
          vscode.Uri.joinPath(this.context.extensionUri, "media", "analyze.js")
        );
        const csp = [
          "default-src 'none'",
          `style-src ${webview.cspSource} 'unsafe-inline'`,
          `script-src 'nonce-${nonce}' ${webview.cspSource}`,
          `img-src ${webview.cspSource} data:`,
          `font-src ${webview.cspSource}`,
        ].join("; ");

        return `<!DOCTYPE html>
    <html lang="ko">
    <head>
    <meta charset="UTF-8"/>
    <meta http-equiv="Content-Security-Policy" content="${csp}"/>
    <meta name="viewport" content="width=device-width, initial-scale=1"/>
    <title>Kampff · 지금 대상</title>
        <link rel="stylesheet" href="${cssUri}?${bust}"/>
        </head>
      <body>
    <div class="top">
      <div class="brand">
        <div class="mark" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="12" cy="12" r="7.5" stroke="currentColor" stroke-width="1.6" opacity=".45"/>
            <path d="M12 5.2A6.8 6.8 0 0 1 18.5 12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
            <circle cx="12" cy="12" r="2" fill="currentColor"/>
            <path d="M12 12L15.8 8.4" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>
          </svg>
        </div>
        <div>
          <h1>이 사람 분석</h1>
          <p class="sub">원클릭 <span class="term" data-term="dossier">dossier</span>. 진행이 아래에 보입니다.</p>
        </div>
      </div>
      <button type="button" class="icon-btn" id="btnSettings" title="설정">⚙</button>
    </div>

    <details class="guide" id="guideBox">
      <summary>
        <span>도움말 · 용어</span>
        <span class="step" style="margin-left:auto;margin-right:6px">?</span>
      </summary>
      <div class="guide-body">
        <ol class="guide-steps">
          <li><b>이 사람</b> = 핸들/회원 ID (예: X <code>elonmusk</code> · example only). 글 URL 비움.</li>
          <li><b>이 글</b> = 게시글 <b>URL</b> 하나. ID 없어도 됨.</li>
          <li>Setup으로 dataRoot/wikiRoot 한 번 잡기.</li>
          <li>① 시작 → Hermes → HTML. 점선 단어 = 용어 설명.</li>
        </ol>
        <div class="gloss-head">용어 사전</div>
        <div class="gloss-list" id="glossList"></div>
      </div>
    </details>

    <div class="card progress-card sticky-progress" id="progressCard" data-phase="idle">
      <!-- Fixed 3-line window: L1 status · L2 bar · L3 detail (in-place updates only) -->
      <div class="prog3" id="prog3win" aria-live="polite" aria-atomic="true">
        <div class="prog3-l1" id="progLine1">
          <span class="prog-live" id="progLive" hidden></span>
          <span class="prog-phase" id="humanPhase">준비</span>
          <span class="prog-who" id="progWho">—</span>
          <span class="prog-pct" id="pctLabel">0%</span>
          <span class="prog-elapsed" id="progElapsed">0s</span>
        </div>
        <div class="pbar"><div class="pfill" id="pfill" style="width:0%"></div></div>
        <div class="prog3-l3" id="progressMsg" title="">ID 입력 후 ① 시작</div>
        <ul class="prog-materials" id="progMaterials" hidden></ul>
      </div>
      <div class="prog-actions" id="progActions" hidden>
        <button type="button" class="btn ghost" id="btnPauseToggle" title="일시정지 / 재개" data-paused="0">일시정지</button>
        <button type="button" class="btn warn" id="btnCancel" title="완전 종료 (kill)">중단</button>
      </div>
      <span id="progHint" hidden></span>
      <ol class="steps" id="steps" hidden></ol>
      <p class="prog-safe" id="progSafe" hidden>polite · rate-limit</p>
    </div>

  <div class="card">
      <div class="card-h"><span class="lbl">사이트</span><span class="step">1</span></div>
      <label class="field" for="site">사이트 / 플랫폼 <span class="term help-ico" data-term="platform" tabindex="0">?</span></label>
      <select class="plain" id="site" aria-label="platform">
        <option value="x">X (x)</option>
        <option value="facebook">Facebook (facebook)</option>
        <option value="instagram">Instagram (instagram)</option>
        <option value="reddit">Reddit (reddit)</option>
        <option value="linkedin">LinkedIn (linkedin)</option>
        <option value="custom">Custom URL (custom)</option>
      </select>
    </div>

    <div class="card focus" id="idBlock">
          <div class="card-h"><span class="lbl" id="idTitle">대상</span><span class="step">2</span></div>

          <div class="seg scope-seg" data-name="mode" id="modeSeg">
            <button type="button" data-v="member" class="on" title="회원 한 명 · 글·댓글·공감 4축">이 사람</button>
            <button type="button" data-v="thread" title="게시글 URL 하나">이 글</button>
          </div>
          <div class="scope-banner" id="scopeBanner" role="status">핸들/회원 ID만 입력. 예: elonmusk (example only)</div>

          <div id="personFields" class="person-fields emphasis">
            <label class="field" for="authorId" id="lblAuthorId">Handle / 회원 ID<span class="req" id="reqId">*</span> <span class="term help-ico" data-term="authorid" tabindex="0">?</span></label>
            <input id="authorId" type="text" autocomplete="off" spellcheck="false" autocapitalize="off" autocorrect="off" placeholder="예: elonmusk · example only"/>
            <p class="field-hint" id="idHint">프로필 닉네임이 아니라 <b>회원 ID</b>입니다. 글 URL은 ‘이 글’ 모드에서.</p>
            <div class="row2" id="nickRow">
              <div>
                <label class="field" for="nick">닉네임 (선택) <span class="term help-ico" data-term="nick" tabindex="0">?</span></label>
                <input id="nick" type="text" placeholder="화면 이름 · 선택"/>
              </div>
            </div>
          </div>

          <div id="urlField" class="url-field hide">
            <label class="field" for="url" id="lblUrl">글 URL<span class="req" id="reqUrl">*</span> <span class="term help-ico" data-term="thread" tabindex="0">?</span></label>
            <input id="url" type="text" autocomplete="off" spellcheck="false" placeholder="https://x.com/elonmusk · example only"/>
            <p class="field-hint" id="urlHint">이 게시글 하나만 봅니다. 회원 ID 없어도 됩니다.</p>
          </div>

          <div class="ctx" id="ctxChip">
            <span class="k">작업</span>
            <span class="v" id="ctxWho">—</span>
            <span class="pill unk term" id="tagA" data-term="analysis">분석데이터 …</span>
            <span class="pill unk term" id="tagR" data-term="report">보고서 …</span>
          </div>

          <details class="known-ids" id="knownBox">
            <summary>알려진 ID 고르기</summary>
            <div class="search-wrap">
              <span class="ico">⌕</span>
              <input id="targetFilter" type="text" placeholder="필터"/>
            </div>
            <div class="list" id="targetList" role="listbox"></div>
          </details>
        </div>

        <div class="card">
          <div class="card-h"><span class="lbl" id="runTitle">분석 실행</span><span class="step">3</span></div>
          <p class="hint-inline" id="runHint"><b class="term" data-term="member">이 사람</b> → 회원 ID. <b class="term" data-term="thread">이 글</b> → 글 URL. 둘 중 하나만.</p>
          <div>
            <label class="field">깊이 <span class="term help-ico" data-term="depth" tabindex="0">?</span></label>
            <div class="seg" data-name="depth" id="depthSeg">
              <button type="button" data-v="quick" class="on" title="가벼운 수집 (quick)">빠른</button>
              <button type="button" data-v="full" title="깊게 수집 · 시간↑ (FULL)">FULL</button>
            </div>
          </div>
          <div style="margin-top:8px">
            <label class="field" for="note">메모</label>
            <input id="note" type="text" placeholder="선택 · 본인만 보는 메모"/>
          </div>

          <div class="stack">
            <button type="button" class="btn primary" id="btnGo">
              <span class="t" id="btnGoTitle">① 이 사람 분석 시작</span>
              <span class="d" id="btnGoSub">회원 ID 기준 4축 · 끝나면 dossier</span>
            </button>
        <button type="button" class="btn secondary" id="btnRender">
          <span class="t">② HTML 보고서 다시 만들기</span>
          <span class="d"><span class="term" data-term="analysis">analysis.json</span> → <span class="term" data-term="report">report.html</span> · 이 ID만</span>
        </button>
        <button type="button" class="btn" id="btnOpenThis">
          <span class="t">이 사람 보고서 열기</span>
          <span class="d">폼 ID 파일 · <span class="term" data-term="out">out</span> 최신(타인) 아님</span>
        </button>
        <button type="button" class="btn" id="btnDesk">
          <span class="t">거리 책상 (Desk)</span>
          <span class="d">인용 뮤트 · 상황 · 시간 · 한 사람만</span>
        </button>
        <button type="button" class="btn" id="btnGraph">
          <span class="t">관계 그래프 (Graph)</span>
          <span class="d">ID 중심 · 글·댓글 + 이미 수확한 상대</span>
        </button>
        <div class="row-g" style="margin-top:6px">
          <button type="button" class="btn ghost" id="btnOpenQuickBrowser" title="이 ID의 빠른(quick) HTML을 기본 브라우저로">브라우저 · 빠른</button>
          <button type="button" class="btn ghost" id="btnOpenFullBrowser" title="이 ID의 FULL HTML을 기본 브라우저로">브라우저 · FULL</button>
        </div>
      </div>
      <details class="adv export-box" id="exportBox" style="margin-top:10px">
        <summary>선택 · 분석 후 내보내기</summary>
        <p class="hint-inline" style="margin:6px 0 8px"><span class="term" data-term="dossier">dossier</span>가 있을 때만. 게시용 초안 ≠ 전반 분석 자체.</p>
        <button type="button" class="btn" id="btnCPost">
          <span class="t">게시글 초안 (선택)</span>
          <span class="d">이 ID 분석 기반 draft · 복붙용</span>
        </button>
      </details>

      <div class="row-g" style="margin-top:8px">
              <button type="button" class="btn ghost" id="btnQueue" title="queue 폴더 — 작업 요청 파일">큐</button>
              <button type="button" class="btn ghost" id="btnSites" title="사이트 URL·로그인 등록">사이트</button>
              <button type="button" class="btn ghost" id="btnSetup" title="dataRoot 경로 설정">Setup</button>
              <button type="button" class="btn ghost" id="btnRefresh" title="목록 새로고침">↻</button>
            </div>

      <div class="divider"></div>
      <button type="button" class="btn warn" id="btnOutLatest">
        <span class="t">⚠ <span class="term" data-term="out">out</span> 최신(<span class="term" data-term="mtime">mtime</span>) 열기</span>
        <span class="d">폼 대상과 무관할 수 있음</span>
      </button>
      <p class="out-meta" id="outMeta">out 리포트 정보</p>
    </div>

    <div id="status">ready</div>
    <p class="foot">
      <b style="color:var(--fg);font-weight:600">① 한 번</b> = 접수→<span class="term" data-term="hermes">Hermes</span> 분석→HTML→열기<br/>
      대상 = 입력 ID만 · <span class="kbd">Ctrl</span>+<span class="kbd">Enter</span>
    </p>

    <details class="adv">
      <summary>고급 · SNS · 실행기</summary>
      <div class="link-row"><span>Facebook</span><input data-plat="facebook" type="text"/></div>
      <div class="link-row"><span>X</span><input data-plat="x" type="text"/></div>
      <div class="link-row"><span>Instagram</span><input data-plat="instagram" type="text"/></div>
      <div class="link-row"><span>Reddit</span><input data-plat="reddit" type="text"/></div>
      <div class="link-row"><span>LinkedIn</span><input data-plat="linkedin" type="text"/></div>
      <label class="field" for="customUrl" style="margin-top:8px">Custom URL</label>
      <input id="customUrl" type="text" placeholder="https://…"/>
      <label class="field" for="launch" style="margin-top:8px">큐 후 실행기 <span class="term help-ico" data-term="launch" tabindex="0">?</span></label>
      <select class="plain" id="launch">
        <option value="auto">auto (Hermes 자동 · 추천)</option>
        <option value="hermes">hermes chat</option>
        <option value="terminal">terminal helper</option>
        <option value="none">none (파일만)</option>
      </select>
    </details>

  <script nonce="${nonce}" src="${glossUri}?${bust}"></script>
    <script nonce="${nonce}" src="${jsUri}?${bust}"></script>
    </body>
    </html>`;
      }
    }

function getNonce(): string {
  const chars =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  let out = "";
  for (let i = 0; i < 32; i++)
    out += chars.charAt(Math.floor(Math.random() * chars.length));
  return out;
}
