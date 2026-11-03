"""AI YouTube Shorts Generator and Highlight Extraction module."""
from .detector import detect_highlights
from .splitter import slice_short_project

__all__ = ["detect_highlights", "slice_short_project"]
