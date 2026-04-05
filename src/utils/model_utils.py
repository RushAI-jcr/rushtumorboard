# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

from __future__ import annotations

import os

from semantic_kernel.connectors.ai.open_ai.prompt_execution_settings.azure_chat_prompt_execution_settings import (
    AzureChatPromptExecutionSettings,
)


_NON_TEMP_MODELS = frozenset({
    "o1", "o1-mini", "o3", "o3-mini", "o3-pro",
    "o4-mini", "gpt-5", "gpt-5-mini", "gpt-5-nano", "deepseek-r1",
})


def model_supports_temperature(deployment_name: str | None = None) -> bool:
    """
    Check if the given model supports the temperature parameter.

    Args:
        deployment_name: Azure deployment name to check. Falls back to
            AZURE_OPENAI_DEPLOYMENT_NAME env var if not provided.

    Returns:
        bool: True if the model supports temperature, False if it's a
        reasoning model that doesn't.
    """
    model_name = deployment_name or os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "")
    model = model_name.lower()
    for non_temp_model in _NON_TEMP_MODELS:
        if non_temp_model in model:
            return False
    return True


def make_structured_settings(response_format: type | None = None, deployment_name: str | None = None, **kwargs) -> AzureChatPromptExecutionSettings:
    """Create AzureChatPromptExecutionSettings with temperature guard.

    If the model supports temperature, sets temperature=0.0.
    Otherwise, omits temperature (for reasoning models).
    """
    settings = AzureChatPromptExecutionSettings(response_format=response_format, **kwargs)
    if model_supports_temperature(deployment_name):
        settings.temperature = 0.0
    return settings
