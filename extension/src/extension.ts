import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";
import { analyzeFromPalette, submitAnalyze } from "./analyze";
import { AnalyzeViewProvider } from "./analyzeView";
import { getConfig, peopleDir, queueDir, updateConfig, wikiRoot } from "./config";
import {
  ensureSitesSeeded,
  initSites,
  listEnabledSites,
  runManageSitesWizard,
} from "./sites";
import { ensureWikiLayout } from "./wikiStore";
import {
  analysisPathForReport,
  InboxProvider,
  KampffItem,
  RawProvider,
  reportDisplayLabel,
  ReportsProvider,
} from "./providers";
import {
  notesPathForPerson,
  PeopleItem,
  PeopleProvider,
} from "./peopleProvider";
import { ReportPanel } from "./reportPanel";
import { generateCommunityPost } from "./communityPost";
import {
  findLatestAnalysis,
  findLatestReport,
  findReportsByDepth,
  openReportForTarget,
  openReportInBrowser,
} from "./renderReport";
import {
  formatTarget,
  getActiveTarget,
  setActiveTarget,
} from "./sessionContext";
import {
  cancelActiveJob,
  startExternalProgressWatch,
  togglePauseJob,
} from "./jobRunner";
import { maybeStartDevReload } from "./devReload";
import {
  disposeKampffLog,
  kampffLog,
  kampffLogBlock,
  showKampffLog,
} from "./log";

let status: vscode.StatusBarItem | undefined;
let refreshTimer: NodeJS.Timeout | undefined;
let reportsRef: ReportsProvider | undefined;

