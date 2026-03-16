#!/usr/bin/env python3
"""PDF Agent — conversational CLI for AI-powered document generation.

Usage:
    python -m pdf_agent.main

Environment variables:
    OPENAI_API_KEY           – required when using the OpenAI provider (default)
    ANTHROPIC_API_KEY        – required when using the Anthropic provider
    PDF_AGENT_LLM_PROVIDER   – "azure" (default), "openai", "anthropic", "gemini", "bedrock"
    PDF_AGENT_MODEL           – model name override (default: gpt-4o)
    AZURE_OPENAI_ENDPOINT     – required for azure provider
    AZURE_OPENAI_DEPLOYMENT   – required for azure provider
    AZURE_OPENAI_API_KEY      – required for azure provider
    AZURE_OPENAI_API_VERSION  – optional (default: 2024-12-01-preview)
"""

from __future__ import annotations

import sys

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage

from pdf_agent.config import AgentConfig, get_config
from pdf_agent.graph.pdf_agent_graph import build_graph
from pdf_agent.graph.state import PDFAgentState


def _create_llm(config: AgentConfig) -> BaseChatModel:
    """Instantiate the chat model based on ``config.llm_provider``.

    Supported providers
    -------------------
    openai    : OpenAI ChatGPT models (default)
                Env: OPENAI_API_KEY
    anthropic : Anthropic Claude models
                Env: ANTHROPIC_API_KEY
    gemini    : Google Gemini via langchain-google-genai
                Env: GOOGLE_API_KEY
    azure     : Azure AI Foundry / Azure OpenAI
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

    # Explicit OpenAI or unknown provider — fall back to OpenAI with a warning
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


def run_cli() -> None:
    """Run the interactive CLI loop."""
    config = get_config()
    llm = _create_llm(config)
    graph = build_graph(llm, config)

    # Persistent state across turns
    state: PDFAgentState = {
        "messages": [],
        "intent": "",
        "document_spec": None,
        "pdf_path": None,
        "chat_response": None,
        "error": None,
    }

    print("=== PDF Generation Agent ===")
    print("Type your request (or 'quit' to exit).\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in {"quit", "exit", "q"}:
            print("Goodbye!")
            break

        # Append the new user message
        state["messages"] = [*state["messages"], HumanMessage(content=user_input)]

        # Run the graph
        result = graph.invoke(state)

        # Merge result back into persistent state
        state["document_spec"] = result.get("document_spec", state["document_spec"])
        state["pdf_path"] = result.get("pdf_path", state["pdf_path"])
        state["chat_response"] = result.get("chat_response")
        state["messages"] = result.get("messages", state["messages"])
        state["error"] = result.get("error")
        intent = result.get("intent", "")

        # Display outcome
        if state["error"]:
            print(f"\n⚠  Error: {state['error']}\n")
        elif intent == "chat":
            # Response was already streamed token-by-token inside the node
            pass
        elif state["pdf_path"] and intent in ("create", "edit"):
            print(f"\n✅ PDF generated at: {state['pdf_path']}\n")
        else:
            print("\n(no output produced)\n")


if __name__ == "__main__":
    run_cli()
