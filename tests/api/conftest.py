import os

# Placeholder values so the settings can load in tests. /health never
# connects to the database or Redis, so these don't need to be real.
os.environ.setdefault("POSTGRES_USER", "test")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("POSTGRES_DB", "test")