export function activate(context: vscode.ExtensionContext): void {
  initSites(context);
    void ensureSitesSeeded();
    const cfg0 = getConfig();
    let siteSummary = "(none)";
    try {
      siteSummary = listEnabledSites().map((s) => s.id).join(",") || "(none)";
    } catch {
      /* ignore */
    }
  kampffLogBlock("activate", [
    `version ${context.extension.packageJSON?.version ?? "?"}`,
    `mode ${vscode.ExtensionMode[context.extensionMode] ?? context.extensionMode}`,
    `extensionPath ${context.extensionPath}`,
    `dataRoot ${cfg0.dataRoot || "(empty)"}`,
    `wikiRoot ${cfg0.wikiRoot || "(empty)"}`,
    `skillsDev ${cfg0.skillsDevRoot || "(empty)"}`,
    `peopleDir ${peopleDir(cfg0)}`,
    `queueDir ${queueDir(cfg0)}`,
    `python ${cfg0.pythonPath}`,
    `hermesCommand ${cfg0.hermesCommand || "(auto)"}`,
    `launch ${cfg0.analyzeLaunch}`,
    `harvestPolite ${cfg0.harvestPolite !== false}`,
    `sites ${siteSummary}`,
  ]);
  kampffLog("Output channel ready — job stdout/stderr and promote lines land here.");

  const reports = new ReportsProvider();
  reportsRef = reports;
  const inbox = new InboxProvider();
  const raw = new RawProvider();
  const people = new PeopleProvider();
  const analyzeView = new AnalyzeViewProvider(context);

    // External Hermes/harvest jobs write queue/*-progress.json — surface in sticky + status bar
    context.subscriptions.push(startExternalProgressWatch());

    // Trees + status only. Never touch analyze webview on the timer.
    const refreshTrees = () => {
      reports.refresh();
      inbox.refresh();
      raw.refresh();
      people.refresh();
      updateStatus(reports);
    };
    const refreshAll = () => {
      refreshTrees();
      analyzeView.refresh({ focusId: false });
    };

    // Dev: media save → webview only; tsc out/ → extension host (see devReload.ts)
    context.subscriptions.push(
      vscode.commands.registerCommand("kampff.devSoftReload", () => {
        analyzeView.rebuildHtml();
        refreshTrees();
      })
    );
    maybeStartDevReload(context, {
      onMedia: () => {
        analyzeView.rebuildHtml();
        refreshTrees();
      },
    });

  status = vscode.window.createStatusBarItem(
    vscode.StatusBarAlignment.Left,
    48
  );
  status.command = "kampff.statusBarAction";
  context.subscriptions.push(status);

  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(
      AnalyzeViewProvider.viewType,
      analyzeView,
      { webviewOptions: { retainContextWhenHidden: true } }
    ),
    vscode.window.registerTreeDataProvider("kampff.reports", reports),
    vscode.window.registerTreeDataProvider("kampff.inbox", inbox),
    vscode.window.registerTreeDataProvider("kampff.raw", raw),
    vscode.window.registerTreeDataProvider("kampff.people", people),

    vscode.commands.registerCommand("kampff.refresh", () => refreshAll()),
        vscode.commands.registerCommand("kampff.refreshStatus", () =>
          updateStatus(reports)
        ),
        vscode.commands.registerCommand("kampff.cancelJob", () =>
          cancelActiveJob("command")
        ),
        vscode.commands.registerCommand("kampff.togglePauseJob", () => togglePauseJob()),
        // legacy aliases → same toggle
        vscode.commands.registerCommand("kampff.pauseJob", () => togglePauseJob()),
        vscode.commands.registerCommand("kampff.resumeJob", () => togglePauseJob()),
        vscode.commands.registerCommand("kampff.showLog", () => {
          showKampffLog(false);
          kampffLog("(showLog) channel focused");
        }),
        vscode.commands.registerCommand("kampff.analyze", () => analyzeFromPalette()),
    vscode.commands.registerCommand("kampff.focusAnalyze", async () => {
      await vscode.commands.executeCommand("kampff.analyze.focus");
      analyzeView.refresh({ focusId: true });
    }),

    vscode.commands.registerCommand("kampff.statusBarAction", async () => {
      const mode = getConfig().statusBarClick;
      if (mode === "analyze") {
        await vscode.commands.executeCommand("kampff.focusReportBuilder");
        return;
      }
      if (mode === "latestReport") {
        // Explicit: out mtime latest — label says so
        const latest = reports.latest();
        if (!latest) {
          void vscode.window.showWarningMessage("Kampff: out/ 리포트 없음");
          return;
        }
        await vscode.commands.executeCommand(
          "kampff.openReportPath",
          latest.fsPath
        );
        return;
      }
      const active = getActiveTarget();
      const latest = reports.latest();
      const activeLabel = formatTarget(active);
      const outLabel = latest
        ? reportDisplayLabel(latest.fsPath, latest.meta)
        : "(없음)";
      const pick = await vscode.window.showQuickPick(
        [
          {
            label: `$(person) 이 사람 분석 뷰`,
            description: "회원 전반 dossier · 폼",
            id: "builder",
          },
          {
            label: `$(graph) 이 사람 분석 리포트 열기`,
            description: active?.id
              ? activeLabel
              : "대상 없음 — 먼저 폼에 ID",
            id: "activeReport",
          },
          {
            label: `$(warning) out 최신(mtime) 열기`,
            description: outLabel + " · 폼 대상과 다를 수 있음",
            id: "outLatest",
          },
          {
            label: `$(export) 게시 초안(선택)`,
            description: active?.id
              ? activeLabel + " · 분석 후 export"
              : "대상 없음",
            id: "cpostActive",
          },
          { label: `$(list-ordered) 큐 폴더`, id: "queue" },
          { label: `$(folder-opened) dataRoot (runtime)`, id: "data" },
          { label: `$(book) wikiRoot (LLM Wiki)`, id: "wiki" },
          { label: `$(organization) people`, id: "people" },
          { label: `$(tools) Setup`, id: "setup" },
                    { label: `$(globe) 사이트 등록`, id: "sites" },
                    { label: `$(gear) Settings`, id: "settings" },
          { label: `$(refresh) Refresh trees`, id: "refresh" },
        ],
        {
          title: "Kampff",
          placeHolder: `작업=${activeLabel} · out최신=${outLabel}`,
        }
      );
      if (!pick) return;
      switch (pick.id) {
        case "builder":
          await vscode.commands.executeCommand("kampff.focusReportBuilder");
          break;
        case "activeReport":
          if (!active?.id) {
            void vscode.window.showWarningMessage(
              "작업 대상 ID 없음 — 보고서 만들기에서 ID 입력"
            );
            await vscode.commands.executeCommand("kampff.focusReportBuilder");
            break;
          }
          try {
            await openReportForTarget(active.id);
          } catch (e) {
            void vscode.window.showWarningMessage(
              e instanceof Error ? e.message : String(e)
            );
          }
          break;
        case "outLatest":
          {
            const latest = reports.latest();
            if (!latest) {
              void vscode.window.showWarningMessage("out/ 리포트 없음");
              break;
            }
            await vscode.commands.executeCommand(
              "kampff.openReportPath",
              latest.fsPath
            );
          }
          break;
        case "cpostActive":
          if (!active?.id) {
            void vscode.window.showWarningMessage("작업 대상 없음");
            break;
          }
          {
            const r = findLatestReport(active.id);
            const a = findLatestAnalysis(active.id);
            const p = r || a;
            if (!p) {
              void vscode.window.showWarningMessage(
                `analysis/report 없음: ${active.id}`
              );
              break;
            }
            await vscode.commands.executeCommand("kampff.generateCommunityPost", {
              fsPath: p,
              label: active.id,
              kind: r ? "report" : "analysis",
            } as KampffItem);
          }
          break;
        case "queue":
          await vscode.commands.executeCommand("kampff.openQueue");
          break;
        case "data":
          await vscode.commands.executeCommand("kampff.openDataRoot");
          break;
        case "wiki":
          await vscode.commands.executeCommand("kampff.openWikiRoot");
          break;
        case "people":
          await vscode.commands.executeCommand("kampff.openPeopleRoot");
          break;
        case "setup":
                  await vscode.commands.executeCommand("kampff.setup");
                  break;
                case "sites":
                  await vscode.commands.executeCommand("kampff.manageSites");
                  break;
                case "settings":
                  await vscode.commands.executeCommand("kampff.openSettings");
                  break;
        case "refresh":
          refreshAll();
          break;
        default:
          break;
      }
    }),

    vscode.commands.registerCommand("kampff.setup", async () => {
          await runSetupWizard();
          refreshAll();
        }),

        vscode.commands.registerCommand("kampff.manageSites", async () => {
          await runManageSitesWizard();
          refreshAll();
        }),

        vscode.commands.registerCommand(
          "kampff.openReport",
          async (item?: KampffItem) => {
        const p = item?.fsPath || reports.latest()?.fsPath;
        if (!p || !fs.existsSync(p)) {
          void vscode.window.showWarningMessage(
            "Kampff: no report HTML found under out/"
          );
          return;
        }
        const mode = getConfig().reportOpenMode;
        if (mode === "browser" || mode === "both") {
          await vscode.env.openExternal(vscode.Uri.file(p));
        }
        if (mode === "panel" || mode === "both") {
          ReportPanel.show(context, p, path.basename(p));
        }
      }
    ),

    vscode.commands.registerCommand(
      "kampff.openReportPath",
      async (reportPath?: string) => {
        const p = typeof reportPath === "string" ? reportPath : undefined;
        if (!p || !fs.existsSync(p)) {
          void vscode.window.showWarningMessage("Kampff: report path missing");
          return;
        }
        const mode = getConfig().reportOpenMode;
        if (mode === "browser" || mode === "both") {
          await vscode.env.openExternal(vscode.Uri.file(p));
        }
        if (mode === "panel" || mode === "both") {
          ReportPanel.show(context, p, path.basename(p));
        }
      }
    ),

    vscode.commands.registerCommand("kampff.focusReportBuilder", async () => {
          await vscode.commands.executeCommand("kampff.analyze.focus");
          analyzeView.refresh({ focusId: true });
        }),

        // Palette one-click — works even if webview button is dead
        vscode.commands.registerCommand("kampff.startMemberJob", async () => {
          const cfg = getConfig();
          const id = await vscode.window.showInputBox({
            title: "Kampff · 이 사람 분석 시작",
            prompt: "Handle / author id (예: elonmusk)",
            placeHolder: "author_id",
            ignoreFocusOut: true,
          });
          if (!id?.trim()) return;
          const nick = await vscode.window.showInputBox({
            title: "닉네임 (선택)",
            prompt: "비워도 됨",
            ignoreFocusOut: true,
          });
          try {
            const input = nick?.trim() ? `${id.trim()} ${nick.trim()}` : id.trim();
            const req = await submitAnalyze({
              input,
              platform: "x",
              mode: "member",
              depth: (cfg.defaultDepth as "quick" | "full") || "quick",
            });
            void vscode.window.showInformationMessage(
              `Kampff 시작: ${req.parsed.display} · 진행은 상태바/알림/출력(Kampff)`
            );
            await vscode.commands.executeCommand("kampff.focusReportBuilder");
          } catch (e) {
            const msg = e instanceof Error ? e.message : String(e);
            void vscode.window.showErrorMessage(`Kampff 실패: ${msg}`);
          }
        }),

    vscode.commands.registerCommand(
      "kampff.openGraph",
      async (item?: KampffItem | string) => {
        const {
          openGraphForTarget,
          renderGraphFromBundle,
          renderGraphFromJson,
          openGraphHtml,
        } = await import("./renderGraph");
        try {
          let html: string;
          if (typeof item === "string" && item.endsWith(".json") && item.includes("bundle")) {
            html = await renderGraphFromBundle(item, true);
          } else if (item && typeof item === "object" && "fsPath" in item) {
            const fp = (item as KampffItem).fsPath;
            if (fp.endsWith("-graph.html")) {
              await openGraphHtml(fp);
              html = fp;
            } else if (/bundle.*\.json$/i.test(fp) || path.basename(fp).startsWith("bundle")) {
              html = await renderGraphFromBundle(fp, true);
            } else if (fp.endsWith("-graph.json")) {
              html = await renderGraphFromJson(fp, true);
            } else {
              html = await openGraphForTarget(path.basename(fp));
            }
          } else {
            const id = getActiveTarget()?.id;
            html = await openGraphForTarget(id);
          }
          void vscode.window.showInformationMessage(`Graph: ${html}`);
        } catch (e) {
          void vscode.window.showErrorMessage(
            `Graph failed: ${e instanceof Error ? e.message : e}`
          );
        }
      }
    ),

    vscode.commands.registerCommand(
      "kampff.openDesk",
      async (item?: KampffItem | string) => {
        const { openDeskForTarget, renderDeskFromAnalysis } = await import(
          "./renderReport"
        );
        try {
          let desk: string;
          if (typeof item === "string" && item.endsWith("-analysis.json")) {
            desk = await renderDeskFromAnalysis(item, true);
          } else if (item && typeof item === "object" && "fsPath" in item) {
            const fp = (item as KampffItem).fsPath;
            if (fp.endsWith("-analysis.json")) {
              desk = await renderDeskFromAnalysis(fp, true);
            } else if (fp.endsWith("-desk.html")) {
              await vscode.commands.executeCommand("kampff.openReportPath", fp);
              desk = fp;
            } else if (fp.endsWith("-report.html")) {
              const a = fp.replace(/-report\.html$/i, "-analysis.json");
              if (fs.existsSync(a)) {
                desk = await renderDeskFromAnalysis(a, true);
              } else {
                throw new Error("sibling analysis.json missing");
              }
            } else {
              desk = await openDeskForTarget(path.basename(fp));
            }
          } else {
            const id =
              getActiveTarget()?.id ||
              (await vscode.window.showInputBox({
                title: "Kampff · Distance Desk",
                prompt: "author id (analysis.json must exist in out/)",
              }));
            if (!id) return;
            desk = await openDeskForTarget(id.trim());
          }
          void vscode.window.showInformationMessage(`Desk: ${desk}`);
        } catch (e) {
          void vscode.window.showErrorMessage(
            `Desk failed: ${e instanceof Error ? e.message : e}`
          );
        }
      }
    ),

    vscode.commands.registerCommand(
      "kampff.renderReport",
      async (item?: KampffItem | string) => {
        const { renderReportForTarget, renderReportFromAnalysis, findLatestAnalysis } =
          await import("./renderReport");
        try {
          let report: string;
          if (typeof item === "string" && item.endsWith("-analysis.json")) {
            report = await renderReportFromAnalysis(item, true);
          } else if (item && typeof item === "object" && "fsPath" in item) {
            const fp = (item as KampffItem).fsPath;
            if (fp.endsWith("-analysis.json")) {
              report = await renderReportFromAnalysis(fp, true);
            } else if (fp.endsWith("-report.html")) {
              const a = fp.replace(/-report\.html$/i, "-analysis.json");
              if (fs.existsSync(a)) {
                report = await renderReportFromAnalysis(a, true);
              } else {
                throw new Error("sibling analysis.json missing");
              }
            } else {
              // person dir or id folder name
              const id = path.basename(fp);
              report = await renderReportForTarget(id);
            }
          } else {
            const id = await vscode.window.showInputBox({
              title: "Kampff · Render report",
              prompt: "author id (analysis.json must exist in out/)",
              placeHolder: "member_id",
            });
            if (!id) return;
            const a = findLatestAnalysis(id.trim());
            if (!a) throw new Error(`no analysis for ${id}`);
            report = await renderReportFromAnalysis(a, true);
          }
          void vscode.window.showInformationMessage(`Report: ${report}`);
        } catch (e) {
          void vscode.window.showErrorMessage(
            `Render failed: ${e instanceof Error ? e.message : e}`
          );
        }
      }
    ),

    vscode.commands.registerCommand(
      "kampff.generateCommunityPost",
      async (item?: KampffItem | { fsPath?: string; label?: string; kind?: string }) => {
        // Resolve analysis for THIS item / active target — never silent out-latest.
        let html: string | undefined =
          item && "fsPath" in item && item.fsPath?.endsWith(".html")
            ? item.fsPath
            : undefined;
        let analysisPath: string | undefined =
          item && "fsPath" in item && item.fsPath?.endsWith(".json")
            ? item.fsPath
            : undefined;

        if (!analysisPath && html) {
          analysisPath = analysisPathForReport(html);
        }

        if (!analysisPath || !fs.existsSync(analysisPath)) {
          const active = getActiveTarget();
          if (active?.id) {
            analysisPath = findLatestAnalysis(active.id);
            html = findLatestReport(active.id);
          }
        }

        if (!analysisPath || !fs.existsSync(analysisPath)) {
          void vscode.window.showWarningMessage(
            "Kampff: dossier analysis 없음 — 먼저 이 사람 분석(①). 게시 초안은 분석 후 선택."
          );
          return;
        }

        // remember who we generated for
        try {
          const j0 = JSON.parse(fs.readFileSync(analysisPath, "utf8")) as {
            target?: { id?: string; nick?: string };
          };
          if (j0.target?.id) {
            setActiveTarget({
              id: j0.target.id,
              nick: j0.target.nick,
              lastAction: "community",
            });
            updateStatus(reportsRef || reports);
          }
        } catch {
          /* ignore */
        }

        let seed: Record<string, string> = {};
        try {
          const j = JSON.parse(
            fs.readFileSync(analysisPath, "utf8")
          ) as Record<string, unknown>;
          const target = (j.target || {}) as Record<string, string>;
          const meta = (j.meta || {}) as Record<string, string>;
          const matrix = (j.matrix || {}) as Record<string, string>;
          const trigger = (j.trigger || {}) as Record<string, string>;
          const cp = (j.community_post ||
            j.community_voice ||
            {}) as Record<string, string>;
          seed = {
                      nick: target.nick || "",
                      id: target.id || "",
                      platform: meta.platform || "",
                      board: cp.board || meta.platform || "",
                      tldr: String(j.tldr || ""),
                      one_line: matrix.one_line || "",
                      trigger: trigger.summary || "",
                      recommendation: String(j.recommendation || ""),
                      mechanism: cp.mechanism || "",
                      claim: cp.claim || "",
                      anchor: cp.anchor || "",
                      point: cp.point || "",
                      preset: cp.text_ko || cp.text || "",
                    };
        } catch (e) {
          void vscode.window.showErrorMessage(
            `Kampff: bad analysis.json (${e instanceof Error ? e.message : e})`
          );
          return;
        }
        const text = generateCommunityPost(seed);
        await vscode.env.clipboard.writeText(text);
        const doc = await vscode.workspace.openTextDocument({
          content: text,
          language: "markdown",
        });
        await vscode.window.showTextDocument(doc, {
          preview: true,
          viewColumn: vscode.ViewColumn.Beside,
        });
        if (html && fs.existsSync(html)) {
          ReportPanel.show(context, html, path.basename(html));
        }
        // quiet: status bar only, no modal
        void vscode.window.setStatusBarMessage(
          `Kampff 게시초안(선택) · ${seed.nick || seed.id || "?"} · copied`,
          3500
        );
      }
    ),

    vscode.commands.registerCommand(
      "kampff.openHtmlExternal",
      async (item?: KampffItem) => {
        const p = item?.fsPath || reports.latest()?.fsPath;
        if (!p) return;
        await vscode.env.openExternal(vscode.Uri.file(p));
      }
    ),

    vscode.commands.registerCommand(
      "kampff.openReportBrowser",
      async (item?: KampffItem) => {
        if (item?.fsPath && fs.existsSync(item.fsPath)) {
          await vscode.env.openExternal(vscode.Uri.file(item.fsPath));
          return;
        }
        let id = getActiveTarget()?.id?.trim() || "";
        if (!id) {
          id =
            (
              await vscode.window.showInputBox({
                title: "브라우저로 리포트",
                prompt: "Handle / ID",
                placeHolder: "JerryKi28272668",
                ignoreFocusOut: true,
              })
            )?.trim() || "";
        }
        if (!id) return;
        const found = findReportsByDepth(id);
        if (!found.length) {
          void vscode.window.showWarningMessage(
            `Kampff: ${id} 리포트 없음 (빠른/FULL 각각 한 번씩 돌리면 둘 다 남음)`
          );
          return;
        }
        let pick = found[0];
        if (found.length > 1) {
          const chosen = await vscode.window.showQuickPick(
            found.map((r) => ({
              label: r.depth === "full" ? "FULL" : "빠른",
              description: path.basename(r.reportPath),
              detail: new Date(r.mtimeMs).toLocaleString(),
              r,
            })),
            { title: `브라우저 · ${id}`, placeHolder: "빠른 / FULL" }
          );
          if (!chosen) return;
          pick = chosen.r;
        }
        await openReportInBrowser(id, pick.depth);
      }
    ),

    vscode.commands.registerCommand(
      "kampff.openAnalysisJson",
      async (item?: KampffItem) => {
        let p = item?.fsPath;
        if (p && p.endsWith(".html")) {
          p = analysisPathForReport(p);
        } else if (!p) {
          const latest = reports.latest()?.fsPath;
          p = latest ? analysisPathForReport(latest) : undefined;
        }
        if (!p || !fs.existsSync(p)) {
          void vscode.window.showWarningMessage(
            "Kampff: analysis.json not found"
          );
          return;
        }
        const doc = await vscode.workspace.openTextDocument(p);
        await vscode.window.showTextDocument(doc, { preview: true });
      }
    ),

    vscode.commands.registerCommand("kampff.openDataRoot", async () => {
      const root = getConfig().dataRoot;
      if (!root || !fs.existsSync(root)) {
        const fix = await vscode.window.showErrorMessage(
          `Kampff dataRoot missing: ${root || "(empty)"}`,
          "Setup paths…"
        );
        if (fix) await vscode.commands.executeCommand("kampff.setup");
        return;
      }
      await vscode.commands.executeCommand(
        "revealFileInOS",
        vscode.Uri.file(root)
      );
    }),

    vscode.commands.registerCommand("kampff.openWikiRoot", async () => {
      const root = wikiRoot();
      if (!root) {
        const fix = await vscode.window.showWarningMessage(
          "Kampff wikiRoot empty — Setup에서 LLM Wiki shelf를 지정하세요.",
          "Setup paths…"
        );
        if (fix) await vscode.commands.executeCommand("kampff.setup");
        return;
      }
      try {
        ensureWikiLayout();
      } catch {
        /* ignore */
      }
      if (!fs.existsSync(root)) {
        fs.mkdirSync(root, { recursive: true });
        ensureWikiLayout();
      }
      await vscode.commands.executeCommand(
        "revealFileInOS",
        vscode.Uri.file(root)
      );
    }),

    vscode.commands.registerCommand("kampff.openPeopleRoot", async () => {
      const root = peopleDir();
      if (!root || !fs.existsSync(root)) {
        void vscode.window.showWarningMessage(
          `People root missing: ${root || "(empty)"} — run accumulate after analyze.`
        );
        return;
      }
      await vscode.commands.executeCommand(
        "revealFileInOS",
        vscode.Uri.file(root)
      );
    }),

    vscode.commands.registerCommand("kampff.openQueue", async () => {
      const q = queueDir();
      if (!q) return;
      fs.mkdirSync(q, { recursive: true });
      await vscode.commands.executeCommand(
        "revealFileInOS",
        vscode.Uri.file(q)
      );
    }),

    vscode.commands.registerCommand(
      "kampff.openPeopleNotes",
      async (item?: PeopleItem | KampffItem) => {
        const dir = item?.fsPath;
        if (!dir) return;
        const target = fs.statSync(dir).isDirectory()
          ? notesPathForPerson(dir)
          : dir;
        if (!fs.existsSync(target)) {
          void vscode.window.showWarningMessage("NOTES/profile not found");
          return;
        }
        if (fs.statSync(target).isDirectory()) {
          await vscode.commands.executeCommand(
            "revealFileInOS",
            vscode.Uri.file(target)
          );
          return;
        }
        const doc = await vscode.workspace.openTextDocument(target);
        await vscode.window.showTextDocument(doc, { preview: true });
      }
    ),

    vscode.commands.registerCommand("kampff.openSettings", async () => {
      await vscode.commands.executeCommand(
        "workbench.action.openSettings",
        "@ext:YangKangSung.kampff"
      );
    }),

    vscode.commands.registerCommand(
      "kampff.copyPath",
      async (item?: KampffItem | PeopleItem) => {
        if (!item?.fsPath) return;
        await vscode.env.clipboard.writeText(item.fsPath);
        void vscode.window.setStatusBarMessage(
          `Kampff: copied ${item.fsPath}`,
          2500
        );
      }
    ),

    vscode.commands.registerCommand(
      "kampff.reveal",
      async (item?: KampffItem | PeopleItem) => {
        const p = item?.fsPath || getConfig().dataRoot;
        if (!p || !fs.existsSync(p)) return;
        await vscode.commands.executeCommand(
          "revealFileInOS",
          vscode.Uri.file(p)
        );
      }
    ),

    vscode.workspace.onDidChangeConfiguration((e) => {
      if (e.affectsConfiguration("kampff")) {
        armTimer(refreshTrees);
        // Soft config push to analyze form — no focus steal
        refreshAll();
      }
    })
  );

  // first-run nudge
  const cfg = getConfig();
  if (!cfg.dataRoot || !fs.existsSync(cfg.dataRoot)) {
    void vscode.window
      .showWarningMessage(
        "Kampff: dataRoot not found. Configure paths to browse reports.",
        "Setup paths…",
        "Settings"
      )
      .then(async (c) => {
        if (c === "Setup paths…")
          await vscode.commands.executeCommand("kampff.setup");
        if (c === "Settings")
          await vscode.commands.executeCommand("kampff.openSettings");
      });
  }

  armTimer(refreshTrees);
  refreshAll();
}

