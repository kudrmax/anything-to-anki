"""Allow running the worker as ``python -m backend.infrastructure.queue``."""
from __future__ import annotations

import asyncio

from backend.infrastructure.queue.job_worker import main

asyncio.run(main())
