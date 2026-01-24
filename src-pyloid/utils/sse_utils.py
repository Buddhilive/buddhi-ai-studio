"""Server-Sent Events (SSE) utilities for real-time progress updates."""

import asyncio
import json
from typing import Any, AsyncGenerator, Dict


def create_sse_message(data: Dict[str, Any], event: str = "message") -> str:
    """Format data as Server-Sent Events message.
    
    Args:
        data: Data to send (will be JSON serialized)
        event: Event type (default: "message")
        
    Returns:
        Formatted SSE message string
    """
    # Serialize data to JSON
    json_data = json.dumps(data)
    
    # Format as SSE
    # event: <event_type>
    # data: <json_data>
    # (blank line)
    message = f"event: {event}\ndata: {json_data}\n\n"
    return message


async def sse_heartbeat(interval: float = 15.0) -> AsyncGenerator[str, None]:
    """Generate SSE heartbeat messages to keep connection alive.
    
    Args:
        interval: Heartbeat interval in seconds
        
    Yields:
        SSE comment lines (keep-alive)
    """
    while True:
        await asyncio.sleep(interval)
        # Send comment line (starts with :)
        yield ": heartbeat\n\n"
