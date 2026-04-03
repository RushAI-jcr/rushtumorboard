# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import asyncio
import json
import logging
import os
from typing import Any

import aiohttp
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai.prompt_execution_settings.azure_chat_prompt_execution_settings import \
    AzureChatPromptExecutionSettings
from semantic_kernel.connectors.ai.open_ai.services.azure_chat_completion import AzureChatCompletion
from semantic_kernel.contents.chat_history import ChatHistory
from semantic_kernel.functions import kernel_function

from data_models.app_context import AppContext
from data_models.chat_context import ChatContext
from data_models.plugin_configuration import PluginConfiguration

logger = logging.getLogger(__name__)
PROMPT = “””You are a gynecologic oncology clinical trial eligibility specialist. Analyze the structured patient data against the clinical trial eligibility criteria.

Respond with **”Yes”** if the patient likely meets eligibility, **”No”** if clearly ineligible, or **”Maybe — requires verification”** if borderline or data is missing.

Then provide a structured explanation:

**1. Key Inclusion Criteria — Match/Mismatch:**
Evaluate each of these critical GYN oncology trial enrollment factors against the trial criteria:
  - **Age**: Does the patient fall within the trial’s age range?
  - **FIGO Stage / Disease Extent**: Does the patient’s staging match the required stage(s)?
  - **Histology**: Does the trial require specific histologic types (e.g., serous only, endometrioid, clear cell, squamous)? Does the patient match?
  - **Biomarker / Molecular Requirements**: Does the trial require specific biomarker status (BRCA+, HRD+, MMR-deficient, PD-L1 CPS ≥1, HER2+, FRα+, POLE-mutated)? Does the patient qualify?
  - **Prior Lines of Therapy**: How many prior systemic regimens has the patient received? Does the trial specify a line (e.g., “1-3 prior lines”, “second-line or later”)?
  - **Platinum Sensitivity**: Does the trial require platinum-sensitive, platinum-resistant, or platinum-refractory disease? What is the patient’s platinum-free interval?
  - **ECOG Performance Status**: Does the patient’s ECOG (0, 1, 2) meet the trial requirement (most require 0-1)?
  - **Prior Specific Agents**: Does the trial exclude patients with prior PARP inhibitor, prior immunotherapy, prior bevacizumab, or prior specific agents? Has the patient received any of these?

**2. Key Exclusion Criteria — Flags:**
  - CNS metastases (many trials exclude active brain mets)
  - Organ function (renal, hepatic — if data available)
  - Autoimmune disease (relevant for immunotherapy trials)
  - Prior malignancy (second primary cancers within 3-5 years)
  - Specific comorbidities mentioned in the trial criteria

**3. Missing Data:**
List any patient data fields that are needed for a definitive eligibility determination but are not provided. Be specific (e.g., “BRCA status not provided — trial requires BRCA1/2 mutation”).

**4. Clinical Relevance:**
Briefly note why this trial may or may not be a good fit for this patient’s clinical situation beyond strict eligibility (e.g., “Patient is platinum-resistant with BRCA1 mutation — this PARP inhibitor trial is highly relevant”).

The treatment history provided in the structured patient attributes represents the patient’s complete treatment record. Do not assume additional treatments were given.
“””

