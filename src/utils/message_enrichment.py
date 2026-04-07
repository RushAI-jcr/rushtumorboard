"""Shared message enrichment for patient images, trial links, and blob SAS URLs.

Used by both the Teams bot (assistant_bot.py) and WebSocket handler (chats.py)
to ensure feature parity across delivery channels.
"""

import html

from data_models.chat_context import ChatContext
from data_models.data_access import DataAccess


def append_links(msg_text: str, chat_ctx: ChatContext) -> str:
    """Append patient image tags and clinical trial links to message text."""
    try:
        clinical_trial_urls = chat_ctx.display_clinical_trials

        # Display clinical trials
        if clinical_trial_urls:
            msg_text += "<h2>Clinical trials</h2><ul>"
            for url in clinical_trial_urls:
                safe_url = html.escape(url, quote=True)
                trial = html.escape(url.split("/")[-1])
                msg_text += f'<li><a href="{safe_url}">{trial}</a></li>'
            msg_text += "</ul>"

        return msg_text
    finally:
        chat_ctx.display_clinical_trials = []


async def apply_sas_urls(msg_text: str, chat_ctx: ChatContext, data_access: DataAccess) -> str:
    """Replace blob URLs with SAS-signed URLs for browser access."""
    try:
        for blob_url in chat_ctx.display_blob_urls:
            blob_sas_url = await data_access.blob_sas_delegate.get_blob_sas_url(blob_url)
            msg_text = msg_text.replace(blob_url, blob_sas_url)
        return msg_text
    finally:
        chat_ctx.display_blob_urls = []
