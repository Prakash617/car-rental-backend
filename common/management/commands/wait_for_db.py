import time

import redis
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.utils import OperationalError


class Command(BaseCommand):
    """Django management command to pause execution until database and redis are available."""

    help = "Waits for database and Redis services to become available."

    def handle(self, *args, **options):
        self.stdout.write("Waiting for PostgreSQL database...")
        db_up = False
        attempts = 0
        while not db_up and attempts < 30:
            try:
                connection.ensure_connection()
                db_up = True
            except OperationalError:
                attempts += 1
                self.stdout.write(f"Database unavailable, waiting 1 second... ({attempts}/30)")
                time.sleep(1)

        if not db_up:
            self.stderr.write(self.style.ERROR("Could not connect to database after 30 attempts."))
            exit(1)

        self.stdout.write(self.style.SUCCESS("PostgreSQL database is available!"))

        self.stdout.write("Waiting for Redis cache...")
        redis_up = False
        redis_attempts = 0
        r = redis.from_url(settings.REDIS_URL)
        while not redis_up and redis_attempts < 30:
            try:
                r.ping()
                redis_up = True
            except (redis.ConnectionError, redis.TimeoutError):
                redis_attempts += 1
                self.stdout.write(f"Redis unavailable, waiting 1 second... ({redis_attempts}/30)")
                time.sleep(1)

        if not redis_up:
            self.stderr.write(self.style.ERROR("Could not connect to Redis after 30 attempts."))
            exit(1)

        self.stdout.write(self.style.SUCCESS("Redis is available!"))
