# backend/axe_scan.py  (axe.min.js comes from the axe-core npm package, saved in backend/vendor)
from pathlib import Path

AXE_SOURCE = (Path(__file__).parent / "vendor" / "axe.min.js").read_text(encoding="utf-8")
TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]
MAX_NODES = 5                                   # nodes kept per rule; `count` keeps the full total


class AxeError(RuntimeError):
    pass


async def inject_axe(page) -> None:
    try:
        await page.evaluate(AXE_SOURCE)         # evaluate is not blocked by the site's CSP
    except Exception:
        try:
            await page.add_script_tag(content=AXE_SOURCE)
        except Exception as e:
            raise AxeError("axe could not run on this page") from e


async def axe_scan(page) -> list[dict]:
    """Runs axe-core with the WCAG 2.0/2.1 A and AA rules. Raises AxeError if axe can't run."""
    await inject_axe(page)
    try:
        result = await page.evaluate(
            "(tags) => axe.run(document, {runOnly: {type: 'tag', values: tags}})", TAGS)
    except Exception as e:
        raise AxeError("axe could not run on this page") from e
    return [{"rule": v["id"], "impact": v["impact"], "help": v["help"],
             "help_url": v["helpUrl"], "tags": v["tags"], "count": len(v["nodes"]),
             "nodes": [{"target": n["target"], "html": n["html"]} for n in v["nodes"][:MAX_NODES]]}
            for v in result["violations"]]
