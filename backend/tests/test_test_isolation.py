"""Guards for the suite itself: it must never use real credentials or reach real services."""

import socket

import pytest

from app.core.config import Settings, get_settings
from tests import conftest


def test_env_file_is_not_loaded():
    assert Settings.model_config["env_file"] is None


def test_settings_are_pinned_to_offline_values():
    settings = get_settings()
    assert settings.ENVIRONMENT == "test"
    assert settings.DATABASE_NAME == "moonlight_studio_test"
    assert settings.MONGODB_URL == "mongodb://localhost:27017"
    assert settings.EMAIL_PROVIDER == "mock"
    assert settings.GROQ_ENABLED is False
    assert settings.STORAGE_BACKEND == "local"
    assert settings.R2_ACCESS_KEY_ID == "" and settings.R2_SECRET_ACCESS_KEY == ""


def test_external_network_is_blocked_and_recorded():
    before = len(conftest._blocked_hosts)
    with pytest.raises(socket.gaierror):
        socket.getaddrinfo("api.groq.com", 443)
    assert conftest._blocked_hosts[before:] == ["api.groq.com"]
    # Acknowledge the deliberate attempt so the autouse guard doesn't fail this test.
    del conftest._blocked_hosts[before:]


def test_loopback_is_still_allowed():
    assert socket.getaddrinfo("localhost", 27017)
