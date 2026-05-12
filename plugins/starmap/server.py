"""Star map widget — computes a horizon view of tonight's sky.

The brightest ~70 named stars are baked into a small catalog below. For the
observer's lat/lon and the current UTC, we compute each star's altitude /
azimuth, then stereographic-project everything above the horizon onto a
unit disc with the zenith at the center.

The math is the standard textbook formulas:
  * Julian Date from civil UT
  * GMST → LST(λ)
  * HA = LST − RA
  * sin(alt) = sin(φ) sin(δ) + cos(φ) cos(δ) cos(HA)
  * az = atan2(−cos(δ) sin(HA), sin(δ) cos(φ) − cos(δ) sin(φ) cos(HA))

We also compute the Moon's position with a low-precision (Meeus) series —
enough accuracy for "where is it on the chart" but no eclipse-grade math.

A small set of constellation outlines is included (line segments between
catalog stars). Visibility filtering is done per-star: a constellation
shows up only if at least 2 of its endpoint stars are above the horizon.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Any


# ---------------------------------------------------------------------------
# Bright-star catalog. Format: (name, RA_hours, Dec_degrees, magnitude).
# Pulled from BSC5 / SIMBAD; selection biased toward stars that anchor
# recognizable constellations + the very brightest in both hemispheres.
# ---------------------------------------------------------------------------

# fmt: off
STARS: list[tuple[str, float, float, float]] = [
    # The 25 brightest stars in the sky.
    ("Sirius", 6.7525, -16.7161, -1.46),
    ("Canopus", 6.3992, -52.6957, -0.74),
    ("Arcturus", 14.2610, 19.1825, -0.05),
    ("Rigil Kentaurus", 14.6600, -60.8354, -0.27),  # α Cen
    ("Vega", 18.6156, 38.7837, 0.03),
    ("Capella", 5.2782, 45.9981, 0.08),
    ("Rigel", 5.2423, -8.2016, 0.13),
    ("Procyon", 7.6550, 5.2250, 0.34),
    ("Achernar", 1.6286, -57.2367, 0.46),
    ("Betelgeuse", 5.9195, 7.4071, 0.50),
    ("Hadar", 14.0637, -60.3730, 0.61),       # β Cen
    ("Altair", 19.8464, 8.8683, 0.77),
    ("Acrux", 12.4433, -63.0991, 0.77),       # α Cru
    ("Aldebaran", 4.5987, 16.5093, 0.85),
    ("Antares", 16.4901, -26.4320, 1.09),
    ("Spica", 13.4199, -11.1614, 1.04),
    ("Pollux", 7.7553, 28.0262, 1.14),
    ("Fomalhaut", 22.9608, -29.6222, 1.16),
    ("Deneb", 20.6905, 45.2803, 1.25),
    ("Mimosa", 12.7953, -59.6887, 1.25),      # β Cru
    ("Regulus", 10.1395, 11.9672, 1.35),
    ("Adhara", 6.9770, -28.9722, 1.50),
    ("Castor", 7.5765, 31.8883, 1.57),
    ("Gacrux", 12.5194, -57.1133, 1.63),      # γ Cru
    ("Shaula", 17.5601, -37.1038, 1.62),

    # Big Dipper / Ursa Major
    ("Dubhe", 11.0621, 61.7508, 1.79),
    ("Merak", 11.0307, 56.3824, 2.37),
    ("Phecda", 11.8972, 53.6948, 2.44),
    ("Megrez", 12.2571, 57.0326, 3.32),
    ("Alioth", 12.9004, 55.9598, 1.76),
    ("Mizar", 13.3987, 54.9254, 2.23),
    ("Alkaid", 13.7923, 49.3133, 1.85),

    # Orion (the rest of it)
    ("Bellatrix", 5.4188, 6.3497, 1.64),
    ("Mintaka", 5.5334, -0.2991, 2.23),
    ("Alnilam", 5.6035, -1.2019, 1.69),
    ("Alnitak", 5.6794, -1.9426, 1.74),
    ("Saiph", 5.7959, -9.6697, 2.07),

    # Cassiopeia
    ("Schedar", 0.6751, 56.5373, 2.24),
    ("Caph", 0.1530, 59.1497, 2.27),
    ("Gamma Cas", 0.9451, 60.7167, 2.47),
    ("Ruchbah", 1.4302, 60.2353, 2.66),
    ("Segin", 1.9064, 63.6700, 3.38),

    # Cygnus
    ("Sadr", 20.3705, 40.2566, 2.20),
    ("Gienah", 20.7702, 33.9703, 2.48),
    ("Delta Cyg", 19.7494, 45.1308, 2.87),
    ("Albireo", 19.5121, 27.9597, 3.08),

    # Lyra
    ("Sheliak", 18.8348, 33.3627, 3.45),
    ("Sulafat", 18.9821, 32.6896, 3.24),

    # Leo
    ("Algieba", 10.3327, 19.8415, 2.20),
    ("Denebola", 11.8177, 14.5720, 2.14),
    ("Zosma", 11.2351, 20.5237, 2.56),

    # Scorpius
    ("Graffias", 16.0906, -19.8054, 2.62),
    ("Dschubba", 16.0056, -22.6217, 2.32),
    ("Sargas", 17.6219, -42.9978, 1.86),
    ("Girtab", 17.7081, -39.0299, 1.62),

    # Carina (south)
    ("Avior", 8.3752, -59.5095, 1.86),
    ("Aspidiske", 9.2849, -59.2754, 2.21),
    ("Miaplacidus", 9.2200, -69.7172, 1.67),

    # Centaurus
    ("Menkent", 14.1115, -36.3700, 2.06),

    # Other useful nav stars
    ("Polaris", 2.5301, 89.2641, 1.98),
    ("Alphard", 9.4595, -8.6586, 1.99),
    ("Diphda", 0.7265, -17.9866, 2.04),
    ("Alpheratz", 0.1398, 29.0904, 2.06),

    # Crux outline filler
    ("Imai", 12.2522, -58.7489, 2.79),         # δ Cru
]
# fmt: on

# Constellation line segments — each entry is a list of star-name pairs that
# trace the constellation. Names match the catalog above.
CONSTELLATIONS: dict[str, list[tuple[str, str]]] = {
    "Crux": [
        ("Acrux", "Gacrux"),
        ("Mimosa", "Imai"),
    ],
    "Orion": [
        ("Betelgeuse", "Bellatrix"),
        ("Bellatrix", "Mintaka"),
        ("Mintaka", "Alnilam"),
        ("Alnilam", "Alnitak"),
        ("Alnitak", "Saiph"),
        ("Saiph", "Rigel"),
        ("Rigel", "Mintaka"),
        ("Betelgeuse", "Alnitak"),
    ],
    "Big Dipper": [
        ("Dubhe", "Merak"),
        ("Merak", "Phecda"),
        ("Phecda", "Megrez"),
        ("Megrez", "Alioth"),
        ("Alioth", "Mizar"),
        ("Mizar", "Alkaid"),
        ("Megrez", "Dubhe"),
    ],
    "Cassiopeia": [
        ("Caph", "Schedar"),
        ("Schedar", "Gamma Cas"),
        ("Gamma Cas", "Ruchbah"),
        ("Ruchbah", "Segin"),
    ],
    "Cygnus": [
        ("Deneb", "Sadr"),
        ("Sadr", "Gienah"),
        ("Sadr", "Delta Cyg"),
        ("Sadr", "Albireo"),
    ],
    "Leo": [
        ("Regulus", "Algieba"),
        ("Algieba", "Zosma"),
        ("Zosma", "Denebola"),
        ("Denebola", "Regulus"),
    ],
}


# ---------------------------------------------------------------------------
# Astronomy helpers
# ---------------------------------------------------------------------------


def _julian_date(ut: datetime) -> float:
    y, m = ut.year, ut.month
    d = ut.day + (ut.hour + ut.minute / 60 + ut.second / 3600) / 24
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    return (
        math.floor(365.25 * (y + 4716))
        + math.floor(30.6001 * (m + 1))
        + d
        + b
        - 1524.5
    )


def _gmst_deg(jd: float) -> float:
    t = (jd - 2451545.0) / 36525
    gmst = (
        280.46061837
        + 360.98564736629 * (jd - 2451545.0)
        + t * t * (0.000387933 - t / 38710000)
    )
    return gmst % 360


def _alt_az(
    ra_h: float, dec_d: float, lat_d: float, lst_h: float
) -> tuple[float, float]:
    """Return (alt_deg, az_deg). az is measured from north going east."""
    ha = math.radians((lst_h - ra_h) * 15)
    dec = math.radians(dec_d)
    lat = math.radians(lat_d)
    sin_alt = math.sin(lat) * math.sin(dec) + math.cos(lat) * math.cos(dec) * math.cos(ha)
    sin_alt = max(-1.0, min(1.0, sin_alt))
    alt = math.asin(sin_alt)
    cos_alt = math.cos(alt) or 1e-9
    sin_az = -math.cos(dec) * math.sin(ha) / cos_alt
    cos_az = (math.sin(dec) - math.sin(alt) * math.sin(lat)) / (cos_alt * math.cos(lat))
    az = math.degrees(math.atan2(sin_az, cos_az)) % 360
    return math.degrees(alt), az


def _moon_radec(jd: float) -> tuple[float, float]:
    """Low-precision Moon position (Meeus ch. 47, truncated). Returns
    (RA_hours, Dec_degrees). Good enough for charting (~0.5°)."""
    t = (jd - 2451545.0) / 36525
    # Mean longitude
    l = 218.3164477 + 481267.88123421 * t
    # Mean elongation, mean anomaly, etc.
    d = 297.8501921 + 445267.1114034 * t
    m = 357.5291092 + 35999.0502909 * t
    mp = 134.9633964 + 477198.8675055 * t
    f = 93.2720950 + 483202.0175233 * t

    lr = math.radians(l)
    dr = math.radians(d)
    mr = math.radians(m)
    mpr = math.radians(mp)
    fr = math.radians(f)

    lon = l
    lon += 6.289 * math.sin(mpr)
    lon += -1.274 * math.sin(mpr - 2 * dr)
    lon += 0.658 * math.sin(2 * dr)
    lon += -0.186 * math.sin(mr)
    lon += -0.059 * math.sin(2 * mpr - 2 * dr)
    lon += -0.057 * math.sin(mpr - 2 * dr + mr)
    lon += 0.053 * math.sin(mpr + 2 * dr)

    lat = 5.128 * math.sin(fr)
    lat += 0.281 * math.sin(mpr + fr)
    lat += -0.278 * math.sin(mpr - fr)

    lon_rad = math.radians(lon % 360)
    lat_rad = math.radians(lat)
    # Ecliptic to equatorial
    eps = math.radians(23.4392911 - 0.0130042 * t)
    sin_ra = math.sin(lon_rad) * math.cos(eps) - math.tan(lat_rad) * math.sin(eps)
    cos_ra = math.cos(lon_rad)
    ra = math.atan2(sin_ra, cos_ra)
    dec = math.asin(
        math.sin(lat_rad) * math.cos(eps)
        + math.cos(lat_rad) * math.sin(eps) * math.sin(lon_rad)
    )
    return (math.degrees(ra) / 15) % 24, math.degrees(dec)


def _project(alt_d: float, az_d: float) -> tuple[float, float]:
    """Linear horizon projection: zenith (0,0), horizon at r=1.
    Azimuth measured N-clockwise: az=0 → +y (top of chart)."""
    r = (90 - alt_d) / 90
    az = math.radians(az_d)
    x = r * math.sin(az)
    y = -r * math.cos(az)
    return x, y


# ---------------------------------------------------------------------------
# Plugin entry point
# ---------------------------------------------------------------------------


def fetch(
    options: dict[str, Any], settings: dict[str, Any], *, ctx: dict[str, Any]
) -> dict[str, Any]:
    try:
        lat = float(options.get("lat") or -37.6494)
        lon = float(options.get("lon") or 145.1004)
    except (TypeError, ValueError):
        return {"error": "Invalid lat/lon."}

    label = (options.get("label") or "").strip()
    show_constellations = options.get("show_constellations", True) is not False
    show_names = options.get("show_names", True) is not False

    ut = datetime.now(UTC)
    jd = _julian_date(ut)
    gmst_h = _gmst_deg(jd) / 15
    lst_h = (gmst_h + lon / 15) % 24

    stars_proj: dict[str, dict[str, Any]] = {}
    visible: list[dict[str, Any]] = []
    for name, ra, dec, mag in STARS:
        alt, az = _alt_az(ra, dec, lat, lst_h)
        if alt < 0:
            stars_proj[name] = {"visible": False}
            continue
        x, y = _project(alt, az)
        rec = {"name": name, "x": x, "y": y, "mag": mag, "visible": True}
        stars_proj[name] = rec
        visible.append(rec)

    lines: list[dict[str, Any]] = []
    if show_constellations:
        for cname, segments in CONSTELLATIONS.items():
            for a, b in segments:
                ap = stars_proj.get(a)
                bp = stars_proj.get(b)
                if not ap or not bp:
                    continue
                if not ap.get("visible") or not bp.get("visible"):
                    continue
                lines.append(
                    {"x1": ap["x"], "y1": ap["y"], "x2": bp["x"], "y2": bp["y"]}
                )

    # Moon
    moon = None
    mra, mdec = _moon_radec(jd)
    malt, maz = _alt_az(mra, mdec, lat, lst_h)
    if malt > -2:  # Show "just risen / just set" too — useful at twilight
        mx, my = _project(max(malt, 0), maz)
        moon = {"x": mx, "y": my, "alt": malt}

    # Local civil time string for the header (we have UT; convert to roughly
    # the user's longitude offset for the chart subtitle. Not a true tz
    # conversion — purely a "what does the sky look like ~now there" hint).
    local_dt = ut + timedelta(hours=lon / 15)
    return {
        "label": label,
        "lat": lat,
        "lon": lon,
        "time_iso": ut.isoformat(),
        "time_local": local_dt.strftime("%H:%M"),
        "stars": visible,
        "lines": lines,
        "moon": moon,
        "show_names": show_names,
    }
