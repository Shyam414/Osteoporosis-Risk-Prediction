
import json

from bson import json_util
from flask import current_app

from run import redis_client


ADMIN_STATS_CACHE_KEY = "mongo:metadata:admin-stats:v1"
DEFAULT_METADATA_CACHE_TTL = 60

# Redis is an optional optimization. Once a connection failure is observed,
# bypass it for the rest of this process so every request does not retry and
# emit a large traceback while Redis is down. Restarting the app re-enables it.
_redis_cache_enabled = True


def _disable_redis_cache(operation):
    global _redis_cache_enabled
    if _redis_cache_enabled:
        current_app.logger.warning(
            "Redis metadata cache unavailable; bypassing cache until restart (%s)",
            operation,
        )
    _redis_cache_enabled = False


def get_admin_stats():
    if _redis_cache_enabled:
        try:
            cached = redis_client.get(ADMIN_STATS_CACHE_KEY)
            if cached:
                if isinstance(cached, bytes):
                    cached = cached.decode("utf-8")
                return json.loads(cached)
        except Exception:
            _disable_redis_cache("admin stats read")

    from run import mongo

    stats = {
        "total_users": mongo.db.users.count_documents({}),
        "verified_users": mongo.db.users.count_documents({"verified": True}),
        "total_records": mongo.db.records.count_documents({}),
    }

    ttl = current_app.config.get(
        "MONGO_METADATA_CACHE_TTL", DEFAULT_METADATA_CACHE_TTL
    )
    if _redis_cache_enabled:
        try:
            redis_client.setex(ADMIN_STATS_CACHE_KEY, int(ttl), json.dumps(stats))
        except Exception:
            _disable_redis_cache("admin stats write")

    return stats


def invalidate_admin_stats():
    """Remove cached aggregate MongoDB metadata after a relevant write."""
    if not _redis_cache_enabled:
        return
    try:
        redis_client.delete(ADMIN_STATS_CACHE_KEY)
    except Exception:
        _disable_redis_cache("admin stats invalidation")


def _dashboard_cache_key(user_id):
    return f"mongo:metadata:dashboard-records:v1:{user_id}"


def get_dashboard_record_metadata(user_id):
    """Return cached record metadata for one dashboard, excluding S3 URLs/files."""
    cache_key = _dashboard_cache_key(user_id)
    if _redis_cache_enabled:
        try:
            cached = redis_client.get(cache_key)
            if cached:
                if isinstance(cached, bytes):
                    cached = cached.decode("utf-8")
                return json_util.loads(cached)
        except Exception:
            _disable_redis_cache("dashboard metadata read")

    from run import mongo

    records = list(
        mongo.db.records.find({"user_id": user_id}).sort("uploaded_at", -1)
    )
    ttl = current_app.config.get(
        "MONGO_METADATA_CACHE_TTL", DEFAULT_METADATA_CACHE_TTL
    )
    if _redis_cache_enabled:
        try:
            redis_client.setex(cache_key, int(ttl), json_util.dumps(records))
        except Exception:
            _disable_redis_cache("dashboard metadata write")

    return records


def invalidate_dashboard_record_metadata(user_id):
    """Remove one user's cached dashboard metadata after a record write."""
    if not _redis_cache_enabled:
        return
    try:
        redis_client.delete(_dashboard_cache_key(user_id))
    except Exception:
        _disable_redis_cache("dashboard metadata invalidation")
