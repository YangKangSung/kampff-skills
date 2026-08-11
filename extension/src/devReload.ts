import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";
import { kampffLog } from "./log";

export type DevReloadHooks = {
  /** media/* change — rebuild webview HTML (fast, no host restart). */
  onMedia?: () => void;
  /** out/* change after tsc — restart extension host. */
  onOut?: () => void;
};

function isDevMode(context: vscode.ExtensionContext): boolean {
  const marker = path.join(context.extensionPath, ".kampff-dev");
  return (
    context.extensionMode === vscode.ExtensionMode.Development ||
    fs.existsSync(marker)
  );
}

/**
 * Edit → see workflow (dev only):
 * - media/**  → soft reload webview (cache-bust)
 * - out/**    → restart extension host (TS)
 * - package.json contributes → full window reload
 */
export function maybeStartDevReload(
  context: vscode.ExtensionContext,
  hooks: DevReloadHooks = {}
): void {
  if (!isDevMode(context)) {
    return;
  }

  let mediaTimer: NodeJS.Timeout | undefined;
  let outTimer: NodeJS.Timeout | undefined;
  let pkgTimer: NodeJS.Timeout | undefined;

  const ignoreName = (name: string): boolean =>
    !name ||
    name.endsWith(".map") ||
    name.endsWith(".d.ts") ||
    name.endsWith(".tsbuildinfo") ||
    name === ".kampff-dev" ||
    name.startsWith(".");

  const softMedia = (reason: string): void => {
    if (mediaTimer) clearTimeout(mediaTimer);
    mediaTimer = setTimeout(() => {
      kampffLog(`dev soft ← ${reason}`);
      void vscode.window.setStatusBarMessage(
        "$(sync) Kampff media reload",
        2500
      );
      if (hooks.onMedia) {
        hooks.onMedia();
      } else {
        void vscode.commands.executeCommand("kampff.devSoftReload");
      }
    }, 250);
  };

  const hardOut = (reason: string): void => {
    if (outTimer) clearTimeout(outTimer);
    outTimer = setTimeout(() => {
      kampffLog(`dev host restart ← ${reason}`);
      void vscode.window.setStatusBarMessage(
        "$(sync) Kampff extension host restart…",
        3000
      );
      if (hooks.onOut) {
        hooks.onOut();
      }
      void vscode.commands.executeCommand(
        "workbench.action.restartExtensionHost"
      );
    }, 900);
  };

  const fullWindow = (reason: string): void => {
    if (pkgTimer) clearTimeout(pkgTimer);
    pkgTimer = setTimeout(() => {
      kampffLog(`dev window reload ← ${reason}`);
      void vscode.commands.executeCommand("workbench.action.reloadWindow");
    }, 1200);
  };

  const watchTree = (
    rel: string,
    onFile: (relPath: string) => void
  ): void => {
    const dir = path.join(context.extensionPath, rel);
    if (!fs.existsSync(dir)) return;
    try {
      const w = fs.watch(dir, { recursive: true }, (_ev, file) => {
        const name = file?.toString() ?? "";
        if (ignoreName(path.basename(name))) return;
        onFile(`${rel}/${name || "?"}`);
      });
      context.subscriptions.push({ dispose: () => w.close() });
    } catch (err) {
      kampffLog(`dev watch failed ${rel}: ${err}`);
    }
  };

  watchTree("media", softMedia);
  watchTree("out", hardOut);

  try {
    const pkg = path.join(context.extensionPath, "package.json");
    const w = fs.watch(pkg, () => fullWindow("package.json"));
    context.subscriptions.push({ dispose: () => w.close() });
  } catch (err) {
    kampffLog(`dev watch package.json failed: ${err}`);
  }

  const bar = vscode.window.createStatusBarItem(
    vscode.StatusBarAlignment.Right,
    1
  );
  bar.text = "$(flame) Kampff DEV";
  bar.tooltip =
    "Live reload on\n• media → webview\n• out (tsc) → extension host\n• package.json → window";
  bar.command = "kampff.devSoftReload";
  bar.show();
  context.subscriptions.push(bar);

  kampffLog(
    `dev live-reload on ${
      context.extensionMode === vscode.ExtensionMode.Development
        ? "(Extension Development Host)"
        : "(.kampff-dev link)"
    }`
  );
}

export function devMarkerPath(extensionPath: string): string {
  return path.join(extensionPath, ".kampff-dev");
}
