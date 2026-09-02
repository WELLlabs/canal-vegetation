"""Bundled canal alignments. The user picks a canal; the app already ships the
verified centreline/reaches, so no shapefile upload is required."""
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
}


def shapefile_path(key: str):
    c = CANALS[key]
    return config.ALIGN_DIR / c["folder"] / f"{c['stem']}.shp"


@functools.lru_cache(maxsize=8)
def _summ(key: str) -> dict:
    import shapefile  # pyshp
    sf = shapefile.Reader(str(shapefile_path(key)))
    n = len(sf)
    bbox = list(sf.bbox)  # [minx, miny, maxx, maxy] in the shapefile CRS
    fields = [f[0] for f in sf.fields[1:]]
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
