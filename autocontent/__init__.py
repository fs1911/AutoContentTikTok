"""AutoContentTikTok — vollautonomes, themenoffenes faceless TikTok-System."""
from .config import CONFIG
from .db import JobStore

__version__ = "0.1.0"
__all__ = ["CONFIG", "JobStore"]
