from flask import current_app
from run import redis_client


def blocklist_token(jti, expires_in):
    """
    Add a JWT JTI to the blocklist until
    the token naturally expires.
    """
    try:
        redis_client.setex(
            f"jwt:blocklist:{jti}",
            int(expires_in),
            "revoked"
        )

        return True

    except Exception:
        current_app.logger.warning(
            "JWT blocklist unavailable; "
            "continuing with fail-open authentication"
        )
        return False


def is_token_blocklisted(jti):
    """
    Check whether a JWT has been revoked.
    """

    try:
        return redis_client.get(
            f"jwt:blocklist:{jti}"
        ) is not None

    except Exception:
        current_app.logger.warning(
            "JWT blocklist unavailable; "
            "continuing with fail-open authentication"
        )
        return False