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

# print(weeks)


def words_by_reference(passage):

    wordcount = 0
    passage_book = passage.split()[0]
    passage_chapters = passage.split()[1]
    if passage_chapters.isdigit():
        chapter = int(passage_chapters)
        passage_chapters = []
        passage_chapters.append(chapter)
    else:
        [opening_chapter, ending_chapter] = passage_chapters.split("-")
        passage_chapters = list(range(int(opening_chapter), int(ending_chapter) + 1))

    print("Assigned Book: " + passage_book)
    print("Assigned Chapters: " + str(passage_chapters))

    with open("/www/vhosts/xastanford.org/wsgi/xadb/scripts/bible/books.csv", newline="") as csvfile:
        data = list(csv.reader(csvfile, quoting=csv.QUOTE_NONE))
        books = {}
        book_chapters = []
        book_chapters.append(0)
        # print(book_chapters)
        for row in data:
            # print(row)
            if row[0].isdigit():
                book_id = int(row[0])
                # print("Book id: "+row[0])
                # print(len(book_chapters))
                book_name = row[2]
                chapter_count = int(row[3])
                books[book_name] = book_id
                book_chapters.append(chapter_count)
        csvfile.close()

    # print(books)

    print("Chapters in " + passage_book + ": " + str(books[passage_book]))

    with open("/www/vhosts/xastanford.org/wsgi/xadb/scripts/bible/chapters.csv", newline="") as csvfile:
        chapter_data = [i for i in range(1, 67)]
        for chapter in chapter_data:
            chapter = []

        data = list(csv.reader(csvfile, quoting=csv.QUOTE_NONE))
        for row in data:
            if row[0].isdigit() and int(row[0]) == books[passage_book] and int(row[1]) in passage_chapters:
                #                print(int(row[0]))
                #                print(int(row[1]))
                print("Adding word count for {} chapter {}: {}".format(passage_book, row[1], row[3]))
                wordcount += int(row[3])
        csvfile.close()

    #    print(book_chapters[books[passage_book]][1])
    print("Words: " + str(wordcount))
    return wordcount


reference = "Luke 1 -4; Proverbs 22"

passages = reference.split(";")

for passage in passages:
    print(words_by_reference(passage))
