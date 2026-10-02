"""
Posts a daily Bible reading to Slack
"""

# from systemd.journal import JournaldLogHandler
import csv
import logging
import sys
import urllib.parse
from datetime import date
from pprint import pformat

import feedparser
import requests
import settings
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

try:
    # XADB deployment: persistent log in /var/log/xadb + Sentry alerts on errors
    sys.path.insert(0, "/www/vhosts/xastanford.org/wsgi/xadb/scripts")
    import cron_logging

    logger = cron_logging.setup("bible-mcheyne", logging.DEBUG if settings.DEBUG else logging.INFO)
except ImportError:
    logging.basicConfig(level=logging.DEBUG if settings.DEBUG else logging.INFO)
    logger = logging.getLogger("bible-mcheyne")

client = WebClient(token=settings.SLACK_TOKEN)

today = date.today()

day_of_week = date.today().weekday()

feed_url = "http://www.edginet.org/mcheyne/rss_feed.php?type=rss_2.0&tz=-8&cal=classic&bible=niv"
# feedparser.parse(url) has no timeout and never raises, so fetch it ourselves
try:
    response = requests.get(feed_url, timeout=20)
    response.raise_for_status()
except requests.RequestException as e:
    logger.error("Could not fetch M'Cheyne feed: %r", e)
    sys.exit(1)
feed = feedparser.parse(response.content)
logger.debug("Feed: %s", pformat(feed))

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
    logger.error("No M'Cheyne readings found in feed; titles were %s", [e.get("title") for e in feed.entries])
    sys.exit(1)

logger.info("Feed had %d entries; posting %d readings", len(feed.entries), reading_count)

try:
    resp = client.chat_postMessage(channel="xa-mcheyne", text=readings)
    logger.info("Posted to #xa-mcheyne (ts %s)", resp.get("ts"))
except SlackApiError as e:
    # You will get a SlackApiError if "ok" is False
    logger.error("Slack error posting M'Cheyne reading: %s", e.response.get("error"), exc_info=True)
    sys.exit(1)
except Exception:
    logger.exception("Error posting M'Cheyne reading")
    sys.exit(1)
