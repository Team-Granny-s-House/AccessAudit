# Demo runs

Golden runs: one good, saved audit per demo target. Each one replays with its original timing at `/audit/{id}?replay=1`, with no network and no TinyFish credits, so it's the fallback if the venue Wi-Fi or a live run fails.

The audit IDs live in the demo laptop's local database (`data/`, not in git), so these links work on that laptop only. Start the backend and frontend first (see the README), then open the links.

| Target | Task | Audit ID | Result | Replay |
| --- | --- | --- | --- | --- |
| SkyRail (broken) | Find trains, select the first train, and enter the passenger name Asha Verma. | `7d658639` | Blocked at step 5 of 6, score 20 (live Agent stream + TinyFish walker) | http://localhost:3000/audit/7d658639?replay=1 |
| SkyRail (fixed) | Find trains, select the first train, and enter the passenger name Asha Verma. | to be recorded | | |
| Real site 1 | to be chosen | to be recorded | | |
| Real site 2 | to be chosen | to be recorded | | |

Reports (no replay): http://localhost:3000/audit/{id}
