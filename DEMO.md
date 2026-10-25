# Demo runs

Golden runs: one good, saved audit per demo target. Each one replays with its original timing at `/audit/{id}?replay=1`, with no network and no TinyFish credits, so it's the fallback if the venue Wi-Fi or a live run fails.

The audit IDs live in the demo laptop's local database (`data/`, not in git), so these links work on that laptop only. Start the backend and frontend first (see the README), then open the links.

| Target | Task | Audit ID | Result | Replay |
| --- | --- | --- | --- | --- |
| SkyRail (broken) | Find trains, select the first train, and enter the passenger name Asha Verma. | `7d658639` | Blocked at step 5 of 6, score 20 (live Agent stream + TinyFish walker) | http://localhost:3000/audit/7d658639?replay=1 |
| SkyRail (fixed) | Find trains, select the first train, and enter the passenger name Asha Verma. | `6b088df7` | Completed, score 100 (saved baseline + TinyFish walker) | http://localhost:3000/audit/6b088df7?replay=1 |
| CPENGRAMS pension grievance portal (pgportal.gov.in/pension) | Open the Contact Us page and find the department's contact email address. | `c8a32416` | Completed with barriers, score 0: Contact Us is reachable by keyboard, but none of the 14 stops on the way has visible focus; also an unnamed control, an unlabelled language dropdown, low contrast and no page language (live Agent stream + TinyFish walker) | http://localhost:3000/audit/c8a32416?replay=1 |
| Real site 2 | not run (IIIT Delhi was considered; its page has about 108 elements without visible focus, too slow to screenshot before the deadline; screenshots are now capped at 3 per kind of issue per page, so a future run takes about 5–8 minutes) | | | |

Reports (no replay): http://localhost:3000/audit/{id}
