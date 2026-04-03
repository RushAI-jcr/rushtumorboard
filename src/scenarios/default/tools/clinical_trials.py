# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import asyncio
import json
import logging
import os
import re
from typing import Any

import aiohttp
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai.prompt_execution_settings.azure_chat_prompt_execution_settings import \
    AzureChatPromptExecutionSettings
from semantic_kernel.connectors.ai.open_ai.services.azure_chat_completion import AzureChatCompletion
from semantic_kernel.contents.chat_history import ChatHistory
from semantic_kernel.contents.chat_message_content import ChatMessageContent
from semantic_kernel.functions import kernel_function

from data_models.app_context import AppContext
from data_models.chat_context import ChatContext
from data_models.gyn_patient_profile import GynPatientProfile
from data_models.plugin_configuration import PluginConfiguration

logger = logging.getLogger(__name__)

# --- Constants for PHI safety ---
_PHI_SCRUB_PATTERNS = [
    re.compile(r'\b\d{1,2}/\d{1,2}/\d{2,4}\b'),   # date patterns (M/D/YY, MM/DD/YYYY)
    re.compile(r'\b\d{7,}\b'),                       # MRN-like long numbers
]
_TRIAL_EVAL_TIMEOUT = float(os.environ.get("CLINICAL_TRIAL_EVAL_TIMEOUT", "90"))


def _load_prompt(filename: str) -> str:
    """Load a prompt template from the config/prompts/ directory."""
    prompts_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config", "prompts",
    )
    filepath = os.path.join(prompts_dir, filename)
    with open(filepath, encoding="utf-8") as f:
        return f.read()


# Prompts loaded at module import from external files (separates clinical knowledge from code)
PROMPT = _load_prompt("clinical_trials_eligibility.txt")
CLINICAL_TRIALS_SEARCH_QUERY = _load_prompt("clinical_trials_search_query.txt")


def _scrub_phi(query: str) -> str:
    """Remove potential PHI patterns from an LLM-generated search query before sending to external API."""
    scrubbed = query
    for pattern in _PHI_SCRUB_PATTERNS:
        scrubbed = pattern.sub('', scrubbed)
    return scrubbed.strip()


def create_plugin(plugin_config: PluginConfiguration) -> "ClinicalTrialsPlugin":
    return ClinicalTrialsPlugin(
        plugin_config.kernel,
        chat_ctx=plugin_config.chat_ctx,
        app_ctx=plugin_config.app_ctx
    )


