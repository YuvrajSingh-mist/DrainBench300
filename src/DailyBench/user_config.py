"""User configuration for the parameterized benchmark.

The benchmark is meant to be usable by anyone, not just the original author's
persona. Every task prompt placeholder (``[contact]``), every ASK USER fact
(``{contact_b}``), and every fabricated seed value that names a concrete
person / place / thing is resolved from ONE flat user config:
``config/user.yaml`` (seeded from the committed ``config/user_config.example``).

Key naming:
- Keys that match a prompt placeholder (e.g. ``contact``, ``food_category``,
  ``stock name``) fill that placeholder directly.
- Fact/seed-only keys (``contact_b``, ``destination``, ``item``,
  ``stock note title``, ``stock threshold``, ...) are used by ASK USER fact
  templates (``{...}``) and by the seed generator/seed scripts.

A missing key fails loudly (exception / verifier report) instead of silently
guessing, so a new user gets "you still need to fill X" rather than a silent
wrong-value run.

No third-party deps: the flat config is parsed with a tiny line parser that
accepts both ``key: value`` and ``key=value`` forms, ignoring blank lines and
``#`` comments (so a YAML- or dotenv-flavoured file both work).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "user.yaml"

# ---------------------------------------------------------------------------
# Schema: key -> (description, example). Drives user_config.example generation
# and the completeness verifier's "you still need to fill X" messages.
# ---------------------------------------------------------------------------
SCHEMA: dict[str, tuple[str, str]] = {
    # people
    "contact": ("The person the agent messages/forwards to for any `[contact]` task "
                "(safe self-target on the test device).", "Yuvraj Airtel"),
    "contact_b": ("The person the ASK USER facts mean when they say 'message the person "
                  "I usually ask' (`{contact_b}` in facts).", "Yuvraj Singh Jio"),
    "contact name": ("Contact to look up in the Contacts search task (`[contact name]`).", "Maa"),
    "sender": ("Gmail sender for the 'unread emails from [sender]' tasks (`[sender]`).", "Myntra"),
    "letter": ("Letter used by the 'contacts starting with [letter]' task.", "Y"),
    # location
    "destination": ("Train-departure ASK USER fact destination (`{destination}`).", "Cuttack"),
    "place": ("Maps/weather target place near the device (`[place]`).", "Bhubaneswar Airport"),
    # stock tracker (hard task #57)
    "stock name": ("Stock ticker/company the agent tracks (`[stock name]`).", "Reliance Industries"),
    "stock note title": ("Title of the Obsidian note holding the threshold + last value "
                         "(`[stock note title]`).", "Stock Watch"),
    "stock threshold": ("Value the stock must cross to trigger a message (seed value).", "1,400 INR"),
    "stock last value": ("Last recorded value in the stock note (seed value).", "1,385 INR"),
    # notes
    "meeting folder": ("Obsidian folder where the reschedule/confirm log is saved "
                       "(`[meeting folder]`).", "Meeting Notes"),
    "news note title": ("Base title for the 'Open Source Model News' note "
                        "(`[news note title]`, a date is appended at run time).", "Open Source Model News"),
    "note title": ("Title for the Notes/Obsidian create-note tasks (`[note title]`).", "Daily Reflection"),
    # shopping
    "shopping_website_1": ("First shopping site for the price-comparison task.", "amazon.in"),
    "shopping_website_2": ("Second shopping site for the price-comparison task.", "flipkart.com"),
    "item": ("The item being shopped for, revealed by the ASK USER fact (`{item}`).", "wireless earbuds"),
    # media
    "food_category": ("Photo category for the Gallery 'best 3 by resolution' task "
                      "(`[food_category]`).", "pizza"),
    "search word": ("Word to search Messages for (`[search word]`).", "ticket"),
    # misc
    "topic": ("Generic research topic used by several search tasks (`[topic]`).", "best budget smartphones 2026"),
    "article url": ("URL for the Chrome summarize-article task (`[article url]`).", "https://en.wikipedia.org/wiki/Open-source_software"),
    "currency pair": ("Exchange-rate pair for the Google Search task (`[currency pair]`).", "USD to INR"),
    "digits": ("Digit prefix for the Phone call-history filter task (`[digits]`).", "98765"),
}

DEFAULT_CONFIG: dict[str, str] = {k: example for k, (_, example) in SCHEMA.items()}


def parse_flat_config(text: str) -> dict[str, str]:
    """Parse a flat ``key: value`` / ``key=value`` config, ignoring comments/blanks."""
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # first unquoted ':' or '=' separates key and value; take the leftmost
        m = re.match(r"^([^:=]+?)\s*[:=]\s*(.*)$", line)
        if not m:
            continue
        key = m.group(1).strip()
        val = m.group(2).strip()
        # strip a trailing inline comment ("key=value # note"), but only when '#'
        # is preceded by whitespace so a value that legitimately contains '#' (e.g.
        # a URL fragment like https://x/y#section) is left untouched.
        val = re.sub(r"\s+#.*$", "", val).strip()
        # strip surrounding quotes
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        out[key] = val
    return out


def load_user_config(path: str | Path | None = None) -> dict[str, str]:
    """Load config/user.yaml (or the given path), merged over the shipped defaults.

    Missing file -> defaults only, so the benchmark runs out of the box with the
    example persona values.
    """
    cfg_path = Path(path) if path else DEFAULT_CONFIG_PATH
    cfg = dict(DEFAULT_CONFIG)
    if cfg_path.exists():
        cfg.update(parse_flat_config(cfg_path.read_text(encoding="utf-8")))
    return cfg


_TEMPLATE_RE = re.compile(r"\{([^{}]+)\}")


def template_keys(template: str) -> list[str]:
    """Return the ``{key}`` names referenced by a template string."""
    return _TEMPLATE_RE.findall(template)


def resolve_template(template: str, cfg: dict[str, str]) -> str:
    """Replace every ``{key}`` in a template with cfg[key].

    Raises KeyError naming exactly which key is missing, so a new user sees
    'you still need to fill X' instead of a silent blank.
    """
    missing = [k for k in template_keys(template) if k not in cfg]
    if missing:
        raise KeyError(f"config is missing value(s) needed by template {template!r}: "
                       + ", ".join(f"{k!r} (see config/user_config.example)" for k in sorted(set(missing))))
    return _TEMPLATE_RE.sub(lambda m: cfg[m.group(1)], template)


def resolve_templates(obj, cfg: dict[str, str]):
    """Recursively resolve ``{key}`` templates in strings inside nested dicts/lists."""
    if isinstance(obj, str):
        if "{" in obj:
            return resolve_template(obj, cfg)
        return obj
    if isinstance(obj, dict):
        return {k: resolve_templates(v, cfg) for k, v in obj.items()}
    if isinstance(obj, list):
        return [resolve_templates(v, cfg) for v in obj]
    return obj


def var_map(config: dict[str, str], cli_vars: dict[str, str] | None = None,
            vars_file: dict[str, str] | None = None) -> dict[str, str]:
    """Build the placeholder -> value map for prompt rendering.

    Precedence (low -> high): shipped defaults (already merged into `config`),
    then a per-day vars file, then explicit CLI --var flags.
    """
    merged = dict(config)          # config keys are the baseline (incl. defaults)
    if vars_file:
        merged.update(vars_file)
    if cli_vars:
        merged.update(cli_vars)
    return merged
