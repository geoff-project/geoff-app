# Changelog

## v0.0.3

### Visible changes

- The LSA context selector now remembers the context per accelerator and always
  selects a context if one is available.
- Add a logging console to the GUI.
- Add function optimization to the GUI.
- Add skeleton-point selection to the configure-environment dialog.
- Show the exception in a message box if environment initialization or
  configuration fail.
- Remove command-line options `--quiet` and `--verbose`.
- Show a please-wait dialog during environment initialization.

### Build changes

- Upgrade `cernml-coi` requirement to 0.4.
- Upgrade `accwidgets` requirement to 1.0.1 and all widgets.
- Add dependency on `cernml-coi-funcs`.
- Enable JPype import hooks while executing foreign imports.
- Update installation guide to include Acc-Py Base 2020.11.

### Bug fixes

- Log caught exceptions via `logging` module.

## v0.0.2

### Build changes

- Upgrade build setup to use `pyproject.toml`.
- Make `accwidgets` requirement stricter (0.4.X instead of >=0.4).
- Fix conflicting test dependencies (Require PyTest as modern as required by
  PyTest-Mock).

## v0.0.1

- Initial release.
