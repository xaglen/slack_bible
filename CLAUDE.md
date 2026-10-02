# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A standalone cron-driven Slack bot that posts a daily Bible reading. It lives at
`scripts/bible/` inside the XADB tree but is **its own nested git repo** with its own
remote (`git@github.com:xaglen/slack_bible.git`, branch `main`). The parent XADB repo
sees this whole directory as a single untracked `??` line — always `git -C scripts/bible`
or `cd` here before running git. Commits, pushes, and history here are separate from XADB.

Publicly documented in `README.md` (the reading-plan rationale). `LICENSE` is MIT.

## Running / deployment

- No build, no test suite, no linter config of its own.
- Two independent scripts, each run once a day by cron (see the deployment's crontab, not
  the README's example line):
  - `slack.py` — the main plan, ~04:00
  - `mcheyne.py` — M'Cheyne readings, ~06:00, posts to a **hardcoded** `#xa-mcheyne`
  - Logs: `/var/log/xadb/cron-bible-slack.log` / `cron-bible-mcheyne.log` (via XADB's
    `scripts/cron_logging.py`); ERROR lines and crashes also go to XADB's Sentry, tagged
    `cron_script`. Cron still pipes stdout to `systemd-cat -t xadb-cron`, but journald
    here keeps only ~13h. Outside the XADB tree the import falls back to `basicConfig`.
- **Run with the XADB venv python, not system python3**: `slack_sdk` (and `feedparser`
  for `mcheyne.py`) are only installed in `/www/vhosts/xastanford.org/wsgi/xadb/venv`.
  The README's `/usr/bin/python3` line is stale for this host.
- Manual run: `cd scripts/bible && /www/vhosts/xastanford.org/wsgi/xadb/venv/bin/python slack.py`.
  Must run **from this directory** — `import settings` is a bare top-level import (relies
  on the script dir being on `sys.path`). All CSV opens use hardcoded absolute paths, so
  data loading works from anywhere, but the `settings` import does not.
- `settings.py` is gitignored and holds the **live Slack bot token**. Copy from
  `settings.example.py`, then **add `DEBUG = False`** — `settings.example.py` omits it but
  both scripts read `settings.DEBUG`, so a fresh copy `AttributeError`s on first run.
  `DEBUG=True` prints diagnostics and (in `mcheyne.py`) dumps the parsed feed.

## How the plan works (`slack.py`)

Everything keys off `weeks = (today - date(2012, 10, 22)).days // 7` and
`date.today().weekday()` (Mon=0):

- **Mon/Wed/Fri** → Old Testament, one line from `ot.csv`
- **Tue/Thu** → New Testament, one line from `nt.csv`
- **Every weekday** → one line from `wisdom.csv` (Psalms/Proverbs/Ecclesiastes/Song of
  Songs/Lamentations)
- **Sat/Sun** → `sys.exit()` early (Sat = catch-up day, Sun = church)

Progress indices:
- `ot_progress = 3*weeks + 15` then `+0/+1/+2` for Mon/Wed/Fri. The **`+15` is a
  deliberate historical offset**; the epoch date and this constant are load-bearing —
  changing either shifts every subscriber's position in the plan.
- `nt_progress = 2*weeks` then `+0/+1` for Tue/Thu.
- Wisdom: `(weeks*5 + weekday) % wisdom_entries`.
- All three index their list modulo its line count; a stray `IndexError` is caught and
  wraps to entry 0.

Output: BibleGateway NIV deep-links for the main + wisdom passage, plus an **estimated
read time** — `words_by_reference()` sums `WordCountKjv` from `chapters.csv` for the
referenced chapters, `reading_time()` divides by 450 wpm.

`words_by_reference()` parsing: `rsplit(" ", 1)` splits book from chapter spec so
multi-word books ("1 Thessalonians") work; `"1-5"` expands to a range; a book with no
number ("Philemon", "Jude") hits the `ValueError` branch → chapter 1.

## Data files

| File | Format | Role |
|---|---|---|
| `ot.csv`, `nt.csv`, `wisdom.csv` | one passage per line, e.g. `Genesis 1-5` | the ordered reading lists — **editing these changes the plan** |
| `books.csv` | `BookID,OsisID,BookName,TotalChapters,Volume` | book-name → id lookup |
| `chapters.csv` | `BookID,Chapter,TotalVerses,WordCountKjv,ReadingTimeInSecondsKjvScourby` | per-chapter word counts for read-time estimate |
| `chapters_original.csv` | backup of `chapters.csv` (untracked) | reference only |
| `bible.json` | 8 MB full-text dump | only consumed by the unfinished `chapters.json.py` scratch |

- `wisdom.csv` line 1 carries a **UTF-8 BOM**; every CSV is opened with `utf-8-sig`, which strips it.
- `books.csv` spells it **"Psalm"**, not "Psalms" — a book name that doesn't match is logged as an
  ERROR (Sentry) and counted as 0 words; the post still goes out.
- README's stated counts (126 OT / 55 NT / 248 wisdom readings) have drifted:
  `ot.csv` is now 127 entries (`Nehemiah 11-13` added), `wisdom.csv` 248.

## Other files — mostly not part of the daily job

- `chapters.py`, `chapters.json.py` — **dev scratch**. Not imported anywhere; they run
  code (and `chapters.py` calls Slack machinery / prints) at module load. Don't treat as
  library code.
- `index.php`, `test.php` — a legacy standalone PHP reimplementation of the same plan,
  reading CSVs from `/www/vhosts/xastanford.org/htdocs/prayer/bible/`. It renders a
  yesterday/today/tomorrow table and hardcodes the wisdom-book chapter ranges in PHP
  rather than reading `wisdom.csv`. If you change the plan logic, this is a parallel copy
  that will silently diverge.
- `pray.log.txt`, `votd.log.txt` — stray logs from sibling `scripts/` tools; gitignored (`*.log.txt`).

## `mcheyne.py`

Separate job. Fetches the edginet M'Cheyne RSS feed (`requests`, 20s timeout) and parses it with
`feedparser`; posts to `#xa-mcheyne`, or logs an ERROR and posts nothing if no readings match.
Odd calendar year → Carson "year one" + the feed's "Family" readings; even year → "year
two" + "Secret" readings.
