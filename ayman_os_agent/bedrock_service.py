"""Deprecated alias. Use ``ayman_os_agent.ai_service.AIService`` instead."""

from .ai_service import AIService

__all__ = ["AIService"]

# Backwards-compatible name used by older code paths.
BedrockService = AIService
