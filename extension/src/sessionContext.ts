/**
 * Single source of truth for "who am I working on right now".
 * Prevents cognitive dissonance: buttons must act on THIS id, not mtime-latest out/.
 */
import * as vscode from "vscode";

export interface ActiveTarget {
  id: string;
  nick?: string;
  platform?: string;
  /** queue | render | open | pick */
  lastAction?: string;
  updatedAt: number;
}

let active: ActiveTarget | undefined;
const emitter = new vscode.EventEmitter<ActiveTarget | undefined>();
export const onDidChangeActiveTarget = emitter.event;

export function getActiveTarget(): ActiveTarget | undefined {
  return active;
}

export function setActiveTarget(
  partial: Omit<ActiveTarget, "updatedAt"> & { updatedAt?: number }
): ActiveTarget {
  const id = (partial.id || "").trim();
  active = {
    id,
    nick: (partial.nick || "").trim() || undefined,
    platform: partial.platform,
    lastAction: partial.lastAction,
    updatedAt: partial.updatedAt ?? Date.now(),
  };
  emitter.fire(active);
  return active;
}

export function clearActiveTarget(): void {
  active = undefined;
  emitter.fire(undefined);
}

export function formatTarget(t?: ActiveTarget | null): string {
  if (!t?.id) return "(대상 없음)";
  if (t.nick && t.nick !== t.id) return `${t.nick} · ${t.id}`;
  return t.id;
}
