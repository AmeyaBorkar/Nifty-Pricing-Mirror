"""Thin wrapper around `growwapi.GrowwAPI` covering authentication."""

from __future__ import annotations

import logging

from .config import Settings

log = logging.getLogger(__name__)


class AuthenticationError(RuntimeError):
    """Raised when no usable Groww credential is configured."""


class GrowwClient:
    """Holds an authenticated `GrowwAPI` instance."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._api = self._authenticate(settings)

    @staticmethod
    def _authenticate(settings: Settings):
        from growwapi import GrowwAPI  # imported lazily so import-time is cheap

        if settings.access_token:
            log.info("Authenticating Groww with pre-issued access token")
            return GrowwAPI(settings.access_token)

        if settings.api_key and settings.totp_secret:
            import pyotp

            log.info("Authenticating Groww via TOTP flow")
            totp = pyotp.TOTP(settings.totp_secret).now()
            token = GrowwAPI.get_access_token(api_key=settings.api_key, totp=totp)
            return GrowwAPI(token)

        if settings.api_key and settings.api_secret:
            log.info("Authenticating Groww via API key + secret flow")
            token = GrowwAPI.get_access_token(
                api_key=settings.api_key, secret=settings.api_secret
            )
            return GrowwAPI(token)

        raise AuthenticationError(
            "No Groww credentials found. Set GROWW_ACCESS_TOKEN, or "
            "GROWW_API_KEY with either GROWW_API_SECRET or GROWW_TOTP_SECRET. "
            "See .env.example."
        )

    @property
    def api(self):
        return self._api

    @property
    def SEGMENT_CASH(self):
        return self._api.SEGMENT_CASH

    @property
    def SEGMENT_FNO(self):
        return self._api.SEGMENT_FNO

    @property
    def EXCHANGE_NSE(self):
        return self._api.EXCHANGE_NSE
