"""Create the SQLite database and seed the sample evaluation criteria.
Usage: python scripts/seed_db.py [--reset]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import database  # noqa: E402

if __name__ == "__main__":
    database.init_db(reseed="--reset" in sys.argv)
    for c in database.get_criteria(active_only=False):
        print(c)
    print(f"Database ready at {database.DB_PATH}")