async function runSetupWizard(): Promise<void> {
  const cfg = getConfig();

  const dataPick = await vscode.window.showOpenDialog({
    canSelectFiles: false,
    canSelectFolders: true,
    canSelectMany: false,
    openLabel: "Select runtime KAMPFF_DATA (dataRoot)",
    title: "Kampff · dataRoot (runtime scratch: inbox/queue/out)",
    defaultUri: cfg.dataRoot ? vscode.Uri.file(cfg.dataRoot) : undefined,
  });
  if (dataPick?.[0]) {
    await updateConfig("dataRoot", dataPick[0].fsPath);
  }

  const wikiPick = await vscode.window.showOpenDialog({
    canSelectFiles: false,
    canSelectFolders: true,
    canSelectMany: false,
    openLabel: "Select LLM Wiki shelf (wikiRoot)",
    title: "Kampff · wikiRoot (durable people/ + reports/)",
    defaultUri: cfg.wikiRoot ? vscode.Uri.file(cfg.wikiRoot) : undefined,
  });
  if (wikiPick?.[0]) {
    await updateConfig("wikiRoot", wikiPick[0].fsPath);
    try {
      ensureWikiLayout(getConfig());
    } catch {
      /* ignore */
    }
  }

  const skillsPick = await vscode.window.showOpenDialog({
    canSelectFiles: false,
    canSelectFolders: true,
    canSelectMany: false,
    openLabel: "Select kampff-skills clone",
    title: "Kampff · skillsDevRoot",
    defaultUri: cfg.skillsDevRoot
      ? vscode.Uri.file(cfg.skillsDevRoot)
      : undefined,
  });
  if (skillsPick?.[0]) {
    await updateConfig("skillsDevRoot", skillsPick[0].fsPath);
  }

  const launch = await vscode.window.showQuickPick(
    [
      {
        label: "auto",
        description: "One-click Hermes + progress (recommended)",
      },
      {
        label: "terminal",
        description: "Queue + helper terminal",
      },
      { label: "hermes", description: "hermes chat -q with prompt" },
      { label: "none", description: "Queue files only" },
    ],
    { title: "After Analyze queue…" }
  );
  if (launch) await updateConfig("analyzeLaunch", launch.label);

  const depth = await vscode.window.showQuickPick(
    [
      { label: "quick", description: "Light / public-first" },
      { label: "full", description: "Full lawful collect" },
    ],
    { title: "Default depth" }
  );
  if (depth) await updateConfig("defaultDepth", depth.label);

  const py = await vscode.window.showInputBox({
    title: "Python path",
    value: cfg.pythonPath || "python",
    placeHolder: "python · py · full path to venv python.exe",
  });
  if (py !== undefined && py.trim()) await updateConfig("pythonPath", py.trim());

  const siteStep = await vscode.window.showQuickPick(
    [
      {
        label: "사이트 등록/편집",
        description: "URL + 로그인 ID/비밀번호 → Analyze 선택 목록",
        id: "manage",
      },
      {
        label: "사이트 단계 건너뛰기",
        description: "이미 등록된 목록 유지",
        id: "skip",
      },
    ],
    { title: "Kampff · 등록 사이트" }
  );
  if (siteStep?.id === "manage") {
    await runManageSitesWizard();
  }

  const next = getConfig();
  const sites = listEnabledSites();
  const siteLine = sites.length
    ? sites.map((s) => s.id).join(", ")
    : "(none)";
  void vscode.window.showInformationMessage(
    `Kampff: saved. runtime=${next.dataRoot || "(empty)"} · wiki=${next.wikiRoot || "(none)"} · sites=${siteLine}`
  );
}

