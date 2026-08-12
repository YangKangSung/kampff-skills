#!/usr/bin/env node
/**
 * One-shot live workflow:
 *   1. junction repo → editor extensions dirs (.kampff-dev)
 *   2. tsc -watch forever
 *
 * After first Reload Window, save:
 *   media/*  → webview soft reload
 *   src/*    → tsc → out/* → extension host restart
 */
"use strict";

const { spawn, spawnSync } = require("child_process");
const path = require("path");

const root = path.resolve(__dirname, "..");
const npmCmd = process.platform === "win32" ? "npm.cmd" : "npm";
const node = process.execPath;

function run(label, args, opts = {}) {
  console.log(`\n[kampff-dev] ${label}`);
  // win32 shell:true splits unquoted "C:\Program Files\..." at space.
  // Absolute exe (node) → no shell. Bare .cmd (npm.cmd) → shell.
  const file = args[0];
  const useShell =
    process.platform === "win32" && !path.isAbsolute(file);
  const r = spawnSync(file, args.slice(1), {
    cwd: root,
    stdio: "inherit",
    shell: useShell,
    ...opts,
  });
  if (r.status !== 0) {
    console.error(`[kampff-dev] failed: ${label} (exit ${r.status})`);
    process.exit(r.status || 1);
  }
}

console.log("╔══════════════════════════════════════════════╗");
console.log("║  Kampff live dev                             ║");
console.log("║  edit → save → see (auto)                    ║");
console.log("╚══════════════════════════════════════════════╝");

run("link extension install path", [node, path.join("scripts", "dev-link.js")]);
run("compile once", [npmCmd, "run", "compile"]);

console.log(`
[kampff-dev] ready
  1) VS Code:  Developer: Reload Window  (first time only)
  2) keep this terminal open (tsc -watch)
  3) save files:
       media/**     → Analyze webview refresh (fast)
       src/**       → extension host restart (~1s after tsc)
       package.json → full window reload

  status bar shows:  Kampff DEV
  stop: Ctrl+C · unlink: npm run dev:unlink
`);

const child = spawn(npmCmd, ["run", "watch"], {
  cwd: root,
  stdio: "inherit",
  shell: process.platform === "win32",
});

const stop = () => {
  try {
    child.kill("SIGTERM");
  } catch {
    /* ignore */
  }
  process.exit(0);
};
process.on("SIGINT", stop);
process.on("SIGTERM", stop);

child.on("exit", (code) => process.exit(code || 0));
