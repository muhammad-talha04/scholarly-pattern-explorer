import os
import tempfile

import pytest

# Offline + isolated: no model download, no writes into the repo's data/ dir.
os.environ.setdefault("ML_EMBEDDER", "hash")
os.environ.setdefault("ML_DATA_DIR", tempfile.mkdtemp(prefix="ml-api-test-"))
os.environ["ML_VECTOR_BACKEND"] = "local"
os.environ.pop("DATABASE_URL", None)
os.environ.pop("ML_LLM_URL", None)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Empty the in-process windows so one test cannot trip the next test's cap."""
    from app import ratelimit

    ratelimit.reset()
    yield
    ratelimit.reset()
