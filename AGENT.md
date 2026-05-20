# Instructions for Codex Agents

You are building a scientific Python simulator.

Priorities:
1. Correct physical units.
2. Clear modular architecture.
3. Small testable functions.
4. Deterministic behavior with random seeds.
5. Good docstrings and type hints.
6. Do not over-engineer v0.

Use Python 3.11+.

Preferred libraries:
- numpy
- pandas
- pydantic or dataclasses
- matplotlib
- pytest
- pyyaml

Do not implement detailed Wi-Fi MAC/PHY in v0.
Do not implement Fresnel or human movement in v0.
Keep interfaces extensible for future versions.

Run before finishing:
- pytest
- python examples/run_v0.py