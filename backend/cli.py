"""Command-line tools.

python -m backend.cli scan <url>     axe-core scan of one page

WALKER_MODE=local scans in a local Chromium (free); otherwise a TinyFish Browser session is used.
"""
import argparse, asyncio, os, sys

from backend.axe_scan import AxeError, axe_scan
from backend.tinyfish_browser import close_page, open_page

IMPACT_ORDER = ["critical", "serious", "moderate", "minor"]


async def scan(url: str) -> int:
    print(f"scan {url}  (WALKER_MODE={os.getenv('WALKER_MODE', 'tinyfish')})")
    pw, browser, page, session_id = await open_page(url)
    try:
        violations = await axe_scan(page)
    except AxeError as e:
        print(f"error: {e}")
        return 1
    finally:
        await close_page(pw, browser, session_id)
    violations.sort(key=lambda v: IMPACT_ORDER.index(v["impact"]) if v["impact"] in IMPACT_ORDER else 9)
    for v in violations:
        print(f"{v['impact']:<9} {v['rule']:<24} {v['count']:>3} element(s)  {v['help']}")
    print(f"{len(violations)} rule(s) violated")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m backend.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    p_scan = sub.add_parser("scan", help="axe-core scan of one page")
    p_scan.add_argument("url")
    args = parser.parse_args()
    if args.command == "scan":
        return asyncio.run(scan(args.url))
    return 2


if __name__ == "__main__":
    sys.exit(main())
