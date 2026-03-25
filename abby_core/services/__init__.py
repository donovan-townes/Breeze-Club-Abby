"""Abby Core Services

Platform-agnostic services for announcements, delivery, notifications, and other
cross-cutting concerns. These services work with any adapter (Discord, Web, CLI, etc.)

Services organize into:
- events_lifecycle: System event recording & lifecycle (seasons, world announcements)
- content_delivery: Content item management across lifecycle stages
- notification_service: Platform-agnostic notification dispatch
- economy_service: User economics and transactions
"""

from .content_delivery import (
    create_content_item,
    list_scheduled_due_items,
    list_due_items_for_delivery_global,
    bulk_update_lifecycle,
)

from .notification_service import (
    get_notification_service,
    NotificationLevel,
    NotificationTarget,
)

from .announcement_dispatcher import (
    get_announcement_dispatcher,
    AnnouncementDispatcher,
    AnnouncementStateError,
    AnnouncementValidationError,
)

from .dlq_service import (
    get_dlq_service,
    DLQService,
    DLQStatus,
    DLQErrorCategory,
)

from .metrics_service import (
    get_metrics_service,
    MetricsService,
    MetricType,
)

__all__ = [
    'create_content_item',
    'list_scheduled_due_items',
    'list_due_items_for_delivery_global',
    'bulk_update_lifecycle',
    'get_notification_service',
    'NotificationLevel',
    'NotificationTarget',
    'get_announcement_dispatcher',
    'AnnouncementDispatcher',
    'AnnouncementStateError',
    'AnnouncementValidationError',
    'get_dlq_service',
    'DLQService',
    'DLQStatus',
    'DLQErrorCategory',
    'get_metrics_service',
    'MetricsService',
    'MetricType',
]
