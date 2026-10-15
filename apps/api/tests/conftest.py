import os
import tempfile

# Offline + isolated: no model download, no writes into the repo's data/ dir.
os.environ.setdefault("ML_EMBEDDER", "hash")
os.environ.setdefault("ML_DATA_DIR", tempfile.mkdtemp(prefix="ml-api-test-"))
os.environ["ML_VECTOR_BACKEND"] = "local"
os.environ.pop("DATABASE_URL", None)
os.environ.pop("ML_LLM_URL", None)
