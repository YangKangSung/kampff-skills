import * as vscode from "vscode";

let channel: vscode.OutputChannel | undefined;

/** Lazy-create Output channel "Kampff" (View → Output dropdown). */
export function getKampffChannel(): vscode.OutputChannel {
  if (!channel) {
    channel = vscode.window.createOutputChannel("Kampff");
  }
  return channel;
}

/** Append a timestamped line. Safe before activate finishes. */
export function kampffLog(msg: string): void {
  const line = `[${new Date().toLocaleTimeString()}] ${msg}`;
  getKampffChannel().appendLine(line);
}

export function kampffLogBlock(title: string, lines: string[]): void {
  const ch = getKampffChannel();
  const ts = new Date().toLocaleTimeString();
  ch.appendLine(`[${ts}] ── ${title} ──`);
  for (const ln of lines) {
    ch.appendLine(`[${ts}]   ${ln}`);
  }
}

/** Focus Output panel on Kampff channel. */
export function showKampffLog(preserveFocus = false): void {
  getKampffChannel().show(preserveFocus);
}

export function disposeKampffLog(): void {
  channel?.dispose();
  channel = undefined;
}
