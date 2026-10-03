"""
Posts a daily Bible reading to Slack
"""

# from systemd.journal import JournaldLogHandler
import csv
import logging
import re
import sys
import urllib.parse
from datetime import date

import settings
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

try:
    # XADB deployment: persistent log in /var/log/xadb + Sentry alerts on errors
    sys.path.insert(0, "/www/vhosts/xastanford.org/wsgi/xadb/scripts")
    import cron_logging

    logger = cron_logging.setup("bible-slack", logging.DEBUG if settings.DEBUG else logging.INFO)
except ImportError:
    logging.basicConfig(level=logging.DEBUG if settings.DEBUG else logging.INFO)
    logger = logging.getLogger("bible-slack")


def words_by_reference(passage):
    logger.debug("Counting words for %r", passage)
    wordcount = 0
    passage_book = passage.rsplit(" ", 1)[0]
    passage_chapters = passage.split()[-1]
    if passage_chapters.isdigit():
        chapter = int(passage_chapters)
        passage_chapters = []
        passage_chapters.append(chapter)
    else:
        try:
            [opening_chapter, ending_chapter] = passage_chapters.split("-")
            passage_chapters = list(range(int(opening_chapter), int(ending_chapter) + 1))
        except ValueError:  # is not a digit, must be blank like Philemon or Jude
            passage_chapters = [1]  # so assign chapter 1

    with open(
        "/www/vhosts/xastanford.org/wsgi/xadb/scripts/bible/books.csv", newline="", encoding="utf-8-sig"
    ) as csvfile:
        data = list(csv.reader(csvfile, quoting=csv.QUOTE_NONE))
        books = {}
        book_chapters = []
        book_chapters.append(0)
        for row in data:
            # print(row)
            if row[0].isdigit():
                book_id = int(row[0])
                book_name = row[2]
                chapter_count = int(row[3])
                books[book_name] = book_id
                book_chapters.append(chapter_count)

    if passage_book not in books:
        # a typo'd book in a CSV shouldn't stop the post -- just under-count the read time
        logger.error("Unknown book %r in %r - not in books.csv, counting 0 words", passage_book, passage)
        return 0
    logger.debug("Chapters in %s: %s", passage_book, book_chapters[books[passage_book]])

    with open(
        "/www/vhosts/xastanford.org/wsgi/xadb/scripts/bible/chapters.csv", newline="", encoding="utf-8-sig"
    ) as csvfile:
        data = list(csv.reader(csvfile, quoting=csv.QUOTE_NONE))
        for row in data:
            if row[0].isdigit() and int(row[0]) == books[passage_book] and int(row[1]) in passage_chapters:
                wordcount += int(row[3])

    return wordcount


def reading_time(word_count=0):
    words_per_minute = 450  # 256 in original
    minutes, _seconds = divmod(60 * word_count / words_per_minute, 60)
    # multiply by 60 since I then divmod by 60. Since I don't really care about seconds anymore
    # I could just do minutes = word_count / words_per_minute and get the same result
    return f"about {max(1, round(minutes))} min (~{word_count:,} words)"


def pretty_reference(reference):
    """Display form of a reference: 'Ruth 1–4' (en dash in ranges), 'Psalm 85' for a single
    psalm. Display only — links keep the original text, which Bible Gateway parses."""
    reference = re.sub(r"(?<=\d)-(?=\d)", "–", reference.strip())
    return re.sub(r"^Psalms (\d+)$", r"Psalm \1", reference)


# reference = "Luke 1 -4; Proverbs 22"

# passages = reference.split(";")

# for passage in passages:
#    print(words_by_reference(passage))


client = WebClient(token=settings.SLACK_TOKEN)

start = date(2012, 10, 22)
today = date.today()
weeks = (today - start).days // 7


with open("/www/vhosts/xastanford.org/wsgi/xadb/scripts/bible/nt.csv", newline="", encoding="utf-8-sig") as csvfile:
    new_testament = list(csv.reader(csvfile, quoting=csv.QUOTE_NONE))
    new_testament_entries = sum(1 for row in new_testament)

with open("/www/vhosts/xastanford.org/wsgi/xadb/scripts/bible/ot.csv", newline="", encoding="utf-8-sig") as csvfile:
    old_testament = list(csv.reader(csvfile, quoting=csv.QUOTE_NONE))
    old_testament_entries = sum(1 for row in old_testament)

day_of_week = date.today().weekday()

