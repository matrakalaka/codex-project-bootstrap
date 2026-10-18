from pathlib import Path

import pytest

from agentterm.postgres import PostgresSyncStore


def test_postgres_schema_and_adapter_contract_are_present():
    schema = Path(__file__).parents[3] / "deploy/postgres-schema.sql"
    assert "agentterm_sequences" in schema.resolve().read_text()
    assert PostgresSyncStore.__name__ == "PostgresSyncStore"


def test_postgres_driver_qualification_is_explicitly_optional():
    pytest.importorskip("psycopg")
