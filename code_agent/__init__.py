"""
Standalone Coding Agent

A LangGraph-based agent that generates, validates, and tests code in isolated sandboxes.
Independent of the Script Authoring Pipeline for standalone testing.
"""

from .graph import coding_agent

__all__ = ["coding_agent"]
