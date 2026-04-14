"""API ファクトリー関数."""

from __future__ import annotations

from fmcli.core.output import get_timeout
from fmcli.domain.models import Profile
from fmcli.infra.filemaker_api import FileMakerAPI
from fmcli.infra.http_client import HttpClient


def create_api(profile: Profile) -> FileMakerAPI:
    """Profile から FileMakerAPI を生成する."""
    client = HttpClient(profile.host, verify_ssl=profile.verify_ssl, timeout=get_timeout())
    return FileMakerAPI(client, profile.database)
