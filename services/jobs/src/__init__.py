"""Job orchestration service.

Manages the lifecycle of analysis jobs:
- Queue management
- Progress tracking
- Result storage
- Retry logic
- Timeout handling

Uses Celery for task distribution and Redis for state tracking.
"""
