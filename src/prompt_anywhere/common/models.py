"""Shared wire models between UI and host.

Keep these lightweight and stable; they form the UI↔host contract.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class Attachment(BaseModel):
    kind: str
    path: str


class PromptContext(BaseModel):
    cwd: Optional[str] = None
    active_window_title: Optional[str] = None
    extra: dict[str, Any] = Field(default_factory=dict)


class SendPromptRequest(BaseModel):
    text: str
    attachments: list[Attachment] = Field(default_factory=list)
    context: PromptContext = Field(default_factory=PromptContext)


class StreamEvent(BaseModel):
    type: Literal["token", "final", "error"]
    text: Optional[str] = None
    meta: dict[str, Any] = Field(default_factory=dict)