CLINICAL_TRIALS_SEARCH_QUERY = """
You are a helpful assistant designed to generate free text search queries for ClinicalTrials.gov based on patient attributes. When given specific patient information, you will construct a query that maximizes the chances of finding relevant clinical trials.

**Instructions:**

1. Identify the key attributes of the patient's condition, including disease stage, primary site, histology, and biomarkers.
2. Construct a search query using free text that includes variations and synonyms for these attributes to ensure comprehensive search results.
3. Focus only on positive attributes. Ignore negative attributes such as negetive biomarkers.
4. Ensure the query is formatted to match terms that might appear in clinical trial descriptions.
5. Use logical operators (AND, OR) to combine different attributes effectively. Make sure the query conforms to the ESSIE expression syntax.

**Example:**

*Patient Attributes:*
- Staging: Likely stage IV disease
- Primary Site: Lung
- Histology: Non-small cell lung carcinoma, adenocarcinoma type
- Biomarkers: EGFR mutation, TP53 mutation, RTK mutation

*Generated Query:*
```
("stage IV" OR "stage 4" OR metastatic) AND "lung cancer" AND "non-small cell" AND "adenocarcinoma" AND (EGFR OR TP53 OR RTK)
```

Given the patient's attributes, generate a search query following the example above. Only output the query.
"""


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
            "biomarkers, histology, and staging. Call this before search_clinical_trials."
        )
    )
    async def generate_clinical_trial_search_criteria(self, biomarkers: list[str], histology: str, staging: str):
        """
        Generates a search query that can be used to call the clinical trial API on https://clinicaltrials.gov.

        Args:
            biomarkers (str): The biomarkers information of the patient.
            histology (str): The histology information of the patient.
            staging (str): The staging information of the patient.
        """
        chat_history = ChatHistory()
        chat_history.add_system_message(CLINICAL_TRIALS_SEARCH_QUERY)
        chat_history.add_user_message("Structured Patient Attributes: \ndata= " +
                                      json.dumps({
                                          'biomarkers': biomarkers,
                                          'histology': histology,
                                          'staging': staging,
                                      }, indent=4))

        chat_completion_response = await self.chat_completion_service.get_chat_message_content(
            chat_history=chat_history, settings=AzureChatPromptExecutionSettings())
        logger.debug("Generated search query: %s", chat_completion_response)
        return str(chat_completion_response)

    @kernel_function(
        description=(
            "Search ClinicalTrials.gov for recruiting trials matching the patient's eligibility criteria. "
            "Evaluates each trial against patient data and returns Yes/No eligibility with explanation. "
            "Call generate_clinical_trial_search_criteria first to get the query string."
        )
    )
    async def search_clinical_trials(self, clinical_trials_query: str, age: str, biomarkers: list[str], histology: str, staging: str, ecog_performance_status: str, first_line_treatment: str, second_line_treatment: str) -> str:
        """
        Asynchronously searches for clinical trials based on patient data and returns a response for each trial, indicating Yes/No if the patient meets all eligibility criteria. Additionally provides an exaplanation as to why.

        Args:
            clinical_trials_query(str): The search query for clinical trials.
            age(str): The age of the patient.
            biomarkers(str): The biomarkers information of the patient.
            histology(str): The histology information of the patient.
            staging(str): The staging information of the patient.
            ecog_performance_status(str): The ECOG performance status of the patient.
            first_line_treatment(str): The first line treatment information of the patient.
            second_line_treatment(str): The second line treatment information of the patient.

        Returns:
            str: A JSON string containing the responses for each clinical trial.
        """
        structured_patient_data = {
            'biomarkers': biomarkers,
            'histology': histology,
            'staging': staging,
            'ecog performance status': ecog_performance_status,
            'first line treatment': first_line_treatment,
            'second line treatment': second_line_treatment,
            'age': age,
        }

        params = {
            "query.term": clinical_trials_query,
            "pageSize": 15,
            "filter.overallStatus": "RECRUITING",
            "fields": "ConditionsModule|EligibilityModule|IdentificationModule"
        }
        async with aiohttp.ClientSession() as session:
            async with session.get("https://clinicaltrials.gov/api/v2/studies", params=params) as resp:
                resp.raise_for_status()
                result = await resp.json()

        study_count = len(result["studies"])
        logger.info("Clinical trials found: %d", study_count)

        _sem = asyncio.Semaphore(5)
        _trial_timeout = 45.0

        async def _evaluate_one(trial: dict) -> object | None:
            async with _sem:
                ch = ChatHistory()
                ch.add_system_message(PROMPT)
                ch.add_user_message(
                    "Structured Patient Attributes: \ndata= "
                    + json.dumps(structured_patient_data, indent=4)
                )
                ch.add_user_message(
                    "Clinical Trial Eligibility Criteria:\n" + json.dumps(trial, indent=4)
                )
                try:
                    return await asyncio.wait_for(
                        self.chat_completion_service.get_chat_message_content(
                            chat_history=ch,
                            settings=AzureChatPromptExecutionSettings(temperature=0),
                        ),
                        timeout=_trial_timeout,
                    )
                except (asyncio.TimeoutError, Exception) as exc:
                    nct = (
                        trial.get("protocolSection", {})
                        .get("identificationModule", {})
                        .get("nctId", "unknown")
                    )
                    logger.warning("Trial evaluation failed for %s: %s", nct, type(exc).__name__)
                    return None

        chat_completion_responses = await asyncio.gather(
            *[_evaluate_one(t) for t in result["studies"]],
            return_exceptions=True,
        )

        trial_dict_results = {}
        for trial, response_result in zip(result["studies"], chat_completion_responses):
            if response_result is None or isinstance(response_result, BaseException):
                continue
            nct_id = trial["protocolSection"]["identificationModule"]["nctId"]
            trial_dict_results[nct_id] = {
                "eligibility": str(response_result),
                "title": trial["protocolSection"]["identificationModule"]["briefTitle"],
            }

        return json.dumps(trial_dict_results, indent=4)

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

        import re as _re
        nct_id = trial.strip().upper()
        if not _re.fullmatch(r"NCT\d{8,11}", nct_id):
            return json.dumps({"error": f"Invalid NCT ID format: {trial!r}. Expected NCTxxxxxxxx."})

        async with aiohttp.ClientSession() as session:
            async with session.get(self.clinical_trial_url + nct_id) as resp:
                resp.raise_for_status()
                result = await resp.json()

        chat_history = ChatHistory()
        chat_history.add_system_message("You are a clinical trial summarizer. Summarize the provided trial information, focusing on what is relevant for an oncologist or patient.")
        chat_history.add_user_message(
            "Summarize the following clinical trial:\n" + json.dumps(result, indent=4)
        )

        settings = AzureChatPromptExecutionSettings(temperature=0)
        chat_completion_response = await self.chat_completion_service.get_chat_message_content(
            chat_history=chat_history, settings=settings)
        self.chat_ctx.display_clinical_trials.append(
            self.clinical_trial_display + trial)
        return str(chat_completion_response)
