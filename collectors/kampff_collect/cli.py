from __future__ import annotations

import argparse
import json
from pathlib import Path

from .pipeline import run_collect
from .registry import list_platforms, list_prebuilt, load_platform


def main() -> None:
    parser = argparse.ArgumentParser(description="Generic kampff collector")
    sub = parser.add_subparsers(dest="cmd")

    c = sub.add_parser("collect", help="targets.json → bundle.json")
    c.add_argument("--targets", required=True, type=Path)
    c.add_argument("--out", required=True, type=Path)
    c.add_argument("--auth-dir", type=Path, default=None)

    sub.add_parser("platforms", help="List all platform YAML ids")
    cat = sub.add_parser("catalog", help="List prebuilt platform packs")
    cat.add_argument("--tags", help="Filter by tag (workplace, sns, dev)")

    show = sub.add_parser("show", help="Show one platform YAML metadata")
    show.add_argument("platform")

    # --- connection setup (SNS + any platform with connection: block) ---
    conn = sub.add_parser("connect", help="SNS/platform connection setup")
    conn_sub = conn.add_subparsers(dest="connect_cmd")

    conn_sub.add_parser("list", help="List SNS platforms + connection modes")

    cs = conn_sub.add_parser("setup", help="Scaffold auth profile for a platform")
    cs.add_argument(
        "--platform",
        required=True,
        choices=["facebook", "x", "instagram", "linkedin", "reddit"],
        help="SNS platform id",
    )
    cs.add_argument("--ref", default=None, help="auth_ref name (default: {platform}_{mode})")
    cs.add_argument("--mode", default=None, help="connection mode id (see connect list)")
    cs.add_argument("--auth-dir", type=Path, default=None)

    st = conn_sub.add_parser("status", help="Check SNS connection readiness")
    st.add_argument("--platform", default=None, help="One platform id (default: all SNS)")
    st.add_argument("--auth-dir", type=Path, default=None)

    doc = conn_sub.add_parser("doctor", help="Alias of status + list")
    doc.add_argument("--auth-dir", type=Path, default=None)

    snip = conn_sub.add_parser("sample-targets", help="Print multi-SNS targets.json skeleton")
    snip.add_argument("--out", type=Path, default=None, help="Write JSON file instead of stdout")

    # backward-compatible auth alias
    auth = sub.add_parser("auth", help="Alias family for connect (login scaffold)")
    auth_sub = auth.add_subparsers(dest="auth_cmd")
    al = auth_sub.add_parser("login", help="Print headed browser login guidance (playwright refs)")
    al.add_argument("--ref", required=True)
    al.add_argument("--url", required=True)
    al.add_argument("--auth-dir", type=Path, default=None)
    auth_sub.add_parser("status", help="Same as connect status")

    args = parser.parse_args()
    if args.cmd == "platforms":
        for p in list_platforms():
            print(p)
        return
    if args.cmd == "catalog":
        tag = getattr(args, "tags", None)
        for entry in list_prebuilt():
            if tag and tag not in entry.get("tags", []):
                continue
            note = entry.get("note", "")
            suffix = f"  # {note}" if note else ""
            print(f"{entry['id']:20} {entry['label']:28} [{entry['transport']}]{suffix}")
        return
    if args.cmd == "show":
        cfg = load_platform(args.platform)
        print(f"id: {cfg.get('id')}  prebuilt: {cfg.get('prebuilt', False)}")
        print(f"transport: {cfg.get('transport')}  auth: {cfg.get('auth')}")
        print(f"capabilities: {', '.join(cfg.get('capabilities', []))}")
        conn_meta = cfg.get("connection")
        if conn_meta:
            print(f"connection.preferred_mode: {conn_meta.get('preferred_mode')}")
            modes = conn_meta.get("modes") or []
            print("connection.modes: " + ", ".join(m.get("id", "?") for m in modes))
        return
    if args.cmd == "collect":
        from .auth_setup import default_auth_dir

        auth_dir = args.auth_dir or default_auth_dir()
        stats = run_collect(args.targets, args.out, auth_dir)
        print(stats)
        return
    if args.cmd == "connect":
        _connect_main(args)
        return
    if args.cmd == "auth":
        _auth_main(args)
        return
    parser.print_help()


def _connect_main(args: argparse.Namespace) -> None:
    from . import auth_setup as az

    cmd = args.connect_cmd
    if cmd == "list":
        print(az.print_sns_list())
        return
    if cmd == "setup":
        result = az.setup_connection(
            args.platform,
            ref=args.ref,
            mode_id=args.mode,
            auth_dir=args.auth_dir,
        )
        print(az.format_setup_report(result))
        return
    if cmd == "status":
        rows = az.status_connection(args.platform, auth_dir=args.auth_dir)
        print(az.format_status_report(rows))
        return
    if cmd == "doctor":
        print(az.print_sns_list())
        print()
        rows = az.status_connection(None, auth_dir=args.auth_dir)
        print(az.format_status_report(rows))
        return
    if cmd == "sample-targets":
        data = az.sample_targets_sns()
        text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text, encoding="utf-8")
            print(f"wrote {args.out}")
        else:
            print(text, end="")
        return
    print("usage: kampff-collect connect {list|setup|status|doctor|sample-targets}")


def _auth_main(args: argparse.Namespace) -> None:
    from . import auth_setup as az

    cmd = args.auth_cmd
    if cmd == "status":
        print(az.format_status_report(az.status_connection(None, auth_dir=None)))
        return
    if cmd == "login":
        auth_dir = args.auth_dir or az.default_auth_dir()
        ref = args.ref
        url = args.url
        # scaffold playwright storage profile
        mode = {
            "id": "playwright_storage",
            "label": f"Playwright session for {ref}",
            "auth_type": "playwright_storage",
            "env": {},
            "steps": [
                f"Launch headed browser with user_data_dir under {auth_dir / ref}",
                f"Navigate to {url} and complete login/SSO yourself",
                f"Save storage_state to {auth_dir / ref / 'state.json'}",
                "Never type passwords into the agent chat",
                "Point targets.auth_ref at this ref",
            ],
        }
        path = az.write_profile(
            auth_dir,
            ref=ref,
            platform_id="internal_web",
            mode=mode,
            extra={"login_url": url, "storage_state": str(Path(ref) / "state.json")},
        )
        print(f"Playwright auth scaffold: {path}")
        print(f"  auth_ref : {ref}")
        print(f"  login_url: {url}")
        print(f"  expected : {auth_dir / ref / 'state.json'}")
        for i, step in enumerate(mode["steps"], 1):
            print(f"  {i}. {step}")
        return
    print("usage: kampff-collect auth {login|status}")


if __name__ == "__main__":
    main()
