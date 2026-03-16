"""Configuration module for the PDF generation agent."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env relative to this file's location: pdf_agent/ → project root
_ENV_FILE = Path(__file__).parent.parent / ".env"


class AgentConfig(BaseSettings):
    """Agent configuration loaded automatically from environment variables and .env.

    Pydantic Settings reads each field from the matching env var (see
    ``validation_alias`` per field), validates types, and raises a clear
    ``ValidationError`` at startup if a required value is missing or malformed.

    Supported providers (``PDF_AGENT_LLM_PROVIDER``):
        - ``azure``     – Azure AI Foundry / Azure OpenAI (default)
        - ``openai``    – OpenAI Chat models
        - ``anthropic`` – Anthropic Claude models
        - ``gemini``    – Google Gemini via langchain-google-genai
        - ``bedrock``   – AWS Bedrock via langchain-aws
    """

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),     # absolute path — works from any cwd
        env_file_encoding="utf-8",
        frozen=True,                  # immutable after construction
        populate_by_name=True,        # allow field name as well as alias in code
        extra="ignore",               # silently ignore unrecognised env vars
    )

    # ── Core LLM settings ────────────────────────────────────────────────
    llm_provider: str = Field(
        "azure", validation_alias="PDF_AGENT_LLM_PROVIDER"
    )
    model_name: str = Field(
        "gpt-5", validation_alias="PDF_AGENT_MODEL"
    )
    temperature: float = 1.0

    # ── Azure AI Foundry / Azure OpenAI ─────────────────────────────────
    # Required when llm_provider == "azure"
    azure_endpoint: str = Field(
        "", validation_alias="AZURE_OPENAI_ENDPOINT"
    )
    azure_deployment: str = Field(
        "", validation_alias="AZURE_OPENAI_DEPLOYMENT"
    )
    azure_api_version: str = Field(
        "2024-12-01-preview", validation_alias="AZURE_OPENAI_API_VERSION"
    )
    azure_api_key: SecretStr = Field(
        SecretStr(""), validation_alias="AZURE_OPENAI_API_KEY"
    )

    # ── AWS Bedrock ──────────────────────────────────────────────────────
    # Required when llm_provider == "bedrock"
    aws_region: str = Field(
        "us-east-1", validation_alias="AWS_REGION"
    )

    # ── Paths ────────────────────────────────────────────────────────────
    output_dir: Path = Field(
        Path("output"), validation_alias="PDF_AGENT_OUTPUT_DIR"
    )
    template_dir: Path = Field(
        default_factory=lambda: Path(__file__).parent / "templates"
    )

    # ── PDF defaults ─────────────────────────────────────────────────────
    default_page_size: str = "A4"
    default_margins: dict[str, str] = Field(
        default_factory=lambda: {
            "top": "2cm",
            "bottom": "2cm",
            "left": "2.5cm",
            "right": "2.5cm",
        }
    )

    def ensure_output_dir(self) -> Path:
        """Create the output directory if it doesn't exist and return it."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        return self.output_dir


def get_config() -> AgentConfig:
    """Return the agent configuration loaded from environment / .env."""
    return AgentConfig()
