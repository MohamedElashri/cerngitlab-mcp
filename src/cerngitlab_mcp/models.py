"""Request/Response models for the HTTP API."""

from pydantic import BaseModel
from typing import Any, Optional, Dict


class McpRequest(BaseModel):
    """MCP tool request model."""

    name: str
    arguments: Dict[str, Any]


class McpResponse(BaseModel):
    """MCP tool response model."""

    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
