"""Thin wrapper around `growwapi.GrowwAPI` with auth + batched LTP fetch."""

from __future__ import annotations

import logging
import time
from typing import Iterable, Sequence

from .config import Settings

log = logging.getLogger(__name__)

# Groww live-data limit is 10 req/sec & 300 req/min. get_ltp accepts up to
# 50 symbols per call, so for the Nifty 50 universe we make 2 calls per
# refresh (spot + futures). A small floor between calls keeps us well clear
# of the per-second cap even on aggressive refresh intervals.
_MIN_GAP_SECONDS = 0.12
_BATCH_SIZE = 50


class AuthenticationError(RuntimeError):
    """Raised when no usable Groww credential is configured."""


class GrowwClient:
    """Holds an authenticated `GrowwAPI` instance and exposes the calls we need."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._api = self._authenticate(settings)
        self._last_call = 0.0

    # ------------------------------------------------------------------ auth
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

    # ----------------------------------------------------------------- props
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

    # ----------------------------------------------------------- live data
    def batched_ltp(
        self,
        segment: str,
        exchange_trading_symbols: Sequence[str],
    ) -> dict[str, float]:
        """Fetch last-traded prices in batches and merge the results."""

        out: dict[str, float] = {}
        for chunk in _chunks(exchange_trading_symbols, _BATCH_SIZE):
            self._throttle()
            response = self._api.get_ltp(
                segment=segment, exchange_trading_symbols=tuple(chunk)
            )
            out.update(_normalise_ltp_response(response))
        return out

    def quote(self, segment: str, exchange: str, trading_symbol: str) -> dict:
        self._throttle()
        return self._api.get_quote(
            exchange=exchange, segment=segment, trading_symbol=trading_symbol
        )

    # ------------------------------------------------------------ internals
    def _throttle(self) -> None:
        gap = time.monotonic() - self._last_call
        if gap < _MIN_GAP_SECONDS:
            time.sleep(_MIN_GAP_SECONDS - gap)
        self._last_call = time.monotonic()


def _chunks(seq: Sequence[str], size: int) -> Iterable[Sequence[str]]:
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def _normalise_ltp_response(resp) -> dict[str, float]:
    """Groww has shipped slightly different LTP shapes across SDK versions.

    Accepts either:
      * `{ "NSE_RELIANCE": 1234.5 }`
      * `{ "NSE_RELIANCE": { "ltp": 1234.5, ... } }`
      * `{ "data": { ... } }`
    """

    if isinstance(resp, dict) and "data" in resp and isinstance(resp["data"], dict):
        resp = resp["data"]
    if not isinstance(resp, dict):
        return {}

    out: dict[str, float] = {}
    for key, value in resp.items():
        if isinstance(value, (int, float)):
            out[key] = float(value)
        elif isinstance(value, dict):
            for candidate in ("ltp", "last_price", "lastPrice", "price"):
                if candidate in value and value[candidate] is not None:
                    out[key] = float(value[candidate])
                    break
    return out
