# Rush GYN Oncology Tumor Board — FAQ

## Q: What is the Rush GYN Oncology Tumor Board system?
A: A multi-agent system that coordinates 10 specialized AI agents to support GYN Oncology Tumor Board case reviews at Rush University Medical Center. Built on Microsoft Semantic Kernel with Azure OpenAI (GPT-4o/4.1 + o3-mini), the system extracts, structures, and presents patient data from Epic Clarity/Caboodle in clinical shorthand format. Agents cover patient history, oncologic history, pathology, radiology, tumor markers, NCCN guidelines, clinical trials, medical research, and report generation.

## Q: How do I start a conversation with the agents?
A: In Microsoft Teams or the React chat UI, start a conversation by mentioning an agent's name followed by your question. For example:
- `@Orchestrator prepare tumor board for patient id patient_gyn_001`
- `@PatientHistory create patient timeline for patient id patient_gyn_001`

Always begin your message with the agent name using the @ mention format.

## Q: How do I clear the chat history and start over?
A: You can reset the conversation state by sending `@Orchestrator clear` in the chat. This will reset the conversation flow and allow you to start fresh.

## Q: What should I do if an agent stops responding during a long-running task?
A: It's a known issue that long-running task orchestration may be interrupted if you introduce another query while a task is running. To avoid this, wait for the current task to complete before making additional requests. If an agent becomes unresponsive, try clearing the chat with `@Orchestrator clear` and starting again.

## Q: What patient data is included in the project by default?
A: The project includes synthetic GYN oncology test cases (`patient_gyn_001`, `patient_gyn_002`) and a legacy generic case (`patient_4`) in the `infra/patient_data/` directory. Each patient folder contains Epic Caboodle CSV exports (clinical_notes.csv, lab_results.csv, pathology_reports.csv, radiology_reports.csv, cancer_staging.csv, medications.csv, diagnoses.csv). Real patient data (15 GUID-named folders from Rush) is present locally but gitignored. No PHI is committed to version control.

## Q: What external APIs does the system call?
A: The system queries public government and academic APIs for clinical decision support — all read-only, no PHI is sent:
- **ClinicalTrials.gov API v2** (NIH/NLM) — trial search and eligibility criteria
- **NCI Clinical Trials API** (National Cancer Institute) — cancer-specific trial data with biomarkers
- **PubMed E-utilities** (NIH/NLM) — medical literature search and abstracts
- **Europe PMC** (EMBL-EBI) — European biomedical literature
- **Semantic Scholar** (Allen Institute for AI) — citation graphs and paper metadata

## Q: What are the data source options?
A: Set the `CLINICAL_NOTES_SOURCE` environment variable:
- `caboodle` — local Epic Caboodle CSV files (default for development)
- `fhir` — Azure Health Data Services FHIR server
- `fabric` — Microsoft Fabric clinical note function
- `blob` — Azure Blob Storage (legacy JSON format)