# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import importlib
import logging
import os
from typing import Any, Awaitable, Callable, override

from pydantic import BaseModel
from semantic_kernel import Kernel
from semantic_kernel.agents import AgentGroupChat, ChatCompletionAgent
from semantic_kernel.agents.channels.chat_history_channel import ChatHistoryChannel
from semantic_kernel.agents.strategies.selection.kernel_function_selection_strategy import \
    KernelFunctionSelectionStrategy
from semantic_kernel.agents.strategies.termination.kernel_function_termination_strategy import \
    KernelFunctionTerminationStrategy
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
from semantic_kernel.connectors.ai.open_ai.prompt_execution_settings.azure_chat_prompt_execution_settings import \
    AzureChatPromptExecutionSettings
from semantic_kernel.connectors.ai.open_ai.services.azure_chat_completion import AzureChatCompletion
from semantic_kernel.connectors.openapi_plugin import OpenAPIFunctionExecutionParameters
from semantic_kernel.contents.chat_history import ChatHistory
from semantic_kernel.contents.chat_message_content import ChatMessageContent
from semantic_kernel.contents.history_reducer.chat_history_truncation_reducer import ChatHistoryTruncationReducer
from semantic_kernel.functions.kernel_function_from_prompt import KernelFunctionFromPrompt
from semantic_kernel.functions.kernel_arguments import KernelArguments
from semantic_kernel.prompt_template.input_variable import InputVariable
from semantic_kernel.prompt_template.prompt_template_config import PromptTemplateConfig

from data_models.app_context import AppContext
from data_models.chat_context import ChatContext
from data_models.plugin_configuration import PluginConfiguration
from healthcare_agents import HealthcareAgent
from healthcare_agents import config as healthcare_agent_config
from utils.logging_http_client import create_logging_http_client
from utils.model_utils import model_supports_temperature

DEFAULT_MODEL_TEMP = 0
DEFAULT_TOOL_TYPE = "function"

logger = logging.getLogger(__name__)


class ChatRule(BaseModel):
    verdict: str
    reasoning: str


def create_auth_callback(chat_ctx: ChatContext) -> Callable[..., Awaitable[Any]]:
    """
    Creates an authentication callback for the plugin configuration.

    :param chat_ctx: The chat context to be used in the authentication.
    :return: A callable that returns an authentication token.
    """
    # TODO - get key or secret from Azure Key Vault for OpenAPI services.
    # Send the conversation ID as a header to the OpenAPI service.
    async def auth_callback():
        return {'conversation-id': chat_ctx.conversation_id}
    return auth_callback

# Need to introduce a CustomChatCompletionAgent and a CustomHistoryChannel because of issue https://github.com/microsoft/semantic-kernel/issues/12095


class CustomHistoryChannel(ChatHistoryChannel):
    """ChatHistoryChannel that filters tool messages and truncates history.

    In multi-agent group chats, tool call/result messages from other agents can
    leak into the thread via broadcasts.  OpenAI requires every role='tool'
    message to immediately follow a role='assistant' message with tool_calls.
    Broadcast ordering doesn't guarantee this, causing 400 errors.

    Fix: strip all FunctionCallContent / FunctionResultContent messages when
    populating the thread.  Each agent only needs the plain-text summaries
    from other agents, not their internal tool interactions.

    Also caps the thread length to prevent 128K context overflow.
    """

    _MAX_THREAD_MESSAGES: int = 14

    @override
    async def receive(self, history: list[ChatMessageContent],) -> None:
        from semantic_kernel.contents.function_call_content import FunctionCallContent
        from semantic_kernel.contents.function_result_content import FunctionResultContent
        from semantic_kernel.contents.utils.author_role import AuthorRole

        # Track count before super() appends, so we only process the delta
        # (new messages added by this broadcast). This prevents O(N²)
        # duplication when receive() is called repeatedly with accumulated history.
        prior_count = len(self.messages)
        await super().receive(history)
        new_messages = self.messages[prior_count:]

        for message in new_messages:
            # Skip tool-related messages — they originate from other agents'
            # auto-function-invocation loops and can arrive without their
            # paired tool_calls/tool_result counterpart, causing OpenAI 400s.
            if message.role == AuthorRole.TOOL:
                continue
            if any(isinstance(item, (FunctionCallContent, FunctionResultContent))
                   for item in (message.items or [])):
                continue
            await self.thread.on_new_message(message)

        # Cap thread length.  With no tool messages, any cut point is safe.
        if hasattr(self.thread, '_chat_history'):
            msgs = self.thread._chat_history.messages
            if len(msgs) > self._MAX_THREAD_MESSAGES:
                old_len = len(msgs)
                self.thread._chat_history.messages = msgs[-self._MAX_THREAD_MESSAGES:]
                logger.debug(
                    "Truncated agent thread history from %d to %d messages",
                    old_len, self._MAX_THREAD_MESSAGES,
                )

    @override
    async def invoke(self, agent, **kwargs):
        """Invoke with diagnostic logging of thread state."""
        from semantic_kernel.contents.function_call_content import FunctionCallContent
        from semantic_kernel.contents.function_result_content import FunctionResultContent

        if hasattr(self.thread, '_chat_history'):
            msgs = self.thread._chat_history.messages
            logger.info(
                "DIAG invoke agent=%s thread_msgs=%d channel_msgs=%d",
                agent.name, len(msgs), len(self.messages),
            )
            for i, m in enumerate(msgs[:5]):
                tool_items = [type(it).__name__ for it in (m.items or [])
                              if isinstance(it, (FunctionCallContent, FunctionResultContent))]
                logger.info(
                    "DIAG   thread[%d] role=%s name=%s tool_items=%s content=%.80s",
                    i, m.role, m.name, tool_items, (m.content or "")[:80],
                )
        async for item in super().invoke(agent, **kwargs):
            yield item


