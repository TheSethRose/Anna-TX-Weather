#!/usr/bin/env python3
"""Nearby town reference points for storm timing around Anna, TX."""
import math

ANNA = {"name": "Anna", "lat": 33.349, "lon": -96.548}

# Generated from the 2024 U.S. Census Gazetteer place file, sorted by distance
# from Anna. Kept static because town coordinates do not need a live API call.
PLACE_POINTS = [
    {"name": "Melissa", "lat": 33.288521, "lon": -96.557632},
    {"name": "Westminster", "lat": 33.364849, "lon": -96.459348},
    {"name": "Van Alstyne", "lat": 33.421688, "lon": -96.583202},
    {"name": "Weston", "lat": 33.330038, "lon": -96.665863},
    {"name": "Blue Ridge", "lat": 33.298359, "lon": -96.398800},
    {"name": "New Hope", "lat": 33.211876, "lon": -96.558682},
    {"name": "Princeton", "lat": 33.184474, "lon": -96.509393},
    {"name": "Howe", "lat": 33.507477, "lon": -96.615543},
    {"name": "McKinney", "lat": 33.201125, "lon": -96.664161},
    {"name": "Tom Bean", "lat": 33.520296, "lon": -96.484218},
    {"name": "Lowry Crossing", "lat": 33.169279, "lon": -96.544985},
    {"name": "Trenton", "lat": 33.426257, "lon": -96.344594},
    {"name": "Whitewright", "lat": 33.511159, "lon": -96.394906},
    {"name": "Celina", "lat": 33.322960, "lon": -96.798821},
    {"name": "Fairview", "lat": 33.140513, "lon": -96.613031},
    {"name": "Dorchester", "lat": 33.531277, "lon": -96.689098},
    {"name": "Gunter", "lat": 33.416309, "lon": -96.820799},
    {"name": "Farmersville", "lat": 33.160912, "lon": -96.360657},
    {"name": "Prosper", "lat": 33.241332, "lon": -96.812388},
    {"name": "Lucas", "lat": 33.101031, "lon": -96.581182},
    {"name": "Leonard", "lat": 33.383176, "lon": -96.246466},
    {"name": "Allen", "lat": 33.109736, "lon": -96.673032},
    {"name": "Seis Lagos", "lat": 33.071461, "lon": -96.566791},
    {"name": "Sherman", "lat": 33.628596, "lon": -96.626722},
    {"name": "Bells", "lat": 33.616488, "lon": -96.412736},
    {"name": "Savoy", "lat": 33.599840, "lon": -96.366028},
    {"name": "Parker", "lat": 33.060839, "lon": -96.625192},
    {"name": "Frisco", "lat": 33.155427, "lon": -96.822596},
    {"name": "Celeste", "lat": 33.289675, "lon": -96.194470},
    {"name": "St. Paul", "lat": 33.047486, "lon": -96.553391},
    {"name": "Southmayd", "lat": 33.623061, "lon": -96.708206},
    {"name": "Wylie", "lat": 33.029144, "lon": -96.527041},
    {"name": "Ector", "lat": 33.579284, "lon": -96.273115},
    {"name": "Savannah", "lat": 33.225738, "lon": -96.908125},
    {"name": "Tioga", "lat": 33.472108, "lon": -96.915704},
    {"name": "Bailey", "lat": 33.433622, "lon": -96.165093},
    {"name": "Murphy", "lat": 33.016418, "lon": -96.608233},
    {"name": "Lavon", "lat": 33.023862, "lon": -96.433029},
    {"name": "Plano", "lat": 33.050769, "lon": -96.747944},
    {"name": "Pilot Point", "lat": 33.398264, "lon": -96.955528},
    {"name": "Josephine", "lat": 33.063107, "lon": -96.316643},
    {"name": "Knollwood", "lat": 33.689274, "lon": -96.618475},
    {"name": "Nevada", "lat": 33.035329, "lon": -96.370639},
    {"name": "Paloma Creek", "lat": 33.225336, "lon": -96.936997},
    {"name": "Little Elm", "lat": 33.192497, "lon": -96.919975},
    {"name": "Paloma Creek South", "lat": 33.210020, "lon": -96.932686},
    {"name": "Providence Village", "lat": 33.237843, "lon": -96.956797},
    {"name": "Aubrey", "lat": 33.308550, "lon": -96.979088},
    {"name": "Collinsville", "lat": 33.559363, "lon": -96.907163},
    {"name": "Hackberry", "lat": 33.149748, "lon": -96.918313},
]


def distance_miles(lat1, lon1, lat2, lon2):
    radius_miles = 3958.7613
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius_miles * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def bearing_degrees(lat1, lon1, lat2, lon2):
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_lambda = math.radians(lon2 - lon1)
    y = math.sin(d_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(d_lambda)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def compass_direction(degrees):
    directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return directions[int((degrees + 11.25) // 22.5) % 16]


def projected_miles_from_anna(place, motion_degrees):
    """Positive means the town is upstream of Anna for the given storm motion."""
    bearing = math.radians(place["bearing_from_anna_degrees"])
    motion = math.radians(motion_degrees)
    return -place["distance_miles"] * math.cos(bearing - motion)


def nearby_places(limit=50, storm_motion_degrees=90, storm_speed_mph=None):
    places = []
    for point in PLACE_POINTS:
        distance = distance_miles(ANNA["lat"], ANNA["lon"], point["lat"], point["lon"])
        bearing = bearing_degrees(ANNA["lat"], ANNA["lon"], point["lat"], point["lon"])
        place = {
            **point,
            "distance_miles": round(distance, 1),
            "bearing_from_anna_degrees": round(bearing),
            "direction_from_anna": compass_direction(bearing),
        }
        upstream = projected_miles_from_anna(place, storm_motion_degrees)
        place["storm_motion_reference"] = {
            "motion_degrees": storm_motion_degrees,
            "upstream_miles": round(upstream, 1),
        }
        if storm_speed_mph:
            place["storm_motion_reference"]["eta_minutes_to_anna"] = round((upstream / storm_speed_mph) * 60) if upstream > 0 else None
        places.append(place)
    return sorted(places, key=lambda p: p["distance_miles"])[:limit]