class ClinicalTrialsPlugin:
    def __init__(self, kernel: Kernel, chat_ctx: ChatContext, app_ctx: AppContext):
        self.root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.kernel = kernel
        self.clinical_trial_url = "https://clinicaltrials.gov/api/v2/studies/"
        self.clinical_trial_display = "https://clinicaltrials.gov/study/"
        self.chat_ctx = chat_ctx
        self.app_ctx = app_ctx

        # Clinical trial matching works better with a reasoning model (gpt-5.4 or o3)
        _reasoning_deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME_REASONING_MODEL")
        _reasoning_endpoint = os.environ.get("AZURE_OPENAI_REASONING_MODEL_ENDPOINT")
        if not _reasoning_deployment:
            raise ValueError(
                "ClinicalTrialsPlugin requires AZURE_OPENAI_DEPLOYMENT_NAME_REASONING_MODEL. "
                "Set it to the Azure OpenAI reasoning model deployment name (e.g. 'o3-mini')."
            )
        if not _reasoning_endpoint:
            raise ValueError(
                "ClinicalTrialsPlugin requires AZURE_OPENAI_REASONING_MODEL_ENDPOINT. "
                "Set it to the Azure OpenAI reasoning model endpoint URL."
            )
        reasoning_kwargs: dict[str, Any] = {
            "service_id": "reasoning-model",
            "deployment_name": _reasoning_deployment,
            "api_version": os.environ.get("AZURE_OPENAI_API_VERSION", "2025-04-01-preview"),
            "endpoint": _reasoning_endpoint,
        }
        api_key = os.environ.get("AZURE_OPENAI_API_KEY")
        if api_key:
            reasoning_kwargs["api_key"] = api_key
        else:
            reasoning_kwargs["ad_token_provider"] = self.app_ctx.cognitive_services_token_provider
        self.chat_completion_service = AzureChatCompletion(**reasoning_kwargs)

    @kernel_function(
        description=(
            "Generate a structured free-text search query for ClinicalTrials.gov based on the patient's "
            "GYN cancer profile. Call this before search_clinical_trials to get the query string. "
            "Pass the patient_profile with at least primary_site, histology, figo_stage, and biomarkers."
        )
    )
    async def generate_clinical_trial_search_criteria(
        self,
        patient_profile: GynPatientProfile,
    ) -> str:
        """
        Generates a search query for ClinicalTrials.gov tailored to the patient's GYN cancer profile.

        Args:
            patient_profile: The patient's full GYN oncology clinical profile including primary_site,
                histology, figo_stage, biomarkers, and optionally platinum_sensitivity,
                current_disease_status, and prior_therapies for more targeted searches.
        """
        chat_history = ChatHistory()
        chat_history.add_system_message(CLINICAL_TRIALS_SEARCH_QUERY)
        chat_history.add_user_message(
            "Structured Patient Attributes: \ndata= "
            + json.dumps(patient_profile.to_search_dict(), indent=2)
        )

        chat_completion_response = await self.chat_completion_service.get_chat_message_content(
            chat_history=chat_history, settings=AzureChatPromptExecutionSettings())
        logger.debug("Generated search query length: %d", len(str(chat_completion_response)))
        return str(chat_completion_response)

    @kernel_function(
        description=(
            "Search ClinicalTrials.gov for recruiting trials matching the patient's full clinical profile. "
            "Evaluates each trial against comprehensive patient data (age, stage, histology, biomarkers, "
            "prior therapies, platinum sensitivity, ECOG, comorbidities) and returns eligibility assessment. "
            "Call generate_clinical_trial_search_criteria first to get the query string. "
            "Pass the complete patient_profile with all available clinical fields for best results."
        )
    )
    async def search_clinical_trials(
        self,
        clinical_trials_query: str,
        patient_profile: GynPatientProfile,
    ) -> str:
        """
        Searches ClinicalTrials.gov and evaluates each trial's eligibility criteria against
        the patient's complete clinical profile. Returns Yes/No/Maybe for each trial with
        a structured explanation of matching and mismatching criteria.

        Args:
            clinical_trials_query: The ESSIE search query (from generate_clinical_trial_search_criteria).
            patient_profile: The patient's full GYN oncology clinical profile. Include all available
                fields -- age, primary_site, histology, figo_stage, biomarkers, ecog_performance_status,
                prior_therapies are required. platinum_sensitivity, molecular_profile, comorbidities,
                organ_function_labs, measurable_disease, ascites, cns_metastases improve accuracy.

        Returns:
            str: A JSON string containing eligibility assessments for each clinical trial.
        """
        structured_patient_data = patient_profile.to_prompt_dict()

        # Scrub potential PHI from LLM-generated query before sending to external API
        scrubbed_query = _scrub_phi(clinical_trials_query)

        params = {
            "query.term": scrubbed_query,
            "pageSize": 15,
            "filter.overallStatus": "RECRUITING",
            "fields": "ConditionsModule|EligibilityModule|IdentificationModule"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.clinical_trial_url, params=params) as resp:
                    resp.raise_for_status()
                    result = await resp.json()
        except aiohttp.ClientResponseError as e:
            logger.error("ClinicalTrials.gov API error: HTTP %d", e.status)
            return json.dumps({"error": "Clinical trials search temporarily unavailable."})
        except aiohttp.ClientError as e:
            logger.error("ClinicalTrials.gov connection error: %s", type(e).__name__)
            return json.dumps({"error": "Clinical trials search temporarily unavailable."})

        studies = result.get("studies", [])
        study_count = len(studies)
        logger.info("Clinical trials found: %d", study_count)

        _sem = asyncio.Semaphore(5)

        async def _evaluate_one(trial: dict) -> ChatMessageContent | None:
            nct = (
                trial.get("protocolSection", {})
                .get("identificationModule", {})
                .get("nctId", "unknown")
            )
            async with _sem:
                ch = ChatHistory()
                ch.add_system_message(PROMPT)
                ch.add_user_message(
                    "<PATIENT_DATA>\n"
                    + json.dumps(structured_patient_data, indent=2)
                    + "\n</PATIENT_DATA>"
                )
                # Extract only eligibility-relevant fields to reduce token usage
                elig = trial.get("protocolSection", {}).get("eligibilityModule", {})
                trial_for_eval = {
                    "nctId": nct,
                    "briefTitle": (
                        trial.get("protocolSection", {})
                        .get("identificationModule", {})
                        .get("briefTitle", "")
                    ),
                    "eligibilityCriteria": elig.get("eligibilityCriteria", ""),
                    "minimumAge": elig.get("minimumAge", ""),
                    "maximumAge": elig.get("maximumAge", ""),
                    "sex": elig.get("sex", ""),
                }
                ch.add_user_message(
                    "Clinical Trial Eligibility Criteria:\n" + json.dumps(trial_for_eval, indent=2)
                )
                try:
                    return await asyncio.wait_for(
                        self.chat_completion_service.get_chat_message_content(
                            chat_history=ch,
                            settings=AzureChatPromptExecutionSettings(),
                        ),
                        timeout=_TRIAL_EVAL_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    logger.warning("Trial evaluation timed out for %s (%.0fs)", nct, _TRIAL_EVAL_TIMEOUT)
                    return None
                except Exception as exc:
                    logger.error("Trial evaluation failed for %s: %s: %s", nct, type(exc).__name__, str(exc)[:200])
                    return None

        chat_completion_responses = await asyncio.gather(
            *[_evaluate_one(t) for t in studies],
        )

        trial_dict_results = {}
        for trial, response_result in zip(studies, chat_completion_responses):
            nct_id = (
                trial.get("protocolSection", {})
                .get("identificationModule", {})
                .get("nctId", "unknown")
            )
            title = (
                trial.get("protocolSection", {})
                .get("identificationModule", {})
                .get("briefTitle", "")
            )
            if response_result is None:
                trial_dict_results[nct_id] = {
                    "eligibility": "Evaluation timed out or failed -- manual review needed",
                    "title": title,
                }
            elif isinstance(response_result, BaseException):
                trial_dict_results[nct_id] = {
                    "eligibility": "Evaluation error -- manual review needed",
                    "title": title,
                }
            else:
                trial_dict_results[nct_id] = {
                    "eligibility": str(response_result),
                    "title": title,
                }

        return json.dumps(trial_dict_results, indent=2)

    @kernel_function(
        description=(
            "Retrieve and summarize detailed eligibility criteria and protocol information for a specific "
            "clinical trial by NCT ID (e.g., 'NCT12345678'). Use after search_clinical_trials identifies a trial of interest."
        )
    )
    async def display_more_information_about_a_trial(self, trial: str) -> str:
        """
        Fetches and displays more information about a specific clinical trial.
        This method retrieves detailed information about a specified clinical trial.

        Args:
            trial(str): The identifier of the clinical trial to fetch information for .
        Returns:
            str: A summary of the clinical trial information.
        """
        nct_id = trial.strip().upper()
        if not re.fullmatch(r"NCT\d{8}", nct_id):
            return json.dumps({"error": f"Invalid NCT ID format: {trial!r}. Expected NCTxxxxxxxx (8 digits)."})

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.clinical_trial_url + nct_id) as resp:
                    resp.raise_for_status()
                    result = await resp.json()
        except aiohttp.ClientResponseError as e:
            logger.error("ClinicalTrials.gov API error for %s: HTTP %d", nct_id, e.status)
            return json.dumps({"error": f"Could not retrieve trial {nct_id}."})
        except aiohttp.ClientError as e:
            logger.error("ClinicalTrials.gov connection error for %s: %s", nct_id, type(e).__name__)
            return json.dumps({"error": f"Could not retrieve trial {nct_id}."})

        chat_history = ChatHistory()
        chat_history.add_system_message("You are a clinical trial summarizer. Summarize the provided trial information, focusing on what is relevant for an oncologist or patient.")
        chat_history.add_user_message(
            "Summarize the following clinical trial:\n" + json.dumps(result, indent=2)
        )

        chat_completion_response = await self.chat_completion_service.get_chat_message_content(
            chat_history=chat_history, settings=AzureChatPromptExecutionSettings())
        self.chat_ctx.display_clinical_trials.append(
            self.clinical_trial_display + trial)
        return str(chat_completion_response)
