# Changelog

## Unreleased

### Visible changes

- Only print message about skeleton points when configuring FunctionOptimizable
  problems.
- Replace load-file button for RL agent execution with a widget that displays
  the full path of the file.
- Support file paths in Configurable interface.
- Add context category filter menu to the LSA selector. This allows the user to
  display and choose non-operational contexts.
- Add `--version` command-line option.

### Bug fixes

- Add ISOLDE support.
- Avoid using JAPC selectors for machine A when instantiating an optimization
  problem for machine B.

## v0.1.5

### Visible changes

- Always attempt a location-based RBAC login at startup.
- Restyle built-in graphs of optimization/training progress.
- Make the accelerator-selection box a little less janky.
- Add Nelder–Mead algorithm for single-objective optimization.
- Add Powell's method for single-objective optimization.

## v0.1.4

### Visible changes

- Much improved cancellation support. Compatible environments are now able to
  be stopped in the middle of an optimization step.

### Build changes

This upgrades cernml-coi to 0.7.0, which is a backwards-incompatible change.
Consequently, all dependent packages are upgraded as well:

- Upgrade cernml-coi requirement to 0.7.0.
- Upgrade cernml-coi-funcs requirement to 0.2.1.
- Upgrade cern-awake-env requirement to 0.15.0.
- Upgrade cern-leir-transfer-line-env requirement to 0.2.0.
- Upgrade cern-sps-tune-env requirement to 0.2.1.
- Upgrade cern-sps-zs-alignment-env requirement to 0.2.0.

## v0.1.3

### Visible changes

- Add [Singular Value Decomposition
  (SVD)](https://gitlab.cern.ch/be-op-ml-optimization/cernml-svd/) as an RL
  algorithm. It works best on linear problems that can be described by an
  invertible response matrix. Thanks to @ivojskov for the implementation!
- Update the simulated AWAKE electron beam steering problem. It now provides a
  new version v1, which does not include the first BPM (which cannot be
  influenced) nor the last kicker (whose effect cannot be observed). This
  removal makes the problem's response matrix invertible and thus compatible
  with SVD.

### Build changes

- Upgrade `cern-awake-env` requirement to 0.14.0.
- Upgrade `cern-coi` requirement to 0.6.2.
- Upgrade `cernml-coi` to 0.6.2. This enables `"cern.cancellable"`.

## v0.1.2

### Build changes

- Upgrade `cern-leir-transfer-line-env` requirement to 0.1.1.

## v0.1.1

### Visible changes

- Add CLI argument `--no-capture-stdout` for debugging purposes.
- Add CLI argument `--japc-no-set` for debugging purposes.
- Add a window title which shows the values of `--server` and `--japc-no-set`.

### Bug fixes

- Catch more plugin exceptions and log them instead of crashing.

## v0.1.0

### Visible changes

- Add initial, extremely fragile implementation of reinforcement learning (RL)
  via [Stable Baselines 3](https://stable-baselines3.readthedocs.io/).
- Add more built-in optimization problems:
    - [SPS ZS Alignment](https://gitlab.cern.ch/be-op-ml-optimization/envs/sps-zs-alignment),
    - [SPS Tune](https://gitlab.cern.ch/be-op-ml-optimization/envs/sps-tune/),
    - [LEIR Transfer Line](https://gitlab.cern.ch/be-op-ml-optimization/envs/leir-transfer-line).
- Add argument `--no-builtins` to start the app without loading the built-in
  optimization problems. In this case, all optimization problems must be
  provided as foreign imports. This mode is best used for debugging.
- Logging messages are no longer printed to standard output nor standard error.
  Instead, the app captures its out standard output/error and redirects them to
  its log console widget.

### Build changes

- Add dependency on Stable Baselines 3 and, transitively, on PyTorch.
- Complete rewrite of GUI code: drop Qt Designer and use hand-written PyQt5
  code instead.

### Bug fixes

- Integer spinboxes in configuration dialogs no longer clip their initial
  values into the range from 0 to 99 inclusive.
- Foreign imports now can import packages from inside zip and wheel files. To
  do so, treat the file as if it were a directory:
  `path/to/archive.zip/package::child_module`.

## v0.0.9

### Visible changes

- When a `coi.Problem` implements the `close()` method, the app now correctly
  calls it before switching to another problem. It also finalizes the `PyJapc`
  object before creating a new one. This behavior is currently not guaranteed
  when the app is *exiting*.
- Matplotlib-based plots (i.e. those created inside `coi.Problem.render()`) now
  are decorated with the navigation toolbar known from interactive Matplotlib
  usage. Each figure is given its own individual toolbar.

### Build changes

- Upgrade `cernml-coi` requirement to 0.6.
- Upgrade `cerml-coi-funcs` requirement to 0.1.1.

### Bug fixes

- Relax the requirement on Gym from `>=0.17, <0.18` to `>=0.17`.
- The new LSA selector introduced in [v0.0.7](#v007) no longer selected an LSA
  context by default. This would make it necessary to select a context even if
  the optimization problem does not require LSA or JAPC. The problem has been
  alleviated by always selecting the unmultiplexed context by default.

## v0.0.8

### Visible changes

- The configure dialog is now more lenient with unconventional config types.
  As the bare minimum, it shows a line-edit widget. Previously, a read-only
  label would be shown.

### Bug fixes

- When applying a configure dialog, check boxes that were never clicked would
  always register as True. This has been fixed.

## v0.0.7

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