function armTimer(fn: () => void): void {
  if (refreshTimer) clearInterval(refreshTimer);
  const ms = getConfig().autoRefreshMs;
  if (ms > 0) {
    refreshTimer = setInterval(fn, ms);
  }
}

function updateStatus(reports: ReportsProvider): void {
  if (!status) return;
  if (!getConfig().showStatusBar) {
    status.hide();
    return;
  }
  const cfg = getConfig();
  const latest = reports.latest();
  const active = getActiveTarget();
  const rootOk = !!(cfg.dataRoot && fs.existsSync(cfg.dataRoot));
  if (!rootOk) {
    status.text = "$(warning) Kampff · setup";
    status.tooltip = "dataRoot missing — click to setup";
    status.backgroundColor = new vscode.ThemeColor(
      "statusBarItem.warningBackground"
    );
    status.show();
    return;
  }
  status.backgroundColor = undefined;
  const outWho = latest
    ? reportDisplayLabel(latest.fsPath, latest.meta)
    : "";
  const outDist = latest?.meta?.distance || "";
  const work = active?.id ? formatTarget(active) : "";

  if (!work && !outWho) {
    status.text = "$(search) Kampff";
    status.tooltip = "대상 없음 · 클릭 메뉴";
    status.show();
    return;
  }

  // Always show BOTH so "neutral" never silently means 굿데이G while user works on double2
  if (work && outWho) {
    status.text = `$(graph) 작업:${work} · out:${outWho}${outDist ? " " + outDist : ""}`;
  } else if (work) {
    status.text = `$(graph) 작업:${work}`;
  } else {
    status.text = `$(graph) out:${outWho}${outDist ? " · " + outDist : ""}`;
  }
  status.tooltip = [
    work ? `지금 작업 대상: ${work} (${active?.lastAction || "—"})` : "작업 대상: (폼에서 ID 지정)",
    outWho ? `out mtime 최신: ${outWho}` : "out 리포트 없음",
    latest?.fsPath || "",
    latest?.meta?.tldr || "",
    "클릭: 메뉴 (이 대상 vs out 최신 구분)",
  ]
    .filter(Boolean)
    .join("\n");
  status.show();
}

export function deactivate(): void {
  if (refreshTimer) clearInterval(refreshTimer);
  disposeKampffLog();
}
