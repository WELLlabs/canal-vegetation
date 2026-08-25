from __future__ import annotations


def score_reach(feats: dict, blocked_frac: float = 0.0) -> dict:
    """Notebook 07 Cell 10 scoring (also used by unit tests)."""
    blockage_types = []
    score = 0.0
    if feats["veg_frac"] > 0.5:
        score += 4.0
        blockage_types.append("heavy_vegetation")
    elif feats["veg_frac"] > 0.25:
        score += 2.5
        blockage_types.append("moderate_vegetation")
    elif feats["veg_frac"] > 0.1:
        score += 1.0
        blockage_types.append("light_vegetation")

    if feats["silt_like_frac"] > 0.35:
        score += 2.0
        blockage_types.append("silt_like_deposit")
    elif feats["silt_like_frac"] > 0.15:
        score += 1.0
        blockage_types.append("light_silt_like")

    if feats["gray_std"] > 55 and feats["water_frac"] < 0.1:
        score += 1.0
        blockage_types.append("structural_irregularity")
    if feats["water_frac"] > 0.4 and feats["veg_frac"] < 0.1:
        score -= 1.5

    if score >= 3.0 or blocked_frac >= 0.45:
        status = "blocked"
    elif score >= 1.5 or blocked_frac >= 0.15:
        status = "partial"
    else:
        status = "clear"

    return {
        "status": status,
        "blockage_score": float(score),
        "blockage_types": blockage_types,
    }
