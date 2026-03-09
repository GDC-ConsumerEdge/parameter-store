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
* Adhere to Google Python Standards first and fall back to PEP8 standards when Google standards do not apply.
  Directions here always take priority over both Google and PEP8 standards.

# Project dependencies instructions

Project dependencies use uv.

* You should always attempt to manage dependencies through uv rather than modifying the
  pyproject.toml directly.
* Always use the 'uv' command runner for managing dependencies and running commands within projects, especially new
  ones. For example, instead of 'python -m myapp', use 'uv run myapp'.

# Tests and Analysis

* Tests should always be written with the pytest framework instead of unittest. ALWAYS run `pytest` with verbosity
  before comitting.
* Static analysis is performed by the `ruff` tool using git pre-commit hooks and in CI on Github
* ALWAYS run `ruff check --fix` and `ruff format` as a final step before committing.

# General/misc

* Whenever applicable, always recommend a change to the `pyproject.toml`

## Agent Instructions

In this project, you will ALWAYS adhere to the following guidelines:

* ALWAYS recommend changes to `README.md` for every change you perform.
* ALWAYS Add docstrings in the Google format.
* ALWAYS Add comments inline ONLY where the use case is not obvious.
* Avoid bolded, bulleted lists.  Use bulleted lists ONLY where it is the best way to convey information.
* ALWAYS use `# TODO:` style notes for interim implementations that should be addressed later.
* ALWAYS generate commits using the conventional commit format.
