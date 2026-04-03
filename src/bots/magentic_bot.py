# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import asyncio
import logging
import os

from autogen_agentchat.base import TaskResult
from autogen_agentchat.messages import (MemoryQueryEvent, ModelClientStreamingChunkEvent, ThoughtEvent,
                                        ToolCallExecutionEvent, ToolCallRequestEvent, UserInputRequestedEvent)
from autogen_agentchat.teams import MagenticOneGroupChat
from autogen_core import CancellationToken
from botbuilder.core import ActivityHandler, MessageFactory, TurnContext
from botbuilder.integration.aiohttp import CloudAdapter

from .bot_context import get_bot_context as _get_bot_context_shared
from data_models.app_context import AppContext
from data_models.chat_context import ChatContext
from group_chat import create_group_chat
from magentic_chat import create_magentic_chat

logger = logging.getLogger(__name__)


def _get_conversation_id(turn_context: TurnContext) -> str:
    """Extract conversation ID from turn context, rejecting requests without one."""
    conversation = turn_context.activity.conversation
    if not conversation or not conversation.id:
        raise ValueError("Received message with no conversation ID")
    return conversation.id


class MagenticBot(ActivityHandler):
    """
    Provides a bot that can be used to interact with the MagenticOneOrchestrator agent.
    This is experimental, and uses the storage as the underlying mechanism to coordinate task and user input.
    When conversation starts, it creates a new blob in the storage to indicate that the conversation is in progress.
    When the chat needs input, it waits for the user to provide input in the blob.
    Better and more rubust mechanisms can be used in the future if magentic chat is found to be useful.
    """

    def __init__(
        self,
        agent: dict,
        adapters: dict[str, CloudAdapter],
        turn_contexts: dict[str, dict[str, TurnContext]],
        app_context: AppContext
    ):
        self.app_context = app_context
        self.all_agents = app_context.all_agent_configs
        self.adapters = adapters
        self.name = agent["name"]
        self.adapters[self.name].on_turn_error = self.on_error  # add error handling
        self.turn_contexts = turn_contexts
        self.data_access = app_context.data_access
        self.container_client = self.data_access.chat_context_accessor.container_client
        self.root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.include_monologue = True

    async def on_message_activity(self, turn_context: TurnContext) -> None:
        conversation_id = _get_conversation_id(turn_context)
        chat_context_accessor = self.data_access.chat_context_accessor
        chat_artifact_accessor = self.data_access.chat_artifact_accessor

        # Load chat context
        chat_ctx = await chat_context_accessor.read(conversation_id)

        # Delete thread if user asks
        if (turn_context.activity.text or "").endswith("monologue"):
            if self.include_monologue:
                await turn_context.send_activity("Monologue mode disabled.")
                self.include_monologue = False
            else:
                await turn_context.send_activity("Monologue mode enabled.")
                self.include_monologue = True
            return

        if (turn_context.activity.text or "").endswith("clear"):
            # Add clear message to chat history
            chat_ctx.chat_history.add_user_message((turn_context.activity.text or "").strip())
            await chat_context_accessor.archive(chat_ctx)
            await chat_artifact_accessor.archive(conversation_id)
            blob_path = f"{conversation_id}/user_message.txt"
            blob_client = self.container_client.get_blob_client(blob_path)
            try:
                await blob_client.delete_blob()
            except Exception:
                logger.exception("Failed to delete user message blob.")

            blob_path_conversation = f"{conversation_id}/conversation_in_progress.txt"

            blob_client = self.container_client.get_blob_client(blob_path_conversation)
            try:
                await blob_client.delete_blob()
            except Exception:
                logger.exception("Failed to delete conversation in progress blob.")

            await turn_context.send_activity("Conversation cleared!")
            return

        (chat, chat_ctx) = create_group_chat(self.app_context, chat_ctx)
        logger.info(f"Created chat for conversation {conversation_id}")

        blob_path_conversation = f"{conversation_id}/conversation_in_progress.txt"
        blob_client = self.container_client.get_blob_client(blob_path_conversation)

        text = turn_context.remove_recipient_mention(turn_context.activity).strip()

        if await blob_client.exists():
            logger.info("Conversation in progress, assuming reply.")
            chat_ctx.chat_history.add_user_message(text)
            await self.user_message_provided(text, turn_context)
        else:
            logger.info(f"Creating Magentic chat for conversation {conversation_id}")
            magentic_chat = create_magentic_chat(
                chat, self.app_context, self.create_input_func_callback(turn_context, chat_ctx))

            await self.process_magentic_chat(magentic_chat, text, turn_context, chat_ctx)

        # Save chat context
        try:
            await chat_context_accessor.write(chat_ctx)
        except Exception:
            logger.exception("Failed to save chat context.")

    async def on_error(self, context: TurnContext, error: Exception):
        # This error is raised as Exception, so we can only use the message to handle the error.
        if str(error) == "Unable to proceed while another agent is active.":
            await context.send_activity("Please wait for the current agent to finish.")
        else:
            logger.exception("Agent %s encountered an error", self.name)
            await context.send_activity("An error occurred. Please retype your request.")

    async def user_message_provided(self, message: str, turn_context: TurnContext):
        conv_id = _get_conversation_id(turn_context)
        blob_path = f"{conv_id}/user_message.txt"
        blob_client = self.container_client.get_blob_client(blob_path)
        await blob_client.upload_blob(message, overwrite=True)

    def create_input_func_callback(self, turn_context: TurnContext, chat_ctx: ChatContext):
        conv_id = _get_conversation_id(turn_context)

        async def user_input_func(prompt: str, cancellation_token: CancellationToken):
            logger.debug("User input requested (prompt length: %d)", len(prompt))
            if chat_ctx.chat_history.messages:
                last_content = chat_ctx.chat_history.messages[-1].content or ""
                await turn_context.send_activity("**User**: " + last_content)

            blob_path_conversation = f"{conv_id}/conversation_in_progress.txt"
            conversation_blob = self.container_client.get_blob_client(blob_path_conversation)
            await conversation_blob.upload_blob("conversation in progress", overwrite=True)

            blob_path = f"{conv_id}/user_message.txt"
            user_message_blob = self.container_client.get_blob_client(blob_path)
            while not (await user_message_blob.exists()):
                await asyncio.sleep(0.5)
                logger.info("Waiting for user input...")

            blob = await user_message_blob.download_blob()
            blob_str = await blob.readall()

            await conversation_blob.delete_blob()
            await user_message_blob.delete_blob()

            return blob_str.decode("utf-8")

        return user_input_func

    async def _get_bot_context(
        self, conversation_id: str, bot_name: str, turn_context: TurnContext
    ) -> TurnContext:
        return await _get_bot_context_shared(
            self.turn_contexts, self.all_agents, self.adapters,
            conversation_id, bot_name, turn_context,
        )

    async def process_magentic_chat(self, magentic_chat: MagenticOneGroupChat, text: str, turn_context: TurnContext, chat_ctx: ChatContext):
        conv_id = _get_conversation_id(turn_context)
        last_result = None
        stream = magentic_chat.run_stream(task=text, cancellation_token=CancellationToken())
        logger.info(f"Processing Magentic chat for conversation {conv_id}")
        async for message in stream:
            logger.debug("Received message type: %s", type(message).__name__)
            if isinstance(message, (ToolCallRequestEvent,
                                    ToolCallExecutionEvent, MemoryQueryEvent, UserInputRequestedEvent, ModelClientStreamingChunkEvent, ThoughtEvent)):
                continue
            elif isinstance(message, TaskResult):
                logger.info("Task result")
                last_result = message
            else:
                agent_name = message.source
                if agent_name == "user":
                    logger.info("User agent message")
                    continue
                if agent_name == "MagenticOneOrchestrator":
                    agent_name = self.name
                    logger.info("MagenticOneOrchestrator agent name")
                context = await self._get_bot_context(
                    conv_id, agent_name, turn_context
                )
                content = message.content if isinstance(message.content, str) else str(message.content)
                if content.strip() == "":
                    continue

                chat_ctx.chat_history.add_assistant_message(content, name=agent_name)

                activity = MessageFactory.text(content)
                activity.apply_conversation_reference(
                    turn_context.activity.get_conversation_reference()
                )
                context.activity = activity
                if self.include_monologue:
                    await context.send_activity(activity)

        if last_result:
            if not self.include_monologue:
                if chat_ctx.chat_history.messages:
                    last_content = chat_ctx.chat_history.messages[-1].content or ""
                    await turn_context.send_activity(
                        MessageFactory.text(last_content)
                    )

            if last_result.stop_reason:
                await turn_context.send_activity(
                    MessageFactory.text(last_result.stop_reason)
                )
