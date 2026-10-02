"""
Posts a daily Bible reading to Slack
"""

# from systemd.journal import JournaldLogHandler
import csv
import logging
import sys
import urllib.parse
from datetime import date

import settings
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

logger = logging.getLogger(__name__)
# journald_handler = JournaldLogHandler()
# journald_handler.setFormatter(logging.Formatter('[%(levelname)s] %message)s'))
# logger.addHandler(journald_handler)
logger.setLevel(logging.INFO)


def words_by_reference(passage):
    print(f"Parameter pasage: {passage}")
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
        csvfile.close()

    if passage_book not in books:
        # a typo'd book in a CSV shouldn't stop the post -- just under-count the read time
        print("Unknown book " + repr(passage_book) + " - not in books.csv, counting 0 words.")
        return 0
    print("Chapters in " + passage_book + ": " + str(book_chapters[books[passage_book]]) + ".")

    with open(
        "/www/vhosts/xastanford.org/wsgi/xadb/scripts/bible/chapters.csv", newline="", encoding="utf-8-sig"
    ) as csvfile:
        chapter_data = [i for i in range(1, 67)]
        for chapter in chapter_data:
            chapter = []

        data = list(csv.reader(csvfile, quoting=csv.QUOTE_NONE))
        for row in data:
            if row[0].isdigit() and int(row[0]) == books[passage_book] and int(row[1]) in passage_chapters:
                wordcount += int(row[3])
        csvfile.close()

    return wordcount


def reading_time(word_count=0):
    words_per_minute = 450  # 256 in original
    minutes, seconds = divmod(60 * word_count / words_per_minute, 60)
    # multiply by 60 since I then divmod by 60. Since I don't really care about seconds anymore
    # I could just do minutes = word_count / words_per_minute and get the same result
    return f"*Estimated read time: {round(minutes)} minutes (~{word_count} words)*"


# reference = "Luke 1 -4; Proverbs 22"

# passages = reference.split(";")

# for passage in passages:
#    print(words_by_reference(passage))

if settings.DEBUG:
    print("Starting script")

client = WebClient(token=settings.SLACK_TOKEN)

start = date(2012, 10, 22)
today = date.today()
weeks = (today - start).days // 7

if settings.DEBUG:
    print(f"Weeks {weeks}")

with open("/www/vhosts/xastanford.org/wsgi/xadb/scripts/bible/nt.csv", newline="", encoding="utf-8-sig") as csvfile:
    new_testament = list(csv.reader(csvfile, quoting=csv.QUOTE_NONE))
    new_testament_entries = sum(1 for row in new_testament)
    csvfile.close()

with open("/www/vhosts/xastanford.org/wsgi/xadb/scripts/bible/ot.csv", newline="", encoding="utf-8-sig") as csvfile:
    old_testament = list(csv.reader(csvfile, quoting=csv.QUOTE_NONE))
    old_testament_entries = sum(1 for row in old_testament)
    csvfile.close()

day_of_week = date.today().weekday()

if settings.DEBUG:
    print(f"Day of week: {day_of_week}")

ot_progress = (
    3 * weeks + 15
)  # through the OT thrice as fast as if reading once a week, adjusted by 15 for historical reasons
nt_progress = 2 * weeks  # NT is twice as fast

try:
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
        if settings.DEBUG:
            print("Exiting scipt")
        sys.exit()  # it's the weekend or there is a logic error
except IndexError:  # weird - just wrap around
    if day_of_week in [0, 2, 4]:
        passage = old_testament[0]
    else:
        passage = new_testament[0]

if settings.DEBUG:
    print(f"Passage: {passage}")

passage_string = f"Main reading: <http://www.biblegateway.com/passage/?search={urllib.parse.quote(passage[0])}&version=NIV|{passage[0]}>"
# print(passage_string)

with open(
    "/www/vhosts/xastanford.org/wsgi/xadb/scripts/bible/wisdom.csv", newline="", encoding="utf-8-sig"
) as csvfile:
    wisdom = list(csv.reader(csvfile, quoting=csv.QUOTE_NONE))
    wisdom_entries = sum(1 for row in wisdom)
    csvfile.close()

# wisdom_books = {'Psalms':150, 'Proverbs':31, 'Job':42, 'Song of Songs':8, 'Ecclesiastes':12, 'Lamentations':5}
# wisdom_chapters=sum(wisdom_books.values())

wisdom_progress = (weeks * 5 + day_of_week) % wisdom_entries
print("Wisdom progress {}".format(wisdom_progress))
wisdom_passage = wisdom[wisdom_progress][0]
print("Wisdom passage {}".format(wisdom_passage))
wisdom_passage_string = "Wisdom reading: <http://www.biblegateway.com/passage/?search={}&version=NIV|{}>".format(
    urllib.parse.quote(wisdom_passage), wisdom_passage
)

if day_of_week == 5 or day_of_week == 6:
    wisdom_passage_string = ""
else:
    wisdom_passage_string = "Wisdom reading: <http://www.biblegateway.com/passage/?search={}&version=NIV|{}>".format(
        urllib.parse.quote(wisdom_passage), wisdom_passage
    )

# print (passage_string)
# print(wisdom_passage_string)

passages = passage[0].split(";")
total_wordcount = 0

for section in passages:
    total_wordcount += words_by_reference(section.strip())
total_wordcount += words_by_reference(wisdom_passage.strip())


time_string = reading_time(total_wordcount)

slack_message = f"Today's Bible readings. {time_string}\n\nSee the schedule: <https://github.com/xaglen/slack_bible|GitHub>:\n* {passage_string}\n* {wisdom_passage_string}"

try:
    resp = client.chat_postMessage(
        channel=settings.SLACK_CHANNEL,
        text=slack_message,
        unfurl_links=False,
    )
except SlackApiError as e:
    # You will get a SlackApiError if "ok" is False
    message = "Slack error posting Bible reading"
    logger.info(message)
    logger.info(e)
    logger.info(e.response)
    print(message)
    print(e)
except TypeError as e:
    message = "TypeError posting Bible reading: {}".format(repr(e))
    logger.info(message)
    print(message + ": " + repr(e))
except:
    e = repr(sys.exc_info()[0])
    message = "Error posting Bible reading: {}".format(e)
    logger.info(message)
    print(message + ": " + e)
