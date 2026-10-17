"""Exception hierarchy for GameLink Agent."""


class GameLinkError(Exception):
    """Base class for all GameLink Agent errors."""


class ConfigError(GameLinkError):
    """Invalid or missing configuration."""


class IngestError(GameLinkError):
    """Failed to read or understand the input game project."""


class AnalysisError(GameLinkError):
    """LLM analysis failed or returned unusable output."""


class SpecValidationError(GameLinkError):
    """A generated spec does not conform to its JSON Schema."""


class GenerateError(GameLinkError):
    """Server code generation failed."""


class DeployError(GameLinkError):
    """Deployment to the target environment failed."""


class JobCancelled(GameLinkError):
    """A long-running operation was cancelled by its caller."""
