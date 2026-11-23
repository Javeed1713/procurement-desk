# Procurement Desk

Procurement Desk analyses supplier negotiation threads and decides, for each
thread, whether to ACCEPT, REJECT, COUNTER or ESCALATE the offer, following
the procurement playbook. The final output is a CSV with exactly 2,000 rows
in the format `thread_id,label`, where each label has the form
`ACTION:REASON:COUNTER_PRICE`.

## Team and Ownership

| Member | Area | Owned files |
|---|---|---|
| Member 1 | Policy engine | src/policy_engine.py, tests/test_policy.py |
| Member 2 | Message parser | src/message_parser.py, tests/test_parser.py |
| Member 3 | Security and decisions | src/security_checker.py, src/decision_engine.py, tests/test_security.py, tests/test_decisions.py |
| Member 4 | Integration | src/schemas.py, src/utils.py, notebooks/main.ipynb, tests/test_integration.py, README.md, requirements.txt, pytest.ini, .gitignore |

Each member edits only the files in their own row. If you need a change in a
file you do not own, message its owner.

## Data Policy

The competition dataset lives in the `data/` folder on each member's computer.
It is listed in `.gitignore` and must never be committed or published. Each
member copies the dataset locally from the official source.

## Setup (Windows PowerShell, from the project root)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Running the Tests

```powershell
python -m pytest -v
```

## Project Structure

The `src` folder holds the modules, `tests` holds the test files, `notebooks`
holds the Kaggle notebook, and `outputs` receives the generated submission.

## Status

The project is in Phase 3 (scaffolding). The modules contain stubs that raise
NotImplementedError until their owners implement them in Phase 4.
