# Contributing to Rush GYN Oncology Tumor Board

## Code of Conduct

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).

## PHI and Patient Data

**This is a healthcare system handling real patient data. HIPAA compliance is non-negotiable.**

- Never commit real patient GUIDs, MRNs, or clinical data to version control
- Real patient data lives in `infra/patient_data/<UUID>/` (gitignored)
- Test with synthetic patients: `patient_gyn_001`, `patient_gyn_002`
- For real patient testing, use `src/tests/local_patient_ids.json` (gitignored) or the `TEST_PATIENT_GUIDS` env var
- Never log patient content at INFO level or above — use DEBUG with metadata only
- The pre-commit hook blocks commits containing known patient GUIDs

## Local Development

### Prerequisites

- Python 3.12+
- Node.js 18+ (for PptxGenJS PowerPoint generation)
- Azure OpenAI credentials

### Setup

```sh
# Clone and configure
git clone https://github.com/RushAI-jcr/rushtumorboard.git
cd rushtumorboard

# Install PHI pre-commit hook
bash scripts/install-hooks.sh

# Python environment
cd src
cp .env.sample .env
# Fill in Azure OpenAI credentials in .env
pip3 install -r requirements.txt

# Run tests with synthetic patient
SCENARIO=default CLINICAL_NOTES_SOURCE=caboodle python3 -m pytest tests/test_local_agents.py -v
```

### Running locally

```sh
cd src
SCENARIO=default CLINICAL_NOTES_SOURCE=caboodle python3 app.py
```

## Commit Conventions

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add cervical cancer NCCN guidelines
fix: prevent thread message duplication in group chat
refactor: extract _is_tool_message helper
docs: update data access layer documentation
```

**Types:** `feat`, `fix`, `refactor`, `docs`, `test`, `ci`, `chore`

## Pull Request Workflow

1. Create a feature branch from `main`
2. Make changes and test locally
3. Ensure the pre-commit hook passes (PHI scan)
4. Push and open a PR using the template
5. All PRs require PHI checklist completion
6. If agent behavior changes, run `scripts/run_batch_e2e.py` with at least 2 synthetic patients

## Testing

| Test | Command | When |
|------|---------|------|
| Unit tests | `python3 -m pytest tests/test_local_agents.py -v` | Every PR |
| Schema alignment | `python3 -m pytest tests/test_schema_alignment.py -v` | Data model changes |
| Batch E2E (synthetic) | `python3 scripts/run_batch_e2e.py --patients patient_gyn_001,patient_gyn_002` | Agent logic changes |
| Batch E2E (full) | `python3 scripts/run_batch_e2e.py` | Before release |
| CSV validation | `python3 scripts/validate_patient_csvs.py` | New patient data |

## Project Structure

See [CLAUDE.md](./CLAUDE.md) for the full directory layout and agent architecture.

## Reporting Issues

- Search [existing issues](https://github.com/RushAI-jcr/rushtumorboard/issues) first
- Use the bug report or feature request templates
- For security vulnerabilities, see [SECURITY.md](./SECURITY.md)
- Never include real patient data in issue descriptions

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](./LICENSE).
