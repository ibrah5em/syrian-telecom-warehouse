"""
Telecom DW ETL package.

Layout:
    etl/
    ├── __init__.py        ← you are here
    ├── __main__.py        entrypoint (python -m etl)
    ├── config.py          env-based connection config
    ├── extract/           {syriatel,mtn}.py — read OLTPs
    ├── transform/         {customers,products,dates,sales}.py — clean & normalize
    ├── load/              {dims,facts}.py — UPSERT into DW
    ├── utils/             {logging,mappings}.py — shared helpers
    └── tests/             pytest smoke tests

Read .claude/skills/etl-patterns/SKILL.md before extending.
"""

__version__ = "0.1.0"