class CustomChatCompletionAgent(ChatCompletionAgent):
    """Custom ChatCompletionAgent to override the create_channel method."""

    @override
    async def create_channel(
        self, chat_history: ChatHistory | None = None, thread_id: str | None = None
    ) -> CustomHistoryChannel:
        """Create a CustomHistoryChannel that strips tool messages and caps length.

        Args:
            chat_history: The chat history for the channel.
            thread_id: The ID of the thread.

        Returns:
            An instance of CustomHistoryChannel.
        """
        from semantic_kernel.agents.chat_completion.chat_completion_agent import ChatHistoryAgentThread
        from semantic_kernel.contents.function_call_content import FunctionCallContent
        from semantic_kernel.contents.function_result_content import FunctionResultContent
        from semantic_kernel.contents.utils.author_role import AuthorRole

        CustomHistoryChannel.model_rebuild()

        # Strip tool messages and cap length to prevent context overflow and
        # orphaned-tool-message 400 errors.
        effective_history = None
        if chat_history and chat_history.messages:
            clean = [
                m for m in chat_history.messages
                if m.role != AuthorRole.TOOL
                and not any(isinstance(item, (FunctionCallContent, FunctionResultContent))
                            for item in (m.items or []))
            ]
            max_initial = CustomHistoryChannel._MAX_THREAD_MESSAGES
            if len(clean) > max_initial:
                clean = clean[-max_initial:]
            effective_history = ChatHistory(messages=clean)
            logger.debug(
                "Channel created with %d messages (from %d original)",
                len(clean), len(chat_history.messages),
            )

        thread = ChatHistoryAgentThread(chat_history=effective_history, thread_id=thread_id)

        if thread.id is None:
            await thread.create()

        messages = [message async for message in thread.get_messages()]

        return CustomHistoryChannel(messages=messages, thread=thread)


