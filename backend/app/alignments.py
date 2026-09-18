"""Bundled canal alignments. The user picks a canal; the app already ships the
verified centreline/reaches, so no shapefile upload is required.

Optional per-canal keys:
  width  — corridor width in metres, used when the shapefile has no width field
           (a raw centreline). Ignored when the shapefile carries its own widths.
  ctype  — canal type recorded on each reach when the shapefile has none.
"""
from __future__ import annotations
import functools
from . import config

# Registry of shipped canals. key -> (label, region, folder, shapefile stem)
CANALS = {
    "tlbc_d95": {
        "label": "TLBC D95 - Attanur",
        "region": "Karnataka, India",
        "folder": "tlbc",
        "stem": "tlbc_segments",
        "reach_field": "id",
    },
    "nrbc": {
        "label": "NRBC network",
        "region": "Karnataka, India",
        "folder": "nrbc",
        "stem": "nrbc_segments",
        "reach_field": "id",
    },
    "Canal_Portion_Hattikuni": {
        "label": "Canal Portion Hattikuni",
        "region": "Karnataka, India",
        "folder": "Canal_Portion_Hattikuni",
        "stem": "Canal_Portion_Hattikuni",
        "reach_field": "id",
        # Raw centreline (no width/chainage in the shapefile): cut into reaches
        # on load, using these defaults.
        "width": 5.0,
        "ctype": "main",
    },
}


def shapefile_path(key: str):
    c = CANALS[key]
    return config.ALIGN_DIR / c["folder"] / f"{c['stem']}.shp"


@functools.lru_cache(maxsize=8)
def _summ(key: str) -> dict:
    import math
    import shapefile  # pyshp
    sf = shapefile.Reader(str(shapefile_path(key)))
    n = len(sf)
    bbox = list(sf.bbox)  # [minx, miny, maxx, maxy] in the shapefile CRS
    fields = [f[0] for f in sf.fields[1:]]
    # A raw centreline (no chainage field) is cut into reaches on load, so report
    # the resulting reach count rather than the raw feature count.
    if "chainage" not in {f.lower() for f in fields}:
        reach_m = float(getattr(config, "REACH_LENGTH_M", 50))
        total = 0.0
        for sh in sf.shapes():
            p = sh.points
            total += sum(math.dist(p[i], p[i + 1]) for i in range(len(p) - 1))
        n = max(n, int(math.ceil(total / reach_m))) if total else n
    sf.close()
    return {"reaches": n, "bbox": bbox, "fields": fields}


def list_canals() -> list[dict]:
    out = []
    for key, c in CANALS.items():
        item = {"key": key, "label": c["label"], "region": c["region"]}
        try:
            item.update(_summ(key))
        except Exception as e:  # shapefile missing / unreadable
            item.update({"reaches": None, "bbox": None, "error": str(e)})
        out.append(item)
    return out
