"""Capture demo reel slides → docs/demo-reel.gif for README embed."""
from pathlib import Path
import subprocess
import sys

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "docs" / "demo-kampff-walkthrough.html").resolve()
OUT_DIR = ROOT / "docs" / "_demo_frames"
GIF = ROOT / "docs" / "demo-reel.gif"
MP4 = ROOT / "docs" / "demo-reel.mp4"

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for p in OUT_DIR.glob("*.png"):
        p.unlink()

    url = HTML.as_uri()
    frames = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1120, "height": 630}, device_scale_factor=1)
        page.goto(url, wait_until="networkidle")
        # stop autoplay
        page.evaluate(
            """() => {
              const b = document.getElementById('btnPlay');
              if (b && b.textContent.trim() === 'Pause') b.click();
            }"""
        )
        n = page.evaluate("() => document.querySelectorAll('.slide').length")
        # ensure start at 0
        page.keyboard.press("r")
        page.wait_for_timeout(700)
        for i in range(n):
            # let stagger animations settle
            page.wait_for_timeout(900)
            path = OUT_DIR / f"frame_{i:02d}.png"
            # capture the stage element only
            stage = page.locator("#stage")
            stage.screenshot(path=str(path))
            frames.append(path)
            if i < n - 1:
                page.keyboard.press("ArrowRight")
                page.wait_for_timeout(200)
        browser.close()

    if not frames:
        print("no frames", file=sys.stderr)
        sys.exit(1)

    # GIF via ffmpeg — ~0.9s per slide, loop
    # scale for GitHub README width
    list_file = OUT_DIR / "frames.txt"
    # use concat demuxer with duration
    lines = []
    for f in frames:
        lines.append(f"file '{f.resolve().as_posix()}'")
        lines.append("duration 1.1")
    lines.append(f"file '{frames[-1].resolve().as_posix()}'")  # last frame needs restate
    list_file.write_text("\n".join(lines), encoding="utf-8")

    # palette GIF
    palette = OUT_DIR / "palette.png"
    subprocess.check_call([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-vf", "fps=10,scale=960:-1:flags=lanczos,palettegen=stats_mode=diff",
        str(palette),
    ])
    subprocess.check_call([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-i", str(palette),
        "-lavfi", "fps=10,scale=960:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5",
        "-loop", "0",
        str(GIF),
    ])
    # also mp4 for optional later
    subprocess.check_call([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-vf", "fps=10,scale=1280:-2:flags=lanczos",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(MP4),
    ])
    print("wrote", GIF, GIF.stat().st_size)
    print("wrote", MP4, MP4.stat().st_size)
    print("frames", len(frames))

if __name__ == "__main__":
    main()
