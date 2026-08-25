from __future__ import annotations


class AppError(Exception):
    """User-facing pipeline/API error. Tracebacks stay in server logs only."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


MODEL_NOT_AVAILABLE = "MODEL_NOT_AVAILABLE"
INVALID_RASTER = "INVALID_RASTER"
UNSUPPORTED_BAND_CONFIGURATION = "UNSUPPORTED_BAND_CONFIGURATION"
INVALID_ALIGNMENT = "INVALID_ALIGNMENT"
MISSING_SHAPEFILE_SIDECARS = "MISSING_SHAPEFILE_SIDECARS"
CRS_ERROR = "CRS_ERROR"
PREDICTION_FAILED = "PREDICTION_FAILED"
