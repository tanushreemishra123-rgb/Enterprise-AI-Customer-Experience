# Starter solution entry point

The supplied starter has been extended into the modular `cx` package. From the project root run the mock service and app using the commands in the root README. The web UI is in `ui/`; core workflow modules are `cx/engine.py`, `cx/ai.py`, `cx/security.py`, `cx/enterprise.py`, and `cx/telemetry.py`.

Reviewer mode is the default and requires no Gemini credentials. Install the single runtime dependency (`defusedxml`, listed in the root `requirements.txt`) from the project root before starting the app. Run the eight mandatory scenarios with `python starter-solution/eval/run_scenarios.py`. Run the unit/integration tests with `python -m unittest discover -s starter-solution/tests -v`.
