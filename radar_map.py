#!/usr/bin/env python3
"""Render a city-level radar map from free public tiles."""
import math
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from rainviewer import LAT, LON

BASEMAP_URL = "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png"
IEM_NEXRAD_WMS = "https://mesonet.agron.iastate.edu/cgi-bin/wms/nexrad/n0q.cgi"
USER_AGENT = "weather-scrape/1.0 (personal use)"
WEB_MERCATOR_RADIUS = 6378137
TILE_SIZE = 256


def download_tile(url, path):
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=20) as resp:
        if resp.status != 200:
            raise RuntimeError(f"tile fetch failed {resp.status}: {url}")
        path.write_bytes(resp.read())


def lat_lon_to_mercator(lat, lon):
    x = WEB_MERCATOR_RADIUS * math.radians(lon)
    y = WEB_MERCATOR_RADIUS * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
    return x, y


def lon_lat_to_global_pixels(lon, lat, zoom):
    n = 2 ** zoom
    x = (lon + 180.0) / 360.0 * n * TILE_SIZE
    lat_rad = math.radians(lat)
    y = (1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2.0
    return x, y * n * TILE_SIZE


def city_bbox(lat=LAT, lon=LON, lon_span=1.72, lat_span=1.1, anna_x=0.74, anna_y=0.52):
    """Frame Anna to the right so west-to-east storms have room on the map."""
    min_lon = lon - lon_span * anna_x
    max_lon = min_lon + lon_span
    max_lat = lat + lat_span * anna_y
    min_lat = max_lat - lat_span
    return min_lon, min_lat, max_lon, max_lat


def xstack_layout(cols, rows):
    layout = []
    for row in range(rows):
        for col in range(cols):
            layout.append(f"{col * TILE_SIZE}_{row * TILE_SIZE}")
    return "|".join(layout)


def run_ffmpeg(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())


def stack_tiles(paths, output_path, cols, rows):
    cmd = ["ffmpeg", "-y"]
    for path in paths:
        cmd.extend(["-i", str(path)])
    cmd.extend([
        "-filter_complex",
        f"xstack=inputs={len(paths)}:layout={xstack_layout(cols, rows)}",
        "-frames:v",
        "1",
        str(output_path),
    ])
    run_ffmpeg(cmd)


def render_basemap(bbox, output_path, width, height, zoom=9):
    min_lon, min_lat, max_lon, max_lat = bbox
    min_px, max_py = lon_lat_to_global_pixels(min_lon, min_lat, zoom)
    max_px, min_py = lon_lat_to_global_pixels(max_lon, max_lat, zoom)

    tile_x_min = math.floor(min_px / TILE_SIZE)
    tile_x_max = math.floor((max_px - 1) / TILE_SIZE)
    tile_y_min = math.floor(min_py / TILE_SIZE)
    tile_y_max = math.floor((max_py - 1) / TILE_SIZE)
    cols = tile_x_max - tile_x_min + 1
    rows = tile_y_max - tile_y_min + 1

    with tempfile.TemporaryDirectory(prefix="weather-basemap-") as tmp:
        tmp_path = Path(tmp)
        tiles = []
        for y in range(tile_y_min, tile_y_max + 1):
            for x in range(tile_x_min, tile_x_max + 1):
                tile = tmp_path / f"base-{x}-{y}.png"
                download_tile(BASEMAP_URL.format(z=zoom, x=x, y=y), tile)
                tiles.append(tile)

        mosaic = tmp_path / "basemap-mosaic.png"
        stack_tiles(tiles, mosaic, cols, rows)

        crop_x = round(min_px - tile_x_min * TILE_SIZE)
        crop_y = round(min_py - tile_y_min * TILE_SIZE)
        crop_w = round(max_px - min_px)
        crop_h = round(max_py - min_py)
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(mosaic),
            "-vf",
            f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y},scale={width}:{height}",
            "-frames:v",
            "1",
            str(output_path),
        ]
        run_ffmpeg(cmd)


def render_iem_radar(bbox, output_path, width, height):
    min_lon, min_lat, max_lon, max_lat = bbox
    min_x, min_y = lat_lon_to_mercator(min_lat, min_lon)
    max_x, max_y = lat_lon_to_mercator(max_lat, max_lon)
    params = {
        "SERVICE": "WMS",
        "VERSION": "1.1.1",
        "REQUEST": "GetMap",
        "LAYERS": "nexrad-n0q-900913",
        "STYLES": "default",
        "SRS": "EPSG:3857",
        "BBOX": f"{min_x},{min_y},{max_x},{max_y}",
        "WIDTH": str(width),
        "HEIGHT": str(height),
        "FORMAT": "image/png",
        "TRANSPARENT": "TRUE",
    }
    download_tile(f"{IEM_NEXRAD_WMS}?{urlencode(params)}", output_path)


def overlay_radar(basemap_path, radar_path, output_path, width, height, anna_x=0.74, anna_y=0.52):
    marker_x = round(width * anna_x)
    marker_y = round(height * anna_y)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(basemap_path),
        "-i",
        str(radar_path),
        "-filter_complex",
        (
            "[1:v]format=rgba,colorchannelmixer=aa=0.66[radar];"
            "[0:v][radar]overlay=0:0,"
            f"drawbox=x={marker_x - 6}:y={marker_y - 6}:w=12:h=12:color=cyan@0.95:t=fill,"
            f"drawbox=x={marker_x - 24}:y={marker_y}:w=48:h=2:color=cyan@0.95:t=fill,"
            f"drawbox=x={marker_x}:y={marker_y - 24}:w=2:h=48:color=cyan@0.95:t=fill"
        ),
        "-frames:v",
        "1",
        str(output_path),
    ]
    run_ffmpeg(cmd)


def render_radar_map(_rainviewer_data, output_path, lat=LAT, lon=LON, width=1600, height=1000):
    """Render a labeled city-level NEXRAD map and return the output path string."""
    bbox = city_bbox(lat=lat, lon=lon)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="weather-radar-map-") as tmp:
        tmp_path = Path(tmp)
        basemap = tmp_path / "basemap.png"
        radar = tmp_path / "radar.png"
        render_basemap(bbox, basemap, width, height)
        render_iem_radar(bbox, radar, width, height)
        overlay_radar(basemap, radar, output_path, width, height)

    return str(output_path)
