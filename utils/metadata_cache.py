import json
import time
from bson import json_util
from flask import current_app
from run import redis_client


ADMIN_STATS_CACHE_KEY = "mongo:metadata:admin-stats:v1"
DEFAULT_METADATA_CACHE_TTL = 60

# How long to wait before retrying Redis
DEFAULT_REDIS_RETRY_COOLDOWN = 30

# Redis state
_redis_cache_enabled = True
_redis_failed_at = None

def _disable_redis_cache(operation):
    """
    Temporarily disable Redis after a failure.
    It will be retried after the cooldown period.
    """
    global _redis_cache_enabled
    global _redis_failed_at

    if _redis_cache_enabled:
        current_app.logger.warning(
            "Redis metadata cache unavailable; "
            "temporarily bypassing cache (%s)",
            operation,
        )

    _redis_cache_enabled = False
    _redis_failed_at = time.time()


def _should_try_redis():
    """
    Decide whether Redis should be used.
    If Redis previously failed, wait for the
    cooldown period before trying again.
    """

    global _redis_cache_enabled
    global _redis_failed_at

    # Redis is currently enabled
    if _redis_cache_enabled:
        return True

    # No failure timestamp
    if _redis_failed_at is None:
        return False

    cooldown = current_app.config.get(
        "REDIS_RETRY_COOLDOWN",
        DEFAULT_REDIS_RETRY_COOLDOWN
    )

    elapsed = time.time() - _redis_failed_at

    # Still inside cooldown period
    if elapsed < cooldown:
        return False

    # Cooldown finished
    # Allow the next Redis operation to retry
    current_app.logger.info(
        "Redis cooldown expired; retrying Redis"
    )

    _redis_cache_enabled = True
    _redis_failed_at = None

    return True


def _redis_get(cache_key, operation):
    """
    Safely read from Redis.
    Returns None on cache miss or Redis failure.
    """

    if not _should_try_redis():
        return None

    try:
        return redis_client.get(cache_key)

    except Exception:
        _disable_redis_cache(operation)
        return None


def _redis_set(cache_key, value, ttl, operation):
    """
    Safely write to Redis.
    """

    if not _should_try_redis():
        return

    try:
        redis_client.setex(
            cache_key,
            int(ttl),
            value
        )

    except Exception:
        _disable_redis_cache(operation)


def _redis_delete(cache_key, operation):
    """
    Safely delete from Redis.
    """

    if not _should_try_redis():
        return

    try:
        redis_client.delete(cache_key)

    except Exception:
        _disable_redis_cache(operation)


# Admin Stats Cache
def get_admin_stats():

    cached = _redis_get(
        ADMIN_STATS_CACHE_KEY,
        "admin stats read"
    )

    if cached:

        if isinstance(cached, bytes):
            cached = cached.decode("utf-8")

        return json.loads(cached)

    # Redis unavailable or cache miss
    # Fall back to MongoDB
    from run import mongo

    stats = {
        "total_users": mongo.db.users.count_documents({}),
        "verified_users": mongo.db.users.count_documents(
            {"verified": True}
        ),
        "total_records": mongo.db.records.count_documents({}),
    }

    ttl = current_app.config.get(
        "MONGO_METADATA_CACHE_TTL",
        DEFAULT_METADATA_CACHE_TTL
    )

    # Cache result if Redis is available
    _redis_set(
        ADMIN_STATS_CACHE_KEY,
        json.dumps(stats),
        ttl,
        "admin stats write"
    )

    return stats


def invalidate_admin_stats():
    """
    Remove cached admin statistics after
    relevant database changes.
    """

    _redis_delete(
        ADMIN_STATS_CACHE_KEY,
        "admin stats invalidation"
    )


# Dashboard Cache
def _dashboard_cache_key(user_id):

    return (
        f"mongo:metadata:dashboard-records:v1:{user_id}"
    )


def get_dashboard_record_metadata(user_id):
    """
    Return cached record metadata for one user.
    """

    cache_key = _dashboard_cache_key(user_id)

    cached = _redis_get(
        cache_key,
        "dashboard metadata read"
    )

    if cached:

        if isinstance(cached, bytes):
            cached = cached.decode("utf-8")

        return json_util.loads(cached)

    # Redis unavailable or cache miss
    # Fall back to MongoDB
    from run import mongo

    records = list(
        mongo.db.records.find({
            "user_id": user_id
        }).sort(
            "uploaded_at",
            -1
        )
    )

    ttl = current_app.config.get(
        "MONGO_METADATA_CACHE_TTL",
        DEFAULT_METADATA_CACHE_TTL
    )

    # Try to cache records
    _redis_set(
        cache_key,
        json_util.dumps(records),
        ttl,
        "dashboard metadata write"
    )

    return records


def invalidate_dashboard_record_metadata(user_id):
    """
    Remove one user's cached dashboard metadata
    after a record write.
    """

    _redis_delete(
        _dashboard_cache_key(user_id),
        "dashboard metadata invalidation"
    )