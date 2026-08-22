"""
Circuit Breaker — Dynamic Polling Strategy for the XML Benefits Register.

Strategy (designed during architecture phase):
1. CLOSED (Healthy): No background polling. Requests go through normally.
2. OPEN (Dead):      All requests instantly return "server is down" (no waiting).
                     A background poller pings /health every 1 second.
3. Recovery:         When /health responds OK, flip back to CLOSED, stop polling.

This avoids the "blind spot" problem of pure active polling and eliminates
wasted traffic when the server is healthy.
"""

import asyncio
import httpx
import time
from enum import Enum

XML_HEALTH_URL = "http://127.0.0.1:8082/health"
HEALTH_CHECK_INTERVAL = 1.0  # seconds — aggressive polling when server is dead
HEALTH_CHECK_TIMEOUT = 2.0   # seconds — timeout for the health check itself


class CircuitState(str, Enum):
    CLOSED = "CLOSED"   # Healthy — requests flow normally
    OPEN = "OPEN"       # Dead — requests are instantly rejected


class CircuitBreaker:
    """
    Circuit Breaker for the XML Benefits Register.

    Uses the Dynamic Polling strategy:
    - No polling when healthy (zero wasted traffic).
    - 1-second polling when dead (fastest possible recovery detection).
    """

    def __init__(self):
        self.state: CircuitState = CircuitState.CLOSED
        self.opened_at: float | None = None
        self.last_health_check: float | None = None
        self._polling_task: asyncio.Task | None = None

    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN

    def trip(self) -> None:
        """
        Trip the circuit breaker to OPEN state.
        Called when a request fails AND /health also fails.
        Starts the background health poller.
        """
        if self.state == CircuitState.OPEN:
            return  # Already open, don't start another poller

        self.state = CircuitState.OPEN
        self.opened_at = time.time()
        print(f"  [circuit-breaker] TRIPPED → OPEN at {time.strftime('%H:%M:%S')}")

        # Start the background poller
        self._start_polling()

    def close(self) -> None:
        """
        Close the circuit breaker (server recovered).
        Stops the background health poller.
        """
        self.state = CircuitState.CLOSED
        self.opened_at = None
        print(f"  [circuit-breaker] RECOVERED → CLOSED at {time.strftime('%H:%M:%S')}")

        # Stop the background poller
        self._stop_polling()

    def _start_polling(self) -> None:
        """Start the background health check polling task."""
        if self._polling_task is not None and not self._polling_task.done():
            return  # Already polling

        try:
            loop = asyncio.get_event_loop()
            self._polling_task = loop.create_task(self._poll_health())
        except RuntimeError:
            pass  # No event loop running (e.g., during testing)

    def _stop_polling(self) -> None:
        """Stop the background health check polling task."""
        if self._polling_task is not None and not self._polling_task.done():
            self._polling_task.cancel()
            self._polling_task = None

    async def _poll_health(self) -> None:
        """
        Background task that pings /health every 1 second while
        the circuit is OPEN. Closes the circuit when /health responds OK.
        """
        print(f"  [circuit-breaker] Starting health poller (every {HEALTH_CHECK_INTERVAL}s)")

        while self.state == CircuitState.OPEN:
            try:
                async with httpx.AsyncClient(timeout=HEALTH_CHECK_TIMEOUT) as client:
                    response = await client.get(XML_HEALTH_URL)
                    self.last_health_check = time.time()

                    if response.status_code == 200:
                        # Server is back! Close the circuit.
                        self.close()
                        return

            except (httpx.ConnectError, httpx.TimeoutException):
                # Still dead, keep polling
                self.last_health_check = time.time()

            except asyncio.CancelledError:
                # Task was cancelled (e.g., server shutdown)
                return

            except Exception:
                pass

            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

    async def check_health_and_trip(self) -> None:
        """
        Called after a failed request. Checks /health to determine
        if the server is truly dead (vs just a random 500 error).

        If /health fails → trips the circuit breaker.
        If /health succeeds → server is alive, it was just a random failure.
        """
        try:
            async with httpx.AsyncClient(timeout=HEALTH_CHECK_TIMEOUT) as client:
                response = await client.get(XML_HEALTH_URL)
                if response.status_code == 200:
                    # Server is alive, just had a random failure. Don't trip.
                    return
        except (httpx.ConnectError, httpx.TimeoutException):
            pass

        # /health also failed — server is truly dead. Trip the breaker.
        self.trip()

    def get_status(self) -> dict:
        """Returns the current status of the circuit breaker."""
        info = {
            "state": self.state.value,
        }
        if self.opened_at is not None:
            info["open_since_seconds"] = round(time.time() - self.opened_at, 1)
        if self.last_health_check is not None:
            info["last_health_check_seconds_ago"] = round(
                time.time() - self.last_health_check, 1
            )
        return info


# Singleton instance — shared across the entire application
xml_circuit_breaker = CircuitBreaker()
