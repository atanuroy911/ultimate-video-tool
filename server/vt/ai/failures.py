"""Actionable service failures, without returning requests, headers or credentials."""
from __future__ import annotations

import httpx


def service_failure(service: str, error: Exception, *, local: bool = False) -> str:
    where = "Server details in Settings" if local else "the AI connection in Server details"
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
        if status in (401, 403):
            return f"{service} refused the connection. Check the saved key and account access in {where}."
        if status == 404:
            return (f"{service} could not find the selected model. Choose a downloaded model in {where}." if local else
                    f"{service} could not find that model or address. Check {where}.")
        if status == 429:
            return f"{service} has reached its usage limit. Wait a little and try again, or choose another director."
        if status >= 500:
            return f"{service} is temporarily unavailable. Try again later or choose another director."
        return f"{service} refused this request. Check {where} and try again."
    if isinstance(error, httpx.TimeoutException):
        return f"{service} took too long to answer. Try again or choose another director."
    if isinstance(error, httpx.HTTPError):
        return f"{service} is not reachable. Check its connection in Server details, then try again."
    return f"{service} returned an unreadable answer. Try again or choose another director."
