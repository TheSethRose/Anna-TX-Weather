#!/usr/bin/env python3
"""SPC (Storm Prediction Center) product fetcher.

Uses public SPC RSS feeds. No API key required.
"""
import html
import json
import re
import xml.etree.ElementTree as ET
from urllib.request import Request, urlopen

HEADERS = {"User-Agent": "weather-scrape/1.0 (personal use)"}

FEEDS = {
    "mesoscale_discussions": "https://www.spc.noaa.gov/products/spcmdrss.xml",
    "watches": "https://www.spc.noaa.gov/products/spcwwrss.xml",
    "convective_outlooks": "https://www.spc.noaa.gov/products/spcacrss.xml",
    "pds_watches": "https://www.spc.noaa.gov/products/spcpdswwrss.xml",
}


def fetch_text(url):
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def clean_description(value):
    if not value:
        return ""
    text = html.unescape(value)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_feed(name, url):
    xml_text = fetch_text(url)
    root = ET.fromstring(xml_text)
    channel = root.find("channel")
    if channel is None:
        return {"updated": "", "items": []}

    items = []
    for item in channel.findall("item"):
        items.append({
            "title": (item.findtext("title") or "").strip(),
            "link": (item.findtext("link") or "").strip(),
            "published": (item.findtext("pubDate") or "").strip(),
            "description": clean_description(item.findtext("description") or ""),
        })

    return {
        "source": "SPC",
        "feed": name,
        "updated": (channel.findtext("lastBuildDate") or channel.findtext("pubDate") or "").strip(),
        "items": items,
    }


def get_spc_products():
    products = {}
    for name, url in FEEDS.items():
        try:
            products[name] = parse_feed(name, url)
        except Exception as e:
            products[name] = {
                "source": "SPC",
                "feed": name,
                "updated": "",
                "items": [],
                "error": str(e),
            }
    return products


if __name__ == "__main__":
    print(json.dumps(get_spc_products(), indent=2))
