# Shared Bot Framework turn-context helpers.
#
# Both AssistantBot and MagenticBot need to create TurnContext objects
# for other bots in the conversation and cache them by conversation ID.
# This module extracts that duplicated infrastructure.

from botbuilder.core import TurnContext
from botbuilder.integration.aiohttp import CloudAdapter


async def create_turn_context(
    all_agents: list[dict],
    adapters: dict[str, CloudAdapter],
    bot_name: str,
    turn_context: TurnContext,
) -> TurnContext:
    """Create a TurnContext wired to *bot_name*'s adapter and credentials."""
    app_id = next(
        agent["bot_id"] for agent in all_agents if agent["name"] == bot_name
    )

    adapter = adapters[bot_name]
    claims_identity = adapter.create_claims_identity(app_id)
    connector_factory = (
        adapter.bot_framework_authentication.create_connector_factory(
            claims_identity
        )
    )
    connector_client = await connector_factory.create(
        turn_context.activity.service_url, "https://api.botframework.com"
    )
    user_token_client = (
        await adapter.bot_framework_authentication.create_user_token_client(
            claims_identity
        )
    )

    async def logic(context: TurnContext):  # noqa: ARG001
        pass

    context = TurnContext(adapter, turn_context.activity)
    context.turn_state[CloudAdapter.BOT_IDENTITY_KEY] = claims_identity
    context.turn_state[CloudAdapter.BOT_CONNECTOR_CLIENT_KEY] = connector_client
    context.turn_state[CloudAdapter.USER_TOKEN_CLIENT_KEY] = user_token_client
    context.turn_state[CloudAdapter.CONNECTOR_FACTORY_KEY] = connector_factory
    context.turn_state[CloudAdapter.BOT_OAUTH_SCOPE_KEY] = "https://api.botframework.com/.default"
    context.turn_state[CloudAdapter.BOT_CALLBACK_HANDLER_KEY] = logic

    return context


async def get_bot_context(
    turn_contexts: dict[str, dict[str, TurnContext]],
    all_agents: list[dict],
    adapters: dict[str, CloudAdapter],
    conversation_id: str,
    bot_name: str,
    turn_context: TurnContext,
) -> TurnContext:
    """Return a cached TurnContext for *bot_name*, creating one if needed."""
    if conversation_id not in turn_contexts:
        turn_contexts[conversation_id] = {}

    if bot_name not in turn_contexts[conversation_id]:
        context = await create_turn_context(all_agents, adapters, bot_name, turn_context)
        turn_contexts[conversation_id][bot_name] = context

    return turn_contexts[conversation_id][bot_name]
