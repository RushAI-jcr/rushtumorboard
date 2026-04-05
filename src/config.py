# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import json
import logging
import os
import re
from typing import Any

import yaml
from azure.monitor.opentelemetry import configure_azure_monitor
from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

logger = logging.getLogger(__name__)
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


def setup_app_insights_logging(credential, log_level=logging.DEBUG) -> None:
    """Configure OpenTelemetry logging and tracing for Application Insights."""
    os.environ["OTEL_EXPERIMENTAL_RESOURCE_DETECTORS"] = "azure_app_service"
    trace.set_tracer_provider(TracerProvider())
    tracer_provider = trace.get_tracer_provider()

    # Configure Azure Monitor Exporter
    if os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        exporter = AzureMonitorTraceExporter(
            connection_string=os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"),
        )
        span_processor = BatchSpanProcessor(exporter)
        tracer_provider.add_span_processor(span_processor)  # type: ignore[attr-defined]

    # Instrument FastAPI
    FastAPIInstrumentor().instrument()

    # Instrument Logging
    LoggingInstrumentor().instrument(set_logging_format=True)

    # Configure Azure Monitor if connection string is set
    if os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        configure_azure_monitor(
            credential=credential,
            logger=logging.getLogger(__name__),
            connection_string=os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"),
            logging_exporter_enabled=True,
            tracing_exporter_enabled=True,
            metrics_exporter_enabled=True,
            enable_live_metrics=True,
            formatter=formatter
        )

    # Ensure all loggers propagate to root for Azure Monitor
    for name in logging.root.manager.loggerDict:
        logging.getLogger(name).propagate = True


def setup_logging(log_level=logging.DEBUG) -> None:
    # Create a logging handler to write logging records, in OTLP format, to the exporter.
    console_handler = logging.StreamHandler()

    # Add filters to the handler to only process records from semantic_kernel.
    # console_handler.addFilter(logging.Filter("semantic_kernel"))
    console_handler.setFormatter(formatter)

    logger = logging.getLogger()
    logger.addHandler(console_handler)
    logger.setLevel(log_level)


_REQUIRED_AGENT_FIELDS = {"name", "description"}
_VALID_TOOL_TYPES = {"function", "openapi"}


def _validate_agent_config(agents: list[dict], scenario: str) -> None:
    """Validate agents.yaml structure at startup to catch config errors early."""
    for i, agent in enumerate(agents):
        # Required top-level fields
        for field in _REQUIRED_AGENT_FIELDS:
            if field not in agent:
                raise ValueError(
                    f"agents.yaml[{i}]: missing required field '{field}'"
                )
        name = agent["name"]
        # Validate tool entries
        for tool in agent.get("tools", []):
            if "name" not in tool:
                raise ValueError(
                    f"agents.yaml agent '{name}': tool entry missing 'name'"
                )
            tool_type = tool.get("type", "function")
            if tool_type not in _VALID_TOOL_TYPES:
                raise ValueError(
                    f"agents.yaml agent '{name}': unknown tool type '{tool_type}'"
                )
            # Verify function tool modules are importable
            if tool_type == "function":
                tool_name = tool["name"]
                try:
                    import importlib
                    importlib.import_module(f"scenarios.{scenario}.tools.{tool_name}")
                except ModuleNotFoundError:
                    raise ValueError(
                        f"agents.yaml agent '{name}': tool module "
                        f"'scenarios.{scenario}.tools.{tool_name}' not found"
                    )


_ENV_VAR_RE = re.compile(r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}')


def _resolve_env_vars_in_agents(agents: list[dict]) -> list[dict]:
    """Resolve ${ENV_VAR} references in string values within agent configs.

    Empty resolved strings are converted to None so that optional fields like
    ``deployment`` fall back to defaults when the env var is unset.
    """
    def _resolve(value: Any) -> Any:
        if isinstance(value, str) and _ENV_VAR_RE.search(value):
            def _sub(m: re.Match) -> str:
                var_name = m.group(1)
                env_val = os.environ.get(var_name, "")
                if not env_val:
                    logger.debug("Env var %s not set, resolving to empty", var_name)
                return env_val
            resolved = _ENV_VAR_RE.sub(_sub, value)
            return resolved if resolved else None
        if isinstance(value, dict):
            return {k: _resolve(v) for k, v in value.items()}
        if isinstance(value, list):
            return [_resolve(item) for item in value]
        return value
    return [_resolve(agent) for agent in agents]


def load_agent_config(scenario: str) -> list[dict]:
    src_dir = os.path.dirname(os.path.abspath(__file__))
    scenario_directory = os.path.join(src_dir, f"scenarios/{scenario}/config")

    agent_config_path = os.path.join(scenario_directory, "agents.yaml")
    excluded_agents_env = os.getenv("EXCLUDED_AGENTS", "")
    excluded_agents = excluded_agents_env.split(",") if excluded_agents_env else []
    logger.info("Excluding agents: %s", excluded_agents)

    with open(agent_config_path, "r", encoding="utf-8") as f:
        agent_config = yaml.safe_load(f)
        agent_config = _resolve_env_vars_in_agents(agent_config)
        agent_config = [agent for agent in agent_config if agent["name"] not in excluded_agents]
        _validate_agent_config(agent_config, scenario)
        logger.info(
            "Loaded agent config for scenario '%s': %s",
            scenario, [agent["name"] for agent in agent_config],
        )

    try:
        bot_ids = json.loads(os.getenv("BOT_IDS", "{}"))
    except json.JSONDecodeError:
        logger.error("Invalid JSON in BOT_IDS environment variable")
        bot_ids = {}
    try:
        hls_model_endpoints = json.loads(os.getenv("HLS_MODEL_ENDPOINTS", "{}"))
    except json.JSONDecodeError:
        logger.error("Invalid JSON in HLS_MODEL_ENDPOINTS environment variable")
        hls_model_endpoints = {}
    for agent in agent_config:
        agent["bot_id"] = bot_ids.get(agent["name"])
        agent["hls_model_endpoint"] = hls_model_endpoints
        if agent.get("addition_instructions"):
            for file in agent["addition_instructions"]:
                filepath = os.path.join(scenario_directory, file)
                try:
                    with open(filepath) as f:
                        agent["instructions"] += f.read()
                except FileNotFoundError:
                    logger.warning("Additional instructions file not found: %s", filepath)

    return agent_config


class DefaultConfig:
    """ Bot Configuration """

    def __init__(self, botId):
        self.APP_ID = botId
        self.APP_PASSWORD = os.environ.get("MicrosoftAppPassword", "")
        self.APP_TYPE = os.environ.get("MicrosoftAppType", "MultiTenant")
        self.APP_TENANTID = os.environ.get("MicrosoftAppTenantId", "")
