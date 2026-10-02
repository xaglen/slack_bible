"""
Posts a daily Bible reading to Slack
"""

# from systemd.journal import JournaldLogHandler
import csv
import logging
import sys
import urllib.parse
from datetime import date
from pprint import pprint

import feedparser
import requests
import settings
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

logger = logging.getLogger(__name__)
# journald_handler = JournaldLogHandler()
# journald_handler.setFormatter(logging.Formatter('[%(levelname)s] %message)s'))
# logger.addHandler(journald_handler)
logger.setLevel(logging.INFO)

client = WebClient(token=settings.SLACK_TOKEN)

today = date.today()

day_of_week = date.today().weekday()

feed_url = "http://www.edginet.org/mcheyne/rss_feed.php?type=rss_2.0&tz=-8&cal=classic&bible=niv"
# feedparser.parse(url) has no timeout and never raises, so fetch it ourselves
try:
    response = requests.get(feed_url, timeout=20)
    response.raise_for_status()
except requests.RequestException as e:
    print(f"Could not fetch M'Cheyne feed: {e!r}")
    sys.exit(1)
feed = feedparser.parse(response.content)
if settings.DEBUG:
    pprint(feed)

if today.year % 2 == 1:
    readings = "Today's <http://www.edginet.org/mcheyne/info.html|M'Cheyne> readings (Carson year one):\n"
else:
    readings = "Today's <http://www.edginet.org/mcheyne/info.html|M'Cheyne> readings (Carson year two):\n"

reading_count = 0
for entry in feed.entries:
    if (today.year % 2 == 0 and "Secret" in entry.title) or (today.year % 2 == 1 and "Family" in entry.title):
        title = entry.title.rsplit(" ", 1)[0]
        readings += "* <{link}|{title}>\n".format(title=title, link=entry.links[0].href)
        reading_count += 1

if reading_count == 0:
    # feed outage or a changed title format -- don't post an empty list
    print(f"No M'Cheyne readings found in feed; titles were {[e.get('title') for e in feed.entries]}")
    sys.exit(1)

# print() rather than logging: cron pipes stdout to systemd-cat, and no log handler is configured
try:
    resp = client.chat_postMessage(channel="xa-mcheyne", text=readings)
except SlackApiError as e:
    # You will get a SlackApiError if "ok" is False
    print("Slack error posting M'Cheyne reading")
    print(e)
    print(e.response)
    sys.exit(1)
except Exception as e:
    print(f"Error posting M'Cheyne reading: {e!r}")
    sys.exit(1)
