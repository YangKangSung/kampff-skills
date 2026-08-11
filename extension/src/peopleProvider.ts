import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";
import { peopleDir } from "./config";

export class PeopleItem extends vscode.TreeItem {
  constructor(
    public readonly label: string,
    public readonly fsPath: string,
    public readonly kind: "platform" | "person" | "file",
    collapsible: vscode.TreeItemCollapsibleState,
    public readonly meta?: {
      distance?: string;
      risk?: number;
      nick?: string;
      runs?: number;
    }
  ) {
    super(label, collapsible);
    this.resourceUri = vscode.Uri.file(fsPath);
    this.contextValue = `kampff.people.${kind}`;
    if (kind === "person") {
      this.iconPath = personDistanceIcon(meta?.distance);
      const d = meta?.distance || "?";
      const r = meta?.risk != null ? `risk ${meta.risk}` : "";
      const runs = meta?.runs != null ? `${meta.runs} runs` : "";
      this.description = [d, r, runs].filter(Boolean).join(" · ");
      const tip = new vscode.MarkdownString(
              [
                `**${label}**` + (meta?.nick ? ` · ${meta.nick}` : ""),
                "People — 이 사람 누적 폴더 (NOTES·이력).",
                meta?.distance
                  ? `distance \`${meta.distance}\` — 나와의 관계·태도 거리(가설)`
                  : "",
                meta?.risk != null
                  ? `authorship risk \`${meta.risk}\` — 계정 정체성/대필 쪽 신호(가설)`
                  : "",
                meta?.runs != null ? `runs \`${meta.runs}\` — 이 사람으로 돌린 분석 횟수` : "",
                "",
                `\`${fsPath.replace(/\\/g, "/")}\``,
              ]
                .filter(Boolean)
                .join("\n\n")
            );
      tip.supportThemeIcons = true;
      this.tooltip = tip;
      this.command = {
        command: "kampff.openPeopleNotes",
        title: "Open NOTES",
        arguments: [this],
      };
    } else if (kind === "platform") {
      this.iconPath = new vscode.ThemeIcon(
        "globe",
        new vscode.ThemeColor("charts.purple")
      );
    } else {
      this.iconPath = new vscode.ThemeIcon("file");
      this.command = {
        command: "vscode.open",
        title: "Open",
        arguments: [vscode.Uri.file(fsPath)],
      };
    }
  }
}

function personDistanceIcon(distance?: string): vscode.ThemeIcon {
  const d = (distance || "").toLowerCase();
  let colorId = "charts.blue";
  if (d.includes("align") || d === "close" || d === "near") colorId = "charts.green";
  else if (d.includes("caution") || d.includes("watch")) colorId = "charts.yellow";
  else if (
    d.includes("hostile") ||
    d.includes("far") ||
    d.includes("danger") ||
    d.includes("high")
  )
    colorId = "charts.red";
  return new vscode.ThemeIcon("person", new vscode.ThemeColor(colorId));
}

function readJson(p: string): Record<string, unknown> | undefined {
  try {
    return JSON.parse(fs.readFileSync(p, "utf8")) as Record<string, unknown>;
  } catch {
    return undefined;
  }
}

export class PeopleProvider implements vscode.TreeDataProvider<PeopleItem> {
  private _onDidChange = new vscode.EventEmitter<PeopleItem | undefined | void>();
  readonly onDidChangeTreeData = this._onDidChange.event;

  refresh(): void {
    this._onDidChange.fire();
  }

  getTreeItem(e: PeopleItem): vscode.TreeItem {
    return e;
  }

  getChildren(element?: PeopleItem): PeopleItem[] {
    const root = peopleDir();
    if (!root || !fs.existsSync(root)) return [];

    if (!element) {
      return fs
        .readdirSync(root)
        .map((d) => path.join(root, d))
        .filter((p) => {
          try {
            return fs.statSync(p).isDirectory();
          } catch {
            return false;
          }
        })
        .sort()
        .map(
          (p) =>
            new PeopleItem(
              path.basename(p),
              p,
              "platform",
              vscode.TreeItemCollapsibleState.Expanded
            )
        );
    }

    if (element.kind === "platform") {
      return fs
        .readdirSync(element.fsPath)
        .map((d) => path.join(element.fsPath, d))
        .filter((p) => {
          try {
            return fs.statSync(p).isDirectory();
          } catch {
            return false;
          }
        })
        .sort()
        .map((p) => {
          const prof = readJson(path.join(p, "profile.json")) || {};
          const id = path.basename(p);
          const nick = (prof.primary_nick as string) || (prof.nick as string);
          return new PeopleItem(
            nick ? `${id} · ${nick}` : id,
            p,
            "person",
            vscode.TreeItemCollapsibleState.Collapsed,
            {
              nick,
              distance: prof.last_distance as string | undefined,
              risk: prof.authorship_risk as number | undefined,
              runs: prof.run_count as number | undefined,
            }
          );
        });
    }

    if (element.kind === "person") {
      const files = [
        "NOTES.md",
        "profile.json",
        "history.json",
        "identity.json",
        "authorship_integrity.json",
        "latest_analysis.json",
      ];
      return files
        .map((f) => path.join(element.fsPath, f))
        .filter((p) => fs.existsSync(p))
        .map(
          (p) =>
            new PeopleItem(
              path.basename(p),
              p,
              "file",
              vscode.TreeItemCollapsibleState.None
            )
        );
    }
    return [];
  }
}

export function notesPathForPerson(personDir: string): string {
  const notes = path.join(personDir, "NOTES.md");
  if (fs.existsSync(notes)) return notes;
  const prof = path.join(personDir, "profile.json");
  return fs.existsSync(prof) ? prof : personDir;
}
