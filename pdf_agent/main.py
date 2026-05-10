"""PDF Agent — FastAPI application for AI-powered document generation.

Usage:
    uvicorn pdf_agent.main:app --host 0.0.0.0 --port 8001 --reload

Environment variables:
    OPENAI_API_KEY           - required when using the OpenAI provider
    ANTHROPIC_API_KEY        - required when using the Anthropic provider
    PDF_AGENT_LLM_PROVIDER   - "azure" (default), "openai", "anthropic", "gemini", "bedrock"
    PDF_AGENT_MODEL          - model name override (default: gpt-4o)
    AZURE_OPENAI_ENDPOINT    - required for azure provider
    AZURE_OPENAI_DEPLOYMENT  - required for azure provider
    AZURE_OPENAI_API_KEY     - required for azure provider
    AZURE_OPENAI_API_VERSION - optional (default: 2024-12-01-preview)
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.language_models import BaseChatModel

from pdf_agent.config import AgentConfig, get_config
from pdf_agent.graph.pdf_agent_graph import build_graph
from pdf_agent.routes import router


def _create_llm(config: AgentConfig) -> BaseChatModel:
    """Instantiate the chat model based on ``config.llm_provider``.

    Supported providers
    -------------------
    openai    : OpenAI ChatGPT models
                Env: OPENAI_API_KEY
    anthropic : Anthropic Claude models
                Env: ANTHROPIC_API_KEY
    gemini    : Google Gemini via langchain-google-genai
                Env: GOOGLE_API_KEY
    azure     : Azure AI Foundry / Azure OpenAI (default)
                Env: AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT,
                     AZURE_OPENAI_DEPLOYMENT, AZURE_OPENAI_API_VERSION
    bedrock   : AWS Bedrock via langchain-aws
                Env: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION
                     (or an IAM role / instance profile)
    """
    provider = config.llm_provider.lower()

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=config.model_name,
            temperature=config.temperature,
        )

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=config.model_name,
            temperature=config.temperature,
        )

    if provider == "azure":
        from langchain_openai import AzureChatOpenAI

        return AzureChatOpenAI(
            azure_endpoint=config.azure_endpoint,
            azure_deployment=config.azure_deployment,
            openai_api_version=config.azure_api_version,
            api_key=config.azure_api_key.get_secret_value(),
            temperature=config.temperature,
        )

    if provider == "bedrock":
        from langchain_aws import ChatBedrock

        return ChatBedrock(
            model_id=config.model_name,
            region_name=config.aws_region,
            model_kwargs={"temperature": config.temperature},
        )

    if provider != "openai":
        import warnings

        warnings.warn(
            f"Unknown llm_provider '{config.llm_provider}', falling back to 'openai'.",
            stacklevel=2,
        )
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=config.model_name,
        temperature=config.temperature,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = get_config()
    config.ensure_output_dir()
    llm = _create_llm(config)
    graph = build_graph(llm, config)

    app.state.graph = graph
    app.state.agent_config = config
    yield


app = FastAPI(title="File Generation Agent API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


if __name__ == "__main__":
    uvicorn.run("pdf_agent.main:app", host="0.0.0.0", port=8001, reload=True)
