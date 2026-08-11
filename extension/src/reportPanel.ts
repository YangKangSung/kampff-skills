import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";
import { generateCommunityPost } from "./communityPost";

/**
 * Opens dossier HTML. Does NOT put Community-post chrome on top.
 * Optional export is collapsed at the bottom only.
 */
export class ReportPanel {
  public static readonly viewType = "kampff.report";
  private static current: ReportPanel | undefined;

  private readonly panel: vscode.WebviewPanel;
  private disposables: vscode.Disposable[] = [];
  private htmlPath = "";

  static show(
    context: vscode.ExtensionContext,
    htmlPath: string,
    title?: string
  ): void {
    const col = vscode.ViewColumn.Beside;
    if (ReportPanel.current) {
      ReportPanel.current.panel.reveal(col);
      ReportPanel.current.load(htmlPath, title);
      return;
    }
    const panel = vscode.window.createWebviewPanel(
      ReportPanel.viewType,
      title || "Kampff dossier",
      col,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
        localResourceRoots: [vscode.Uri.file(path.dirname(htmlPath))],
      }
    );
    ReportPanel.current = new ReportPanel(panel, context, htmlPath, title);
  }

  private constructor(
    panel: vscode.WebviewPanel,
    _context: vscode.ExtensionContext,
    htmlPath: string,
    title?: string
  ) {
    this.panel = panel;
    this.load(htmlPath, title);
    this.panel.onDidDispose(() => this.dispose(), null, this.disposables);
    this.panel.webview.onDidReceiveMessage(
          async (msg: { type?: string; tone?: string }) => {
            if (msg?.type === "genCommunity") {
              await this.generateAndFill(msg.tone);
            } else if (msg?.type === "copied") {
              void vscode.window.setStatusBarMessage(
                "Kampff: 게시초안 copied",
                2500
              );
            }
          },
          null,
          this.disposables
        );
      }

  private analysisPathFor(htmlPath: string): string | undefined {
    const base = htmlPath.replace(/-report\.html$/i, "");
    const a = `${base}-analysis.json`;
    if (fs.existsSync(a)) return a;
    const stem = path.basename(htmlPath, ".html").replace(/-report$/, "");
    const alt = path.join(path.dirname(htmlPath), `${stem}-analysis.json`);
    return fs.existsSync(alt) ? alt : undefined;
  }

  private async generateAndFill(tone?: string): Promise<void> {
      const ap = this.analysisPathFor(this.htmlPath);
      let seed: Record<string, string> = {};
      if (ap) {
        try {
          const j = JSON.parse(fs.readFileSync(ap, "utf8")) as Record<
            string,
            unknown
          >;
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
            preset_short: cp.text_ko_short || "",
            tone: cp.tone || "",
          };
        } catch {
          /* refuse path */
        }
      }
      const text = generateCommunityPost(seed, tone);
    this.panel.webview.postMessage({ type: "fillCommunity", text });
    // only copy when it's a real draft, not refuse banner
    if (!text.startsWith("[게시 초안 생성 불가]")) {
      await vscode.env.clipboard.writeText(text);
      void vscode.window.setStatusBarMessage(
        "Kampff 게시초안(선택) · copied",
        3000
      );
    } else {
      void vscode.window.setStatusBarMessage(
        "Kampff: 게시초안 거부 — dossier 본문이 분석",
        4000
      );
    }
  }

  private load(htmlPath: string, title?: string): void {
    this.htmlPath = htmlPath;
    const baseName = path.basename(htmlPath);
    this.panel.title = title || baseName.replace(/-report\.html$/i, " dossier");
    const dir = path.dirname(htmlPath);
    const raw = fs.readFileSync(htmlPath, "utf8");
    const baseUri = this.panel.webview.asWebviewUri(vscode.Uri.file(dir));
    let html = raw;
    if (!/<base\s/i.test(html)) {
      html = html.replace(
        /<head([^>]*)>/i,
        `<head$1><base href="${baseUri}/">`
      );
    }

    // Dossier-first banner (always): remind this IS the analysis
    const who = baseName.replace(/-report\.html$/i, "");
    const banner = `
    <div id="kampff-dossier-bar" style="position:sticky;top:0;z-index:100;font:12.5px/1.4 system-ui,-apple-system,Segoe UI,sans-serif;color:#f7f8f8;background:rgba(15,16,17,.94);backdrop-filter:blur(12px);border-bottom:1px solid rgba(255,255,255,.08);padding:10px 14px">
      <div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center">
        <span style="display:inline-flex;align-items:center;gap:8px;font-weight:600;letter-spacing:-.02em" title="dossier = 한 사람에 대한 종합 분석 묶음">
          <span style="width:8px;height:8px;border-radius:99px;background:#2dd4bf;box-shadow:0 0 0 3px rgba(45,212,191,.25)"></span>
          이 사람 분석 보고서
        </span>
        <span style="font-size:11px;color:#8a8f98;display:inline-flex;flex-wrap:wrap;gap:6px;align-items:center">
          <span title="파일/대상 식별">${who}</span>
          <span title="TL;DR = 너무 길어서 안 읽을 때 보는 짧은 요약">· 짧은 요약</span>
          <span title="L1–L5 = 분석 깊이/레이어 단계 표시(리포트 본문 구조)">· 단계(L1–L5)</span>
          <span title="Distance = 나와의 관계·태도 거리 가설 (align/neutral/caution/hostile 등)">· 관계 거리</span>
          <span title="Evidence = 판단에 쓴 근거 글·댓글">· 근거</span>
        </span>
        <span style="flex:1"></span>
        <span style="font-size:10px;color:#62666d;border:1px solid rgba(255,255,255,.08);border-radius:999px;padding:3px 8px" title="아래 export는 커뮤니티에 올릴 글 초안일 뿐, 분석 본체가 아닙니다">게시 초안 ≠ 분석</span>
      </div>
      <p style="margin:6px 0 0;font-size:10.5px;color:#62666d;line-height:1.4">점/배지에 마우스를 올리면 용어 설명이 뜹니다. 이 화면이 분석 결과 본체입니다.</p>
    </div>`;
    html = html.replace(/<body([^>]*)>/i, `<body$1>${banner}`);

    // Optional export: collapsed FOOTER only if page has no cpGen; never primary chrome
    if (!/id=["']cpGen["']/.test(html)) {
      const foot = `
<details id="kampff-export-foot" style="margin:24px 12px 40px;padding:12px 14px;border:1px dashed rgba(255,255,255,.12);border-radius:10px;background:rgba(0,0,0,.25);font:12.5px/1.4 system-ui,sans-serif;color:#d0d6e0">
  <summary style="cursor:pointer;font-weight:600;color:#8a8f98" title="export = 밖으로 빼기. 분석 본체가 아닙니다">선택 · 게시글 초안 내보내기 (분석 아님)</summary>
  <p style="font-size:11px;color:#8a8f98;margin:8px 0">말투만 고릅니다. 분석 JSON에 초안 재료(seed)가 있을 때만 나옵니다. AI/ops 태그 문구는 넣지 않습니다.</p>
  <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:8px">
    <label style="font-size:11px;color:#8a8f98" title="tone = 초안 말투">말투
      <select id="vsCpTone" style="margin-left:4px;padding:5px 8px;border-radius:6px;border:1px solid rgba(255,255,255,.12);background:rgba(0,0,0,.35);color:#e2e4e7">
        <option value="peer" selected>동료 톤 (peer)</option>
        <option value="short">짧은 2–3줄 (short)</option>
        <option value="board">보드용 원문 유지 (board)</option>
      </select>
    </label>
    <button type="button" id="vsCpGen" style="cursor:pointer;padding:7px 12px;border-radius:8px;border:1px solid rgba(255,255,255,.12);background:rgba(255,255,255,.04);color:#e2e4e7;font-weight:600">초안 만들기</button>
    <button type="button" id="vsCpCopy" style="cursor:pointer;padding:7px 12px;border-radius:8px;border:1px solid rgba(255,255,255,.1);background:transparent;color:#8a8f98">복사</button>
    <span id="vsCpSt" style="color:#8a8f98;font-size:11px;align-self:center"></span>
  </div>
  <textarea id="vsCpOut" style="display:block;width:100%;min-height:90px;box-sizing:border-box;padding:10px;border-radius:8px;border:1px solid rgba(255,255,255,.08);background:rgba(0,0,0,.35);color:#f7f8f8;font:13px/1.45 system-ui,sans-serif;resize:vertical" placeholder="비어 있으면 정상입니다. 재료가 없으면 거부 메시지가 옵니다."></textarea>
</details>
<script>
(function(){
  const vscode = acquireVsCodeApi();
  const out = document.getElementById('vsCpOut');
  const st = document.getElementById('vsCpSt');
  const toneEl = document.getElementById('vsCpTone');
  function tone(){ return (toneEl && toneEl.value) || 'peer'; }
  document.getElementById('vsCpGen')?.addEventListener('click', () => {
    st.textContent = '…';
    vscode.postMessage({ type: 'genCommunity', tone: tone() });
  });
  document.getElementById('vsCpCopy')?.addEventListener('click', async () => {
    if (!out.value.trim()) { vscode.postMessage({ type: 'genCommunity', tone: tone() }); return; }
    if (out.value.indexOf('[게시 초안 생성 불가]') === 0) { st.textContent = '거부문 — copy 안 함'; return; }
    try {
      await navigator.clipboard.writeText(out.value);
      st.textContent = 'copied';
      vscode.postMessage({ type: 'copied' });
    } catch (e) {
      out.select();
      st.textContent = 'select+copy';
    }
  });
  window.addEventListener('message', (ev) => {
    const m = ev.data || {};
    if (m.type === 'fillCommunity') {
      out.value = m.text || '';
      st.textContent = (m.text || '').indexOf('[게시 초안 생성 불가]') === 0
        ? '거부 — dossier가 분석'
        : 'ok · ' + tone();
    }
  });
})();
</script>`;
      html = html.replace(/<\/body>/i, foot + "</body>");
    } else {
      // page has built-in cp — bridge fill only; do not promote
      const bridge = `
<script>
(function(){
  const vscode = acquireVsCodeApi();
  window.addEventListener('message', (ev) => {
    const m = ev.data || {};
    if (m.type === 'fillCommunity') {
      const out = document.getElementById('cpOut');
      const st = document.getElementById('cpStatus');
      if (out) out.value = m.text || '';
      if (st) st.textContent = (m.text || '').indexOf('[게시 초안 생성 불가]') === 0
        ? '거부 — dossier가 분석'
        : 'host fill';
    }
  });
})();
</script>`;
      html = html.replace(/<\/body>/i, bridge + "</body>");
    }
    this.panel.webview.html = html;
  }

  private dispose(): void {
    ReportPanel.current = undefined;
    while (this.disposables.length) {
      this.disposables.pop()?.dispose();
    }
  }
}
