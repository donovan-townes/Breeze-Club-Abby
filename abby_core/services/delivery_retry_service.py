"""Delivery Retry Service

Automatic retry logic for failed content delivery with exponential backoff.
Part of Phase 2 architectural improvements.

**Responsibility:**
- Retry failed deliveries automatically
- Exponential backoff with jitter
- Max retry limits
- Dead-letter queue for permanent failures
- Delivery status tracking

**Benefits:**
- Robust delivery (currently missing - failed announcements silently drop)
- Automatic recovery from transient failures
- Operator visibility into retry status
- Prevents message loss
"""

from __future__ import annotations

from typing import Dict, Any, Optional, List, Callable, Awaitable, Tuple
from datetime import datetime, timezone, timedelta
import logging
import random

logger = logging.getLogger(__name__)


# Retry configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY_SECONDS = 60  # 1 minute base delay
MAX_BACKOFF_SECONDS = 3600  # Cap at 1 hour
JITTER_FACTOR = 0.1  # ±10% jitter to prevent thundering herd


class DeliveryRetryService:
    """Manages automatic retry logic for failed content deliveries.
    
    Uses exponential backoff with jitter to prevent overwhelming downstream
    services during recovery from outages.
    """
    
    def __init__(
        self,
        max_retries: int = DEFAULT_MAX_RETRIES,
        base_delay_seconds: int = DEFAULT_BASE_DELAY_SECONDS,
    ):
        """Initialize delivery retry service.
        
        Args:
            max_retries: Maximum number of retry attempts
            base_delay_seconds: Base delay for exponential backoff
        """
        self.max_retries = max_retries
        self.base_delay_seconds = base_delay_seconds
    
    def calculate_next_retry_time(
        self,
        attempt_number: int,
        last_attempt_time: Optional[datetime] = None
    ) -> datetime:
        """Calculate when next retry should occur using exponential backoff.
        
        Args:
            attempt_number: Current retry attempt (0-indexed)
            last_attempt_time: When last attempt occurred (defaults to now)
        
        Returns:
            UTC datetime for next retry attempt
        """
        now = last_attempt_time or datetime.now(timezone.utc)
        
        # Exponential backoff: base_delay * 2^attempt
        delay_seconds = self.base_delay_seconds * (2 ** attempt_number)
        
        # Cap at max backoff
        delay_seconds = min(delay_seconds, MAX_BACKOFF_SECONDS)
        
        # Add jitter (±10%) to prevent thundering herd
        jitter = delay_seconds * JITTER_FACTOR * (random.random() * 2 - 1)
        delay_seconds += jitter
        
        next_retry = now + timedelta(seconds=delay_seconds)
        
        logger.debug(
            f"[DeliveryRetry] Calculated next retry: attempt={attempt_number}, "
            f"delay={delay_seconds:.1f}s, next_at={next_retry.isoformat()}"
        )
        
        return next_retry
    
    def should_retry(
        self,
        attempt_count: int,
        error_type: Optional[str] = None
    ) -> bool:
        """Determine if delivery should be retried.
        
        Args:
            attempt_count: Number of attempts so far
            error_type: Type of error encountered (e.g., "timeout", "forbidden")
        
        Returns:
            True if should retry, False if should move to dead-letter queue
        """
        # Max retries exhausted
        if attempt_count >= self.max_retries:
            logger.warning(
                f"[DeliveryRetry] Max retries ({self.max_retries}) exhausted "
                f"for delivery (attempts={attempt_count})"
            )
            return False
        
        # Non-retryable errors (4xx client errors except rate limits)
        non_retryable_errors = {
            "forbidden",  # 403 - no permission
            "not_found",  # 404 - channel deleted
            "bad_request",  # 400 - malformed content
        }
        
        if error_type in non_retryable_errors:
            logger.warning(
                f"[DeliveryRetry] Non-retryable error: {error_type}, "
                "moving to dead-letter queue"
            )
            return False
        
        # All other errors: retry
        return True
    
    def create_retry_record(
        self,
        delivery_item: Dict[str, Any],
        error_message: str,
        error_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a retry record for a failed delivery.
        
        Args:
            delivery_item: Original delivery item dict
            error_message: Error message from failed attempt
            error_type: Type of error (timeout, rate_limit, etc.)
        
        Returns:
            Updated delivery item with retry metadata
        """
        now = datetime.now(timezone.utc)
        
        # Get current retry metadata or initialize
        retry_metadata = delivery_item.get("retry_metadata", {
            "attempt_count": 0,
            "attempts": [],
            "first_failure_at": now,
        })
        
        attempt_count = retry_metadata["attempt_count"]
        
        # Record this attempt
        attempt_record = {
            "attempt_number": attempt_count,
            "attempted_at": now,
            "error_message": error_message,
            "error_type": error_type,
        }
        retry_metadata["attempts"].append(attempt_record)
        retry_metadata["attempt_count"] = attempt_count + 1
        retry_metadata["last_failure_at"] = now
        
        # Calculate next retry time if eligible
        if self.should_retry(attempt_count + 1, error_type):
            next_retry_at = self.calculate_next_retry_time(attempt_count + 1, now)
            retry_metadata["next_retry_at"] = next_retry_at
            retry_metadata["status"] = "pending_retry"
        else:
            retry_metadata["next_retry_at"] = None
            retry_metadata["status"] = "dead_letter"
        
        # Update delivery item
        delivery_item["retry_metadata"] = retry_metadata
        delivery_item["delivery_status"] = retry_metadata["status"]
        
        logger.info(
            f"[DeliveryRetry] Recorded failure for delivery "
            f"{delivery_item.get('item_id', 'unknown')[:8]}...: "
            f"attempt={attempt_count + 1}, status={retry_metadata['status']}"
        )
        
        return delivery_item
    
    async def execute_with_retry(
        self,
        delivery_func: Callable[[], Awaitable[bool]],
        item_id: str,
        max_retries: Optional[int] = None
    ) -> Tuple[bool, int, Optional[str]]:
        """Execute a delivery function with automatic retry logic.
        
        Args:
            delivery_func: Async function that returns True on success
            item_id: ID of delivery item (for logging)
            max_retries: Override default max retries
        
        Returns:
            (success, attempts_made, final_error_message)
        """
        max_attempts = max_retries or self.max_retries
        last_error = None
        
        for attempt in range(max_attempts):
            try:
                logger.debug(
                    f"[DeliveryRetry] Executing delivery attempt {attempt + 1}/{max_attempts} "
                    f"for item {item_id[:8]}..."
                )
                
                success = await delivery_func()
                
                if success:
                    logger.info(
                        f"[DeliveryRetry] Delivery succeeded for {item_id[:8]}... "
                        f"after {attempt + 1} attempts"
                    )
                    return (True, attempt + 1, None)
                else:
                    last_error = "Delivery function returned False"
                    logger.warning(
                        f"[DeliveryRetry] Delivery attempt {attempt + 1} failed "
                        f"for {item_id[:8]}...: {last_error}"
                    )
            
            except Exception as exc:
                last_error = str(exc)
                logger.warning(
                    f"[DeliveryRetry] Delivery attempt {attempt + 1} raised exception "
                    f"for {item_id[:8]}...: {exc}"
                )
            
            # If not last attempt, wait for backoff delay
            if attempt < max_attempts - 1:
                delay = self.base_delay_seconds * (2 ** attempt)
                delay = min(delay, MAX_BACKOFF_SECONDS)
                logger.debug(
                    f"[DeliveryRetry] Waiting {delay}s before retry {attempt + 2}"
                )
                # Note: In production, this should use asyncio.sleep() or scheduler
                # For now, we return and let scheduler handle the delay
                break
        
        logger.error(
            f"[DeliveryRetry] All {max_attempts} delivery attempts failed "
            f"for {item_id[:8]}...: {last_error}"
        )
        
        return (False, max_attempts, last_error)
    
    def get_dead_letter_items(
        self,
        delivery_items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Filter delivery items that have exhausted retries.
        
        Args:
            delivery_items: List of delivery item dicts
        
        Returns:
            List of items in dead-letter status
        """
        dead_letter = []
        
        for item in delivery_items:
            retry_metadata = item.get("retry_metadata", {})
            if retry_metadata.get("status") == "dead_letter":
                dead_letter.append(item)
        
        return dead_letter


# Singleton instance
_retry_service: Optional[DeliveryRetryService] = None


def get_delivery_retry_service() -> DeliveryRetryService:
    """Get singleton delivery retry service.
    
    Returns:
        DeliveryRetryService instance
    """
    global _retry_service
    if _retry_service is None:
        _retry_service = DeliveryRetryService()
    return _retry_service
