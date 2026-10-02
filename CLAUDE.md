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
  - Both are piped through `systemd-cat -t xadb-cron`; read logs with
    `journalctl -t xadb-cron` (shared tag with every other XADB cron script — grep for
    the script name or its `print()` output).
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

- `wisdom.csv` line 1 carries a **UTF-8 BOM**. `slack.py` reads `wisdom.csv` with a plain
  `csv.reader` (no `utf-8-sig`), so the first entry string is `"﻿Psalm 1"` — fine for
  the URL but be aware when comparing.
- README's stated counts (126 OT / 55 NT / 248 wisdom readings) have drifted:
  `ot.csv` is now 127 lines (`Nehemiah 11-13` added), `wisdom.csv` is 247.

## Other files — mostly not part of the daily job

- `chapters.py`, `chapters.json.py` — **dev scratch**. Not imported anywhere; they run
  code (and `chapters.py` calls Slack machinery / prints) at module load. Don't treat as
  library code.
- `index.php`, `test.php` — a legacy standalone PHP reimplementation of the same plan,
  reading CSVs from `/www/vhosts/xastanford.org/htdocs/prayer/bible/`. It renders a
  yesterday/today/tomorrow table and hardcodes the wisdom-book chapter ranges in PHP
  rather than reading `wisdom.csv`. If you change the plan logic, this is a parallel copy
  that will silently diverge.
- `pray.log.txt`, `votd.log.txt` — stray logs from sibling `scripts/` tools; not this
  repo's. `*.log` is gitignored but `.log.txt` is not, so they show as untracked.

## `mcheyne.py`

Separate job. Parses the edginet M'Cheyne RSS feed (`feedparser`), posts to `#xa-mcheyne`.
Odd calendar year → Carson "year one" + the feed's "Family" readings; even year → "year
two" + "Secret" readings.

## Working-tree state

The uncommitted diff on `slack.py` / `chapters.py` / `mcheyne.py` / `settings.example.py`
is almost entirely **ruff reformatting** (import sorting, quote style, line wrapping)
applied by the parent XADB repo's pre-commit hook when these files were staged there.
`slack.py` also has one real change: `print("Chapters in …")` now indexes
`book_chapters[...]` instead of printing the raw id. Review before committing into this
nested repo — its history is otherwise hand-written, unformatted style.
