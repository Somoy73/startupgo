"""Errors raised by the agent."""


class AgentError(RuntimeError):
    """A startup could not be profiled (configuration, LLM or source failure)."""