logger.debug("Weeks since start: %d, day of week: %d", weeks, day_of_week)

ot_progress = (
    3 * weeks + 15
)  # through the OT thrice as fast as if reading once a week, adjusted by 15 for historical reasons
nt_progress = 2 * weeks  # NT is twice as fast

if day_of_week == 0:
    passage = old_testament[ot_progress % old_testament_entries]
elif day_of_week == 1:
    passage = new_testament[nt_progress % new_testament_entries]
elif day_of_week == 2:
    ot_progress = ot_progress + 1
    ot_index = ot_progress % old_testament_entries
    passage = old_testament[ot_index]
elif day_of_week == 3:
    #        print("Weeks: {weeks} NT entries: {nt}  result:{result}".format(weeks=weeks, nt=new_testament_entries, result=((2*weeks)%new_testament_entries)+1))
    # ERROR ALERT  = Thursday Oct 27 2022 weeks was 522 and the calculation resulted in 55 (54 should be the max for nt entries)
    # I need to redo this logic - maybe move the calculation outside the index and then modulus the result in the index?
    #        passage = new_testament[(2*weeks)%new_testament_entries+1]
    nt_progress = nt_progress + 1
    nt_index = nt_progress % new_testament_entries
    passage = new_testament[nt_index]
elif day_of_week == 4:
    ot_progress = ot_progress + 2
    ot_index = ot_progress % old_testament_entries
    passage = old_testament[ot_index]
else:
    logger.info("Weekend (day %d) - nothing to post", day_of_week)
    sys.exit()  # it's the weekend or there is a logic error


passage_string = f"Main: <http://www.biblegateway.com/passage/?search={urllib.parse.quote(passage[0])}&version=NIV|{pretty_reference(passage[0])}>"
# print(passage_string)

with open(
    "/www/vhosts/xastanford.org/wsgi/xadb/scripts/bible/wisdom.csv", newline="", encoding="utf-8-sig"
) as csvfile:
    wisdom = list(csv.reader(csvfile, quoting=csv.QUOTE_NONE))
    wisdom_entries = sum(1 for row in wisdom)

# wisdom_books = {'Psalms':150, 'Proverbs':31, 'Job':42, 'Song of Songs':8, 'Ecclesiastes':12, 'Lamentations':5}
# wisdom_chapters=sum(wisdom_books.values())

wisdom_progress = (weeks * 5 + day_of_week) % wisdom_entries
wisdom_passage = wisdom[wisdom_progress][0]
wisdom_passage_string = "Wisdom: <http://www.biblegateway.com/passage/?search={}&version=NIV|{}>".format(
    urllib.parse.quote(wisdom_passage), pretty_reference(wisdom_passage)
)

# print (passage_string)
# print(wisdom_passage_string)

passages = passage[0].split(";")
total_wordcount = 0

for section in passages:
    total_wordcount += words_by_reference(section.strip())
total_wordcount += words_by_reference(wisdom_passage.strip())


time_string = reading_time(total_wordcount)

slack_message = f"📖 *Today's Bible readings* · {time_string}\n• {passage_string}\n• {wisdom_passage_string}"
blocks = [
    {"type": "section", "text": {"type": "mrkdwn", "text": slack_message}},
    {
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": "<https://github.com/xaglen/slack_bible|Reading plan on GitHub>"}],
    },
]
# What a phone notification shows: the passages themselves.
notification = (
    f"📖 Today's Bible readings: {pretty_reference(passage[0])}, {pretty_reference(wisdom_passage)} · "
    f"{time_string.split(' (', 1)[0]}"
)

logger.info(
    "Main: %s (week %d, day %d) | Wisdom: %s (#%d of %d) | ~%d words",
    passage[0],
    weeks,
    day_of_week,
    wisdom_passage,
    wisdom_progress,
    wisdom_entries,
    total_wordcount,
)

try:
    resp = client.chat_postMessage(
        channel=settings.SLACK_CHANNEL,
        text=notification,
        blocks=blocks,
        unfurl_links=False,
    )
    logger.info("Posted to %s (ts %s)", settings.SLACK_CHANNEL, resp.get("ts"))
except SlackApiError as e:
    # You will get a SlackApiError if "ok" is False
    logger.error("Slack error posting Bible reading: %s", e.response.get("error"), exc_info=True)
    sys.exit(1)
except Exception:
    logger.exception("Error posting Bible reading")
    sys.exit(1)
