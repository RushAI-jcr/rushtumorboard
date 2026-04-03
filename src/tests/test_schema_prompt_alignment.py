"""Test that Pydantic model fields align with LLM prompt descriptions.

Prevents silent schema drift where a field is added to the Pydantic model
but the corresponding LLM prose prompt is not updated (or vice versa).
"""
import pytest

from data_models.tumor_board_summary import TumorBoardDocContent, SlideContent


def test_tumor_board_doc_fields_in_prompt():
    """Every TumorBoardDocContent field must appear in TUMOR_BOARD_DOC_PROMPT."""
    from scenarios.default.tools.content_export.content_export import TUMOR_BOARD_DOC_PROMPT

    for field_name in TumorBoardDocContent.model_fields:
        assert field_name in TUMOR_BOARD_DOC_PROMPT, (
            f"TumorBoardDocContent field '{field_name}' missing from TUMOR_BOARD_DOC_PROMPT — "
            f"add it to the prompt or remove it from the model"
        )


def test_slide_content_fields_in_prompt():
    """Every SlideContent field must appear in SLIDE_SUMMARIZATION_PROMPT."""
    from scenarios.default.tools.presentation_export import SLIDE_SUMMARIZATION_PROMPT

    for field_name in SlideContent.model_fields:
        assert field_name in SLIDE_SUMMARIZATION_PROMPT, (
            f"SlideContent field '{field_name}' missing from SLIDE_SUMMARIZATION_PROMPT — "
            f"add it to the prompt or remove it from the model"
        )
