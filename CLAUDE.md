# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands
- Run app: `python app.py`
- Run tests: `pytest tests/`
- Run single test: `pytest tests/test_file.py::test_function`
- Lint code: `flake8 .`
- Type check: `mypy .`

## Code Style Guidelines
- **Python**: Follow PEP 8 style guide
- **Imports**: Group standard library imports first, then third-party, then local
- **Formatting**: 4 spaces for indentation, 120 character line limit
- **Types**: Use type hints for function parameters and return values
- **Naming**: snake_case for variables/functions, CamelCase for classes
- **Error Handling**: Use try/except with specific exceptions, log all errors
- **Documentation**: Docstrings for all functions/classes using """triple quotes"""
- **Power Awareness**: Check battery/power status before heavy computation

## Project Structure
- Core code is in Python with SQLite for persistence
- Uses Flask for the web interface with static HTML generation
- Integration with hardware components via serial communication