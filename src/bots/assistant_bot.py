# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import asyncio
import html
import logging
import os

from botbuilder.core import MessageFactory, TurnContext
from botbuilder.core.teams import TeamsActivityHandler
from botbuilder.integration.aiohttp import CloudAdapter
from botbuilder.schema import Activity, ActivityTypes
from semantic_kernel.agents import AgentGroupChat

from .bot_context import get_bot_context
from data_models.app_context import AppContext
from data_models.chat_context import ChatContext
from errors import NotAuthorizedError
from group_chat import create_group_chat

logger = logging.getLogger(__name__)


class AssistantBot(TeamsActivityHandler):
    def __init__(
        self,
        agent: dict,
        turn_contexts: dict[str, dict[str, TurnContext]],
        adapters: dict[str, CloudAdapter],
        app_context: AppContext
    ):
        self.app_context = app_context
        self.all_agents = app_context.all_agent_configs
        self.name = agent["name"]
        self.turn_contexts = turn_contexts
        self.adapters = adapters
        self.adapters[self.name].on_turn_error = self.on_error  # add error handling
        self.data_access = app_context.data_access
        self.root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    async def _get_bot_context(
        self, conversation_id: str, bot_name: str, turn_context: TurnContext
    ) -> TurnContext:
        return await get_bot_context(
            self.turn_contexts, self.all_agents, self.adapters,
            conversation_id, bot_name, turn_context,
        )

    async def on_message_activity(self, turn_context: TurnContext) -> None:
        conversation = turn_context.activity.conversation
        if not conversation or not conversation.id:
            logger.error("Received message with no conversation ID; dropping.")
            await turn_context.send_activity("Unable to process: no conversation context.")
            return
        conversation_id = conversation.id
        chat_context_accessor = self.data_access.chat_context_accessor
        chat_artifact_accessor = self.data_access.chat_artifact_accessor

        # Load chat context and set reference date from Teams message timestamp
        chat_ctx = await chat_context_accessor.read(conversation_id)
        if not chat_ctx.request_date and turn_context.activity.timestamp:
            chat_ctx.request_date = turn_context.activity.timestamp.strftime("%Y-%m-%d")

        # Delete thread if user asks
        if (turn_context.activity.text or "").endswith("clear"):
            # Add clear message to chat history
            chat_ctx.chat_history.add_user_message((turn_context.activity.text or "").strip())
            await chat_context_accessor.archive(chat_ctx)
            await chat_artifact_accessor.archive(conversation_id)
            await turn_context.send_activity("Conversation cleared!")
            return
        agents = self.all_agents
        if len(chat_ctx.chat_history.messages) == 0:
            # new conversation. Let's see which agents are available.
            async def is_part_of_conversation(agent):
                context = await self._get_bot_context(conversation_id, agent["name"], turn_context)
                typing_activity = Activity(
                    type=ActivityTypes.typing,
                    relates_to=turn_context.activity.relates_to,
                )
                typing_activity.apply_conversation_reference(
                    turn_context.activity.get_conversation_reference()
                )
                context.activity = typing_activity
                try:
                    await context.send_activity(typing_activity)
                    return True
                except Exception as e:
                    logger.info(f"Failed to send typing activity to {agent['name']}: {e}")
                    # This happens if the agent is not part of the group chat.
                    # Remove the agent from the list of available agents
                    return False

            part_of_conversation = await asyncio.gather(*(is_part_of_conversation(agent) for agent in self.all_agents))
            agents = [agent for agent, should_include in zip(self.all_agents, part_of_conversation) if should_include]

        (chat, chat_ctx) = create_group_chat(self.app_context, chat_ctx, participants=agents)

        # Add user message to chat history
        text = turn_context.remove_recipient_mention(turn_context.activity).strip()
        text = f"{self.name}: {text}"
        chat_ctx.chat_history.add_user_message(text)

        chat.is_complete = False
        await self.process_chat(chat, chat_ctx, turn_context)

        # Save chat context
        try:
            await chat_context_accessor.write(chat_ctx)
        except Exception:
            logger.exception("Failed to save chat context.")

    async def on_error(self, context: TurnContext, error: Exception):
        # This error is raised as Exception, so we can only use the message to handle the error.
        if str(error) == "Unable to proceed while another agent is active.":
            await context.send_activity("Please wait for the current agent to finish.")
        elif isinstance(error, NotAuthorizedError):
            logger.warning("Access denied for agent %s: %s", self.name, error)
            await context.send_activity("You are not authorized to access this agent.")
        else:
            logger.exception("Agent %s encountered an error", self.name)
            await context.send_activity("An error occurred. Please retype your request.")

    async def process_chat(
        self, chat: AgentGroupChat, chat_ctx: ChatContext, turn_context: TurnContext
    ):
        # If the mentioned agent is a facilitator, proceed with group chat.
        # Otherwise, proceed with standalone chat using the mentioned agent.
        agent_config = next(agent_config for agent_config in self.all_agents if agent_config["name"] == self.name)
        mentioned_agent = None if agent_config.get("facilitator", False) \
            else next(agent for agent in chat.agents if agent.name == self.name)

        conversation = turn_context.activity.conversation
        if not conversation or not conversation.id:
            logger.error("Lost conversation ID during process_chat; dropping.")
            return
        conv_id = conversation.id

        async for response in chat.invoke(agent=mentioned_agent):
            context = await self._get_bot_context(
                conv_id, response.name or "", turn_context
            )
            if response.content.strip() == "":
                continue

            msgText = self._append_links_to_msg(response.content, chat_ctx)
            msgText = await self.generate_sas_for_blob_urls(msgText, chat_ctx)

            activity = MessageFactory.text(msgText)
            activity.apply_conversation_reference(
                turn_context.activity.get_conversation_reference()
            )
            context.activity = activity

            await context.send_activity(activity)

            if chat.is_complete:
                break

    def _append_links_to_msg(self, msgText: str, chat_ctx: ChatContext) -> str:
        # Add patient data links to response
        try:
            image_urls = chat_ctx.display_image_urls
            clinical_trial_urls = chat_ctx.display_clinical_trials

            # Display loaded images
            if image_urls:
                msgText += "<h2>Patient Images</h2>"
                for url in image_urls:
                    safe_url = html.escape(url, quote=True)
                    filename = html.escape(url.split("/")[-1], quote=True)
                    msgText += f'<img src="{safe_url}" alt="{filename}" height="300px"/>'

            # Display clinical trials
            if clinical_trial_urls:
                msgText += "<h2>Clinical trials</h2>"
                for url in clinical_trial_urls:
                    safe_url = html.escape(url, quote=True)
                    trial = html.escape(url.split("/")[-1])
                    msgText += f'<li><a href="{safe_url}">{trial}</a></li>'

            return msgText
        finally:
            chat_ctx.display_image_urls = []
            chat_ctx.display_clinical_trials = []

    async def generate_sas_for_blob_urls(self, msgText: str, chat_ctx: ChatContext) -> str:
        try:
            for blob_url in chat_ctx.display_blob_urls:
                blob_sas_url = await self.data_access.blob_sas_delegate.get_blob_sas_url(blob_url)
                msgText = msgText.replace(blob_url, blob_sas_url)

            return msgText
        finally:
            chat_ctx.display_blob_urls = []
