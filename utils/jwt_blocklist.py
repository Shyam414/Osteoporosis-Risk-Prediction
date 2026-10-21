from datetime import datetime, timedelta, timezone
from flask import current_app
from run import mongo


def invalidate_user_sessions(user_id, expires_in=604800):
    try:
        mongo.db.jwt_blocklist.update_one(
            {"user_id": str(user_id)},
            {
                "$set": {
                    "user_id": str(user_id),
                    "blocked_until": (
                        datetime.now(timezone.utc)
                        + timedelta(seconds=max(1, int(expires_in)))
                    ),
                }
            },
            upsert=True,
        )
        return True

    except Exception:
        current_app.logger.exception(
            "Failed to invalidate user sessions"
        )
        return False


def is_user_blocklisted(user_id):
    try:
        now = datetime.now(timezone.utc)

        entry = mongo.db.jwt_blocklist.find_one({
            "user_id": str(user_id),
            "blocked_until": {"$gt": now},
        })

        return entry is not None

    except Exception:
        current_app.logger.exception(
            "Failed to check MongoDB JWT blocklist"
        )
        raise


def remove_user_from_blocklist(user_id):
    try:
        mongo.db.jwt_blocklist.delete_one({
            "user_id": str(user_id)
        })
        return True

    except Exception:
        current_app.logger.exception(
            "Failed to remove user from blocklist"
        )
        return False
