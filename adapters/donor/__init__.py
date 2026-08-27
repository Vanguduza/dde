"""Donor-search HTTP transport (EDR-0015). httpx stays in this package."""

from adapters.donor.http import fetch_uri

__all__ = ["fetch_uri"]
