"""
Day 1 acceptance check: confirm Postgres and Redis are reachable.
Run after `docker compose up -d postgres redis`.
"""
import sys

def check_postgres():
    import psycopg2
    try:
        conn = psycopg2.connect(
            dbname="callforge", user="postgres", password="postgres",
            host="localhost", port=5432,
        )
        conn.close()
        print("[OK] Postgres reachable on localhost:5432")
        return True
    except Exception as e:
        print(f"[FAIL] Postgres not reachable: {e}")
        return False

def check_redis():
    import redis
    try:
        r = redis.Redis(host="localhost", port=6379, db=0)
        r.ping()
        print("[OK] Redis reachable on localhost:6379")
        return True
    except Exception as e:
        print(f"[FAIL] Redis not reachable: {e}")
        return False

if __name__ == "__main__":
    ok = check_postgres() and check_redis()
    sys.exit(0 if ok else 1)