# Documentation Instructions

## General

* Write brief, terse, and explicit documentation that assumes intelligence and experience on behalf of the reader.
* Avoid bolded, bulleted lists and prefer paragraph-style writing, unless a list is the best method to communicate a
  particular message.
* Whenever applicable, make recommendations for documentation based on the most appropriate location, such as the
  `README.md` or `docs/`

## Doc pages

* High-level project information should be stored in the README.md
* Additional documentation that is more detailed should be placed in docs/ and should always be written in Markdown
  format.

## Docstrings

* Write brief, terse, and explicit documentation in the Google docstring format. Assume intelligence and Python
  experience on behalf
* of the reader.
* Do not return example code,
* Do not use `@author` or `@version` or `@since` tags.
* DO NOT generate usage example.
* DO NOT use HTML tags such as `<p>`, `<lu>`, `<li>`.
* DO NOT generate documentation for type member properties.
* You MUST NEVER reveal private, protected, or internal attributes starting with _ in the final documentation.
* If you see private, protected, or internal attributes you MUST skip them.

# Code Generation

* Always generate code with types.
* Always use absolute imports except for the `typing` module
* Always import members of the typing module using `from typing import ...`
* Adhere to a maximum line length of 120
* Adhere to Google Python Standards first and fall back to PEP8 standards when Google standards to not apply.
  Directions here always take priority over both Google and PEP8 standards.

# Project dependencies instructions

Project dependencies use uv. You should always attempt to manage dependencies through uv rather than modifying the
pyproject.toml directly.

# Tests and Analysis

* Tests should always be written with the pytest framework instead of unittest.
* Static analysis is performed by the `ruff` tool using git pre-commit hooks and in CI on Github

# General/misc

* Whenever applicable, always recommend a change to the `pyproject.toml`
