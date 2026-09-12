"""
ARQ Background Email Worker.

Handles asynchronous email sending via Redis queue so that
registration and password-reset endpoints return instantly
instead of waiting for SMTP.

Usage:
    # Start worker (add to docker-compose or run separately)
    arq app.workers.email_worker.WorkerSettings

    # Enqueue a task
    from arq import create_pool
    redis_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    await redis_pool.enqueue_job("send_verification_email_task", to_email, otp)
"""

from app.core.logging_config import logger
from app.core.config import settings


async def send_verification_email_task(ctx, to_email: str, otp: str) -> bool:
    """Background task: send email verification OTP."""
    from app.services.email_verification import send_verification_email
    logger.info("Worker: sending verification email to %s", to_email)
    return send_verification_email(to_email, otp)


async def send_password_reset_email_task(ctx, to_email: str, otp: str) -> bool:
    """Background task: send password reset OTP."""
    from app.services.email_verification import send_password_reset_email
    logger.info("Worker: sending password reset email to %s", to_email)
    return send_password_reset_email(to_email, otp)


async def startup(ctx):
    logger.info("ARQ email worker started")


async def shutdown(ctx):
    logger.info("ARQ email worker shutting down")


class WorkerSettings:
    """ARQ worker configuration."""
    functions = [send_verification_email_task, send_password_reset_email_task]
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 10
    job_timeout = 30  # seconds

    @property
    def redis_settings(self):
        from arq.connections import RedisSettings
        return RedisSettings.from_dsn(settings.redis_url) if settings.redis_url else None