def create_group_chat(
    app_ctx: AppContext, chat_ctx: ChatContext, participants: list[dict] | None = None
) -> tuple[AgentGroupChat, ChatContext]:
    participant_configs = participants or app_ctx.all_agent_configs
    participant_names = [cfg.get("name", "unnamed") for cfg in participant_configs]
    logger.info("Creating group chat with participants: %s", participant_names)

    # Remove magentic agent from the list of agents. In the future, we could add agent type to deal with agents that should not be included in the Semantic Kernel group chat.
    all_agents_config = [
        agent for agent in participant_configs if agent.get("name") != "magentic"
    ]

    def _create_kernel_with_chat_completion(deployment_override: str | None = None) -> Kernel:
        kernel = Kernel()
        deployment = deployment_override or os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"]
        api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")
        service_kwargs: dict[str, Any] = {
            "service_id": "default",
            "deployment_name": deployment,
            "api_version": api_version,
        }
        api_key = os.environ.get("AZURE_OPENAI_API_KEY")
        if api_key:
            service_kwargs["api_key"] = api_key
            service_kwargs["endpoint"] = os.environ["AZURE_OPENAI_ENDPOINT"]
        else:
            service_kwargs["ad_token_provider"] = app_ctx.cognitive_services_token_provider
        kernel.add_service(AzureChatCompletion(**service_kwargs))
        return kernel

    def _create_agent(agent_config: dict):
        agent_kernel = _create_kernel_with_chat_completion()
        plugin_config = PluginConfiguration(
            kernel=agent_kernel,
            agent_config=agent_config,
            data_access=app_ctx.data_access,
            chat_ctx=chat_ctx,
            azureml_token_provider=app_ctx.azureml_token_provider,
            app_ctx=app_ctx,
        )
        is_healthcare_agent = healthcare_agent_config.yaml_key in agent_config and bool(
            agent_config[healthcare_agent_config.yaml_key])

        for tool in agent_config.get("tools", []):
            tool_name = tool.get("name")
            tool_type = tool.get("type", DEFAULT_TOOL_TYPE)

            # Add function tools
            if tool_type == "function":
                scenario = os.environ.get("SCENARIO")
                tool_module = importlib.import_module(f"scenarios.{scenario}.tools.{tool_name}")
                agent_kernel.add_plugin(tool_module.create_plugin(plugin_config), plugin_name=tool_name)
            # Add OpenAPI tools
            # See https://github.com/Azure-Samples/healthcare-agent-orchestrator/blob/main/docs/agent_development.md#agent-with-a-openapi-plugin-example
            elif tool_type == "openapi":
                openapi_document_path = tool.get("openapi_document_path")
                server_url_override = tool.get("server_url_override")
                timeout = tool.get("timeout", 600)
                debug_logging = tool.get("debug_logging", False)
                agent_kernel.add_plugin_from_openapi(
                    plugin_name=tool_name,
                    openapi_document_path=openapi_document_path,
                    execution_settings=OpenAPIFunctionExecutionParameters(
                        http_client=create_logging_http_client(timeout) if debug_logging else None,
                        auth_callback=create_auth_callback(chat_ctx),
                        server_url_override=server_url_override,
                        enable_payload_namespacing=True,
                        timeout=timeout
                    )
                )
            else:
                raise ValueError(f"Unknown tool type: {tool_type}")

        if model_supports_temperature():
            temperature = agent_config.get("temperature", DEFAULT_MODEL_TEMP)
            if temperature is None:
                temperature = DEFAULT_MODEL_TEMP
            logger.debug("Agent %s: temperature=%s", agent_config["name"], temperature)
        else:
            temperature = None
            logger.debug("Agent %s: temperature=None (reasoning model)", agent_config["name"])
        # Limit agent response length to prevent context window overflow in multi-agent chats.
        # 128K-token context with 9+ agents means each agent should stay under ~4K tokens output.
        max_completion_tokens = agent_config.get("max_completion_tokens", 4096)
        settings = AzureChatPromptExecutionSettings(
            function_choice_behavior=FunctionChoiceBehavior.Auto(), seed=42, temperature=temperature,
            max_tokens=max_completion_tokens)
        arguments = KernelArguments(settings=settings)
        instructions = agent_config.get("instructions")
        if agent_config.get("facilitator") and instructions:
            agent_list = "\n\t\t".join([f"- {agent['name']}: {agent['description']}" for agent in all_agents_config])
            instructions = instructions.replace("{{aiAgents}}", agent_list)

        return (CustomChatCompletionAgent(kernel=agent_kernel,
                                          name=agent_config["name"],
                                          instructions=instructions,
                                          description=agent_config["description"],
                                          arguments=arguments) if not is_healthcare_agent else
                HealthcareAgent(name=agent_config["name"],
                                chat_ctx=chat_ctx,
                                app_ctx=app_ctx))

    if model_supports_temperature():
        settings = AzureChatPromptExecutionSettings(
            function_choice_behavior=FunctionChoiceBehavior.Auto(), seed=42, temperature=0, response_format=ChatRule)
    else:
        settings = AzureChatPromptExecutionSettings(
            function_choice_behavior=FunctionChoiceBehavior.Auto(), seed=42, response_format=ChatRule)

    facilitator_agent = next((agent for agent in all_agents_config if agent.get("facilitator")), None)
    if facilitator_agent is None:
        logger.warning("No facilitator agent found; defaulting to %s", all_agents_config[0]["name"])
        facilitator_agent = all_agents_config[0]
    facilitator = facilitator_agent["name"]

    # Create selection function with proper input variable configuration
    agent_name_list = "\n".join([f"\t- {agent['name']}" for agent in all_agents_config])
    selection_prompt_config = PromptTemplateConfig(
        name="selection",
        description="Agent selection prompt",
        template=f"""
        You are overseeing a group chat between several AI agents and a human user.
        Determine which participant takes the next turn in a conversation based on the most recent participant. Follow these guidelines:

        1. **Participants**: Choose only from these participants:
            {agent_name_list}

        2. **General Rules**:
            - **{facilitator} Always Starts**: {facilitator} always goes first to formulate a plan. If the only message is from the user, {facilitator} goes next.
            - **Interactions between agents**: Agents may talk among themselves. If an agent requires information from another agent, that agent should go next.
                EXAMPLE:
                    "*agent_name*, please provide ..." then agent_name goes next.
            - **"back to you *agent_name*": If an agent says "back to you", that agent goes next.
                EXAMPLE:
                    "back to you *agent_name*" then output agent_name goes next.
            - **Once per turn**: Each participant can only speak once per turn.
            - **Default to {facilitator}**: Always default to {facilitator}. If no other participant is specified, {facilitator} goes next.
            - **Use best judgment**: If the rules are unclear, use your best judgment to determine who should go next, for the natural flow of the conversation.

        **Output**: Give the full reasoning for your choice and the verdict. The reasoning should include careful evaluation of each rule with an explanation. The verdict should be the name of the participant who should go next.

        History:
        {{{{$history}}}}
        """,
        input_variables=[
            InputVariable(name="history", allow_dangerously_set_content=True)
        ]
    )

    selection_function = KernelFunctionFromPrompt(
        function_name="selection",
        prompt_template_config=selection_prompt_config,
        prompt_execution_settings=settings
    )

    agent_name_csv = ",".join([agent['name'] for agent in all_agents_config])
    termination_prompt_config = PromptTemplateConfig(
        name="termination",
        description="Agent termination prompt",
        template=f"""
        Determine if the conversation should end based on the most recent message.
        You only have access to the last message in the conversation.

        Reply by giving your full reasoning, and the verdict. The verdict should be either "yes" or "no".

        You are part of a group chat with several AI agents and a user.
        The agents are names are:
            {agent_name_csv}

        If the most recent message is a question addressed to the user, return "yes".
        If the question is addressed to "we" or "us", return "yes". For example, if the question is "Should we proceed?", return "yes".
        If the question is addressed to another agent, return "no".
        If it is a statement addressed to another agent, return "no".
        Commands addressed to a specific agent should result in 'no' if there is clear identification of the agent.
        Commands addressed to "you" or "User" should result in 'yes'.
        If you are not certain, return "yes".

        EXAMPLES:
            - "User, can you confirm the correct patient ID?" => "yes"
            - "*ReportCreation*: Please compile the patient timeline. Let's proceed with *ReportCreation*." => "no" (ReportCreation is an agent)
            - "*ReportCreation*, please proceed ..." => "no" (ReportCreation is an agent)
            - "If you have any further questions or need assistance, feel free to ask." => "yes"
            - "Let's proceed with Radiology." => "no" (Radiology is an agent)
            - "*PatientStatus*, please use ..." => "no" (PatientStatus is an agent)
        History:
        {{{{$history}}}}
        """,
        input_variables=[
            InputVariable(name="history", allow_dangerously_set_content=True)
        ]
    )

    termination_function = KernelFunctionFromPrompt(
        function_name="termination",
        prompt_template_config=termination_prompt_config,
        prompt_execution_settings=settings
    )
    from semantic_kernel.agents.agent import Agent
    agents: list[Agent] = [_create_agent(agent) for agent in all_agents_config]

    agent_names = [agent["name"] for agent in all_agents_config]

    def evaluate_termination(result):
        logger.debug("Termination function result: %s", result)
        try:
            rule = ChatRule.model_validate_json(str(result.value[0]))
            return rule.verdict == "yes"
        except Exception as exc:
            logger.warning("Termination parse failed (%s), defaulting to terminate", exc)
            return True

    def evaluate_selection(result):
        logger.debug("Selection function result: %s", result)
        try:
            rule = ChatRule.model_validate_json(str(result.value[0]))
            return rule.verdict if rule.verdict in agent_names else facilitator
        except Exception as exc:
            logger.warning("Selection parse failed (%s), defaulting to %s", exc, facilitator)
            return facilitator

    selection_deployment = os.environ.get("AZURE_OPENAI_SELECTION_DEPLOYMENT_NAME")

    chat = AgentGroupChat(
        agents=agents,
        chat_history=chat_ctx.chat_history,
        selection_strategy=KernelFunctionSelectionStrategy(
            function=selection_function,
            kernel=_create_kernel_with_chat_completion(selection_deployment),
            result_parser=evaluate_selection,
            agent_variable_name="agents",
            history_variable_name="history",
            # Keep last 12 messages for selection (enough to see recent context
            # without overwhelming the selection model with full chat history)
            history_reducer=ChatHistoryTruncationReducer(
                target_count=12, auto_reduce=True
            ),
        ),
        termination_strategy=KernelFunctionTerminationStrategy(
            agents=[
                agent for agent in agents if agent.name == facilitator
            ],  # Only facilitator decides if the conversation ends
            function=termination_function,
            kernel=_create_kernel_with_chat_completion(selection_deployment),
            result_parser=evaluate_termination,
            agent_variable_name="agents",
            history_variable_name="history",
            maximum_iterations=30,
            # Termination only looks at the last message — keep minimal history
            # to reduce tokens sent to the termination LLM
            history_reducer=ChatHistoryTruncationReducer(
                target_count=1, auto_reduce=True
            ),
        ),
    )

    return (chat, chat_ctx)
