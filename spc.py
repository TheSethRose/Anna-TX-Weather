#!/usr/bin/env python3
"""SPC (Storm Prediction Center) product fetcher.

Uses public SPC RSS feeds. No API key required.
"""
import html
import csv
import json
import math
import re
import xml.etree.ElementTree as ET
from io import StringIO
from urllib.request import Request, urlopen

HEADERS = {"User-Agent": "weather-scrape/1.0 (personal use)"}
LAT, LON = 33.349, -96.548

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


def distance_miles(lat1, lon1, lat2, lon2):
    radius = 3958.8
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def get_storm_reports(radius_miles=250):
    text = fetch_text("https://www.spc.noaa.gov/climo/reports/today.csv")
    reports = []
    report_type = None
    for row in csv.reader(StringIO(text)):
        if not row:
            continue
        if row[0] == "Time":
            if len(row) > 1 and row[1] == "F_Scale":
                report_type = "tornado"
            elif len(row) > 1 and row[1] == "Speed":
                report_type = "wind"
            elif len(row) > 1 and row[1] == "Size":
                report_type = "hail"
            continue
        if len(row) < 8 or not report_type:
            continue
        try:
            lat = float(row[5])
            lon = float(row[6])
        except ValueError:
            continue
        distance = distance_miles(LAT, LON, lat, lon)
        if distance > radius_miles:
            continue
        reports.append({
            "type": report_type,
            "time": row[0],
            "magnitude": row[1],
            "location": row[2],
            "county": row[3],
            "state": row[4],
            "lat": lat,
            "lon": lon,
            "distance_miles": round(distance),
            "comments": row[7],
        })
    reports.sort(key=lambda r: r["distance_miles"])
    return reports[:30]


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
    try:
        products["storm_reports"] = {
            "source": "SPC",
            "feed": "storm_reports",
            "items": get_storm_reports(),
        }
    except Exception as e:
        products["storm_reports"] = {
            "source": "SPC",
            "feed": "storm_reports",
            "items": [],
            "error": str(e),
        }
    return products


if __name__ == "__main__":
    print(json.dumps(get_spc_products(), indent=2))
