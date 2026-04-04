# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import os

from semantic_kernel.contents.chat_history import ChatHistory

from data_models.patient_demographics import PatientDemographics


class ChatContext:
    def __init__(self, conversation_id: str, request_date: str | None = None):
        self.conversation_id = conversation_id
        self.chat_history = ChatHistory()
        self._patient_id: str | None = None
        self.request_date = request_date  # ISO YYYY-MM-DD: date the report was requested
        self.patient_data = []
        self.patient_demographics: PatientDemographics | None = None
        self.display_blob_urls = []
        self.display_image_urls = []
        self.display_clinical_trials = []
        self.output_data = []
        self.root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.healthcare_agents = {}

    @property
    def patient_id(self) -> str | None:
        return self._patient_id

    @patient_id.setter
    def patient_id(self, value: str) -> None:
        if self._patient_id is not None and self._patient_id != value:
            raise ValueError(
                f"ChatContext: patient_id already set to {self._patient_id!r}; "
                f"refusing to overwrite with {value!r}. Each conversation must "
                f"be scoped to a single patient."
            )
        self._patient_id = value
