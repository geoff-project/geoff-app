# Changelog

## Upcoming

### Visible changes

- Upgraded the LSA selector from a built-in version to the version provided by
  [AccWidgets](https://acc-py.web.cern.ch/gitlab/acc-co/accsoft/gui/accsoft-gui-pyqt-widgets/docs/stable/widgets/lsa_selector/index.html).
- Changed default LSA server from *next* to *gpn*.
- Made LSA server configurable on the command line: pass either `-sNAME` or
  `--lsa-server NAME`.

### Build changes

- Upgrade Python requirement to 3.7.
- Upgrade `accwidgets` requirement to 1.1.0 and only the widgets that are used.

## v0.0.6

### Visible changes

- The algorithms now log the optimization results. The level of the message
  depends on the result: successful optimization leaves an INFO entry, failed
  optimization either WARNING or ERROR.
- The initial step size of the BobyQA and COBYLA algorithms is now configurable
  in the GUI as "rhobeg".

## v0.0.5

### Visible changes

- Clicking the Reset button after running an optimization re-renders the
  optimization problem (i.e. calls `problem.render("matplotlib_figures")` if
  possible). This ensures that the user can see that the problem has indeed
  been reset.

## v0.0.4

### Bug fixes

- Unwrap the `Problem` when determining what kind of optimization job to start.
- Handle `render("matplotlib_figures")` returning a `Dict[str, Figure]`
  correctly.

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
