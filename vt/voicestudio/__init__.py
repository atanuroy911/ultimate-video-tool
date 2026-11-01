"""VoiceStudio (https://github.com/debpalash/VoiceStudio) as a voice engine: a small client for its HTTP API, used by the `voicestudio` voice in vt/tts.py,
by the voice.* modules and by the Engines page. VoiceStudio is AGPL-3.0 and runs as its own service; nothing of it is copied here."""
from .client import VoiceStudioClient, VoiceStudioError, client_for

__all__ = ["VoiceStudioClient", "VoiceStudioError", "client_for"]
