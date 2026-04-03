# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

from __future__ import annotations

import os

from semantic_kernel.connectors.ai.open_ai.prompt_execution_settings.azure_chat_prompt_execution_settings import (
    AzureChatPromptExecutionSettings,
)


def model_supports_temperature() -> bool:
    """
    Check if the given model supports the temperature parameter.

    Args:
        model_name: checks AZURE_OPENAI_DEPLOYMENT_NAME from environment.

    Returns:
        bool: True if the model supports temperature, False if it's a non-temperature/reasoning model that doesn't.
    """
    non_temp_models = {"o1", "o1-mini", "o3", "o3-mini", "o3-pro",
                       "o4-mini", "gpt-5", "gpt-5-mini", "gpt-5-nano", "DeepSeek-R1"}

    model_name = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "")

    # Check if the model name contains any of the non-temperature model names
    model = model_name.lower()
    for non_temp_model in non_temp_models:
        if non_temp_model.lower() in model:
            return False

    return True


def make_structured_settings(response_format=None, **kwargs) -> AzureChatPromptExecutionSettings:
    """Create AzureChatPromptExecutionSettings with temperature guard.

    If the model supports temperature, sets temperature=0.0.
    Otherwise, omits temperature (for reasoning models).
    """
    settings = AzureChatPromptExecutionSettings(response_format=response_format, **kwargs)
    if model_supports_temperature():
        settings.temperature = 0.0
    return settings
