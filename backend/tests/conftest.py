import os

os.environ["MODEL_PROVIDER"] = "mock"
os.environ["NOTIFICATION_PROVIDER"] = "mock"

import pytest

from backend.app.db import database


@pytest.fixture(scope="session", autouse=True)
def isolate_test_database(tmp_path_factory):
    original_path = database.DB_PATH
    database.DB_PATH = tmp_path_factory.mktemp("leon-backend-tests") / "leon.db"
    try:
        yield
    finally:
        database.DB_PATH = original_path
