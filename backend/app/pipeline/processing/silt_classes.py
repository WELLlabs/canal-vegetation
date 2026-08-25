from __future__ import annotations


def silt_status_from_counts(n_g: int, n_o: int, n_r_px: int, canal_px: int) -> str:
    """Notebook 08 Cell 4 dominant category, mapped to low/medium/high for the API."""
    if n_r_px > canal_px * 0.2:
        notebook_status = "heavy"
    elif n_o > canal_px * 0.2:
        notebook_status = "moderate"
    elif (n_o + n_r_px) > canal_px * 0.05:
        notebook_status = "light"
    else:
        notebook_status = "clear"

    mapping = {
        "clear": "low",
        "light": "low",
        "moderate": "medium",
        "heavy": "high",
    }
    return mapping[notebook_status]
