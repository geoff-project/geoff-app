<!--
SPDX-FileCopyrightText: 2020-2023 CERN
SPDX-FileCopyrightText: 2023 GSI Helmholtzzentrum für Schwerionenforschung
SPDX-FileNotice: All rights not expressly granted are reserved.

SPDX-License-Identifier: GPL-3.0-or-later OR EUPL-1.2+
-->

# Changelog

## Unreleased

### Visible changes

- GeOFF now uses [Global Trim Request Hooks][coi-utils-docs-hooks] to modify
  all trims that are made through the [cernml-coi-utils][]. Specifically:
  - All trims are marked as transient *except* the final step of any numerical
    optimization (the one that evaluates `x_optimal` a final time) and whenever
    the user clicks the Reset button.
  - All trim descriptions are enhanced with various information that is easily
    accessible within GeOFF but not so within its plugins. This information
    includes, in this order:
    1. the context of the trim (initializing, resetting, optimizing, …);
    2. step index, episode index, skeleton point, and any related information;
    3. the name and version, or at least file path of the optimization problem;
    4. GeOFF's name and version. This information is only added if the trims
    are made through `cernml.lsa_utils`. To make full use of this feature,
    plugin authors are encouraged to avoid using the raw Java API of LSA. If
    the utilities do not suit your needs for any reasons, you are [encouraged
    to report an issue][cernml-coi-utils-issues] to have the required
    functionality added.

### Build changes

- Wrappers around numerical optimization algorithms have been outsourced into
  [cernml-coi-optimizers][].
- Update cern-sps-splitter-opt-env requirement to 0.0.9.
- Update cern-leir-transfer-line-env requirement to 0.5.4.
- Update cernml-coi-utils requirement to 0.2.10.
- Update pjlsa requirement to 0.2.18.
- Update pyjapc requirement to 2.6.

### Bug fixes

- Remove extraneous call to `compute_function_ojective()` when resetting a
  `FunctionOptimizable` problem.

## v0.12.4

### Build changes

- Update sps-blowup requirement to 1.0.2.

## v0.12.3

### Build changes

- Update sps-blowup requirement to 1.0.1.

## v0.12.2

### Build changes

- Update linac3-lebt-tuning requirement to 1.0.2.

## v0.12.1

- Changed project directory structure to
  [src-layout][setuptools-docs-src-layout].

## v0.12.0

### Visible changes

- The new command-line parameter `--keep-going` (`-k` for short) allows to
  continue to import plugins even if one of them fails.
- If multiple exceptions are raised during initialization, the error dialog now
  shows the number of remaining exceptions in the queue.
- The error dialog to show plugin-related exceptions has been overhauled. It's
  now resizeable, colors the the exception traceback in a useful manner and
  automatically scrolls to the exception message.

## v0.11.1

### Bug fixes

- Fix race condition that broke the `--user` command-line parameter.

### Build changes

- Update psb-extr-and-recomb-optim requirement to 1.0.2.

## v0.11.0

### Build changes

- Add sps-blowup 1.0.0.
- Add psb-extr-and-recomb-optim 1.0.0.

### Other changes

- The project has been open-sourced and license information has been added. See
  [COPYING](COPYING) for more information.

## v0.10.1

### Visible changes

- Log messages now distinguish between complete and incomplete cancellations.
  Complete ones are those that either happen between calls to the optimization
  problem, or that are acknowledged by the optimization problem as having been
  handled. Incomplete cancellations mean that the GUI is not sure whether it's
  safe to call the optimization problem without breaking anything. This
  distinction is made to better diagnose cases in which an exception is raised
  at a location that the optimization problem author did not expect.

### Bug fixes

- Remove superfluous debug code that raises an exception in certain cases.
- Fix a bug that delayed the call to `coi.Problem.close()` to a point where the
  JVM might be shut down already, making all calls to
  `PyJapc.SubscriptionHandle.stopMonitoring()` fail.

## v0.10.0

### Visible changes

- Add support for `FunctionOptimizable.override_skeleton_points()`. If a
  function optimization problem implements this method, it takes over the
  selection of skeleton points from the user. The configuration window will in
  that case provide a read-only view of the chosen points. The view is updated
  every time the user clicks Apply. After applying the configuration, the
  problem is allowed to switch between overriding the skeleton points or not;
  the configuration window will be updated accordingly.

### Bug fixes

- Fix bug in machine selection box that was introduced in v0.9.0. If the app
  was started in the selection "no machine", the first choice in the box would
  do nothing, and *then* the box would behave as expected.

### Build changes

- Update cernml-coi requirement to 0.8.9. This adds support for
  `FunctionOptimizable.override_skeleton_points()`.
- Upgrade cernml-coi-utils to 0.2.6. This adds support for
  `lsa_utils.trim_scalar_settings()`.

## v0.9.0

### Visible changes

- The command-line arguments `--user`, `--machine` and `--lsa-server` now
  provide more sensible default behavior. When only one of `--machine` and
  `--lsa-server` is passed, the other is assumed to match. Crucially, this
  means that `--machine=LINAC_4` now implies e.g. `--lsa-server=psb`.
  Furthermore, `--user=SPS.USER.ALL` now implies `--machine=SPS` and
  `--lsa-server=sps`. Any obviously faulty combinations are caught and produce
  an error on startup.

### Bug fixes

  `--lsa-server=sps`. Any obviously faulty combinations are caught and produce
  an error on startup.

### Bug fixes

- Fix bug in which `--user` could not pre-select a timing user from any machine
  but the default selection.
- Fix spurious incompatibility with Python 3.7.

### Build changes

- Upgrade cern-isolde-offline-env requirement to 0.0.5.

## v0.8.5

### Ongoing bugs

- The package spuriously requires Python 3.9 to be installed. This is going to
  be fixed in the next release.

### Bug fixes

- Fix JAPC initialization: InCA accelerator name is now always deduced from the
  `--machine` and `--user` parameters. Before, the application used to always
  contact the AD server for InCA information.

## v0.8.4

### Bug fixes

- Fix cern-isolde-offline-env being declared in stale setup.cfg.

## v0.8.3

### Build changes

- Add cern-isolde-offline-env 0.0.4.

## v0.8.2

### Build changes

- Add support for Python 3.9.
- Update stable-baselines3 requirement to 1.0.
- Update accwidgets requirement to 1.7.5.
- Update cernml-coi requirement to 0.8.7.
- Moved project configuration to pyproject.toml.
- The `importlib-metadata` backport now is only a dependency for Python<3.8.
  When running on Python 3.8 and beyond, the standard library module
  `importlib.metadata` is used.
- Switch to Acc-Py CI templates v2. In the course, this app is no longer
  distributed as sdist, but instead only as wheel.

## v0.8.1

### Build changes

- Add cern-sps-splitter-opt-env 0.0.8.

## v0.8.0

### Visible changes

- The `--machine` command-line parameter now also accepts machine names in
  lower-case.
- The new command-line parameter `--user` allows specifying the TGM user to
  preselect in the LSA selector. This allows forwarding a user selected in the
  CCM to this program.

### Build changes

- Upgrade cernml-coi requirement to 0.8.5. This enables use of AD and ELENA
  optimization problems.

## v0.7.5

### Visible changes

- BOBYQA now supports a higher precision on its `rhobeg` and `rhoend`
  parameters. For regrettable internal reasons, the input fields in the
  configuration dialog consequently no longer have spin controls.
- The runtime plugin mechanism (known as "foreign imports") now supports
  modules inside namespace packages. As before, it remains an error to import a
  namespace package directly. However, the error message in this case has been
  improved. (It used to be "AssertionError", now it reads "no `__init__.py`
  found".) This is to catch common mistakes in which a plugin's project
  directory is passed instead of the package path.

## v0.7.4

### Build changes

- Upgrade cern-leir-transfer-line-env requirement to 0.5.2.

## v0.7.3

### Build changes

- Upgrade cern-leir-transfer-line-env requirement to 0.5.1.

## v0.7.2

### Build changes

- Upgrade cernml-coi-utils to 0.2.5. This adds the ability to trim multiple
  functions at once via `cernml.lsa_utils.IncorporatorGroup`.
- Upgrade cern-leir-transfer-line-env requirement to 0.5.0.

## v0.7.1

### Bug fixes

- FunctionOptimizable problems are now recognized as such again.

## v0.7.0

### Visible changes

- If a plugin raises an exception, open a message box instead of expanding the
  log console.
- Show an informational message box whenever an optimization, RL training, RL
  run or reset operation terminates successfully.

### Bug fixes

- The initial point for numerical optimization is now verified to be a 1-D
  float array. Returning anything else prevents optimization from starting.
  This catches a common bug where an array with `dtype="object"` is returned by
  accident.

## v0.6.0

### Visible changes

- Refactor logging. By default, the app now logs all events not only to the
  logging console, but also to a file in the user's temporary directory. This
  is to faciliate post-mortem debugging in the case of a crash. This behavior
  can be disabled with the new command-line option `--disable-logging`. The
  user may also choose a specific logging file with the new command-line option
  `--log-file`.
- Remove the command-line option `--no-capture-stdout`. It is made superfluous
  by the new setup. Its behavior can roughly be emulated with `--log-file=-`.
  This uses the new logging mechanism, but picks `stderr` instead of a real
  file for output.

## v0.5.0

### Visible changes

- Upgrade PyQtGraph from 0.10 to 0.12. This should bring a number of bug fixes,
  performance improvements and quality-of-life changes. In particular, curves
  on the **actor plot** can now be selectively hidden by clicking their
  respective **icon** in the graph's legend.
- Provide new screenshot button provided by [AccWidgets][].

### Build changes

- Upgrade cern-leir-transfer-line-env requirement to 0.4.4.
- Upgrade accwidgets requirement to 1.7.0.
- Upgrade pyqtgraph requirement to 0.12.0.
- Add dependency on pylogbook 3.3.0 for new screenshot button.

## v0.4.0

### Visible changes

- Add Extremum Seeking via [cernml-extremum-seeking][] as a numerical
  optimization scheme.

### Build changes

- Use [setuptools-scm][] for version management. This is a breaking change, as
  it removes the `acc_app_optimisation.__version__` constant. Please use
  [`importlib.metadata`][] (backported as [`importlib_metadata`][] before
  Python 3.8) to query the app's version programmatically.

## v0.3.4

### Build changes

- Upgrade cern-leir-transfer-line-env requirement to 0.4.3.

## v0.3.3

### Build changes

- Upgrade cern-leir-transfer-line-env requirement to 0.4.2.

## v0.3.2

### Visible changes

- Resets of numerical optimization can now be cancelled. For most problems,
  this only does anything if the optimization problem is
  [cancellable][coi-docs-cancellation]. For [function
  optimization][coi-docs-funcopt], this may interrupt the reset between
  manipulated time points.
- If a plugin raises an exception, the log console expands automatically now.

### Build changes

- Upgrade cern-awake-env requirement to 0.18.0.

## v0.3.1

### Bug fixes

- Fix broken configuration of Bayesian optimization.

## v0.3.0

### Visible changes

- Add Bayesian optimization via [scikit-optimize][] as a numerical optimization
  scheme.

### Build changes

- Add dependency on scikit-optimize v0.9.0 for new Bayesian optimization.
- Drop dependency on cernml-coi-funcs v0.2.4. This package has been deprecated
  since [v0.0.1.8](#v018). The `FunctionOptimizable` interface has been
  integrated into cernml-coi; the LSA utilities have been integrated into
  cernml-coi-utils.

## v0.2.2

### Visible changes

- Before resets of numerical optimization, the user is shown the reset point
  and asked for confirmation.
- If an exception is raised during the import of foreign or built-in
  environments, an error dialog is shown to the user.

### Build changes

- Add linac3-lebit-tuning 1.0.0.

## v0.2.1

### Build changes

- Upgrade cern-leir-transfer-line-env requirement to 0.4.1.

## v0.2.0

### Build changes

- Upgrade cernml-coi requirement to 0.8.2. This is a breaking change w.r.t. to
  the previous 0.7.x line.
- Upgrade cern-awake-env requirement to 0.16.0.
- Upgrade cern-leir-transfer-line-env requirement to 0.4.0.
- Upgrade cern-sps-tune-env requirement to 0.4.0.
- Upgrade cern-sps-zs-alignment-env requirement to 0.4.0.

### Visible changes

- Add a legend to the built-in actors plot.

## v0.1.11

### Build changes

- Upgrade cern-leir-transfer-line-env requirement to 0.3.2.

## v0.1.10

### Build changes

- Upgrade cernml-coi-utils to 0.2.3. This adds an optional *description*
  argument to LSA incorporations.
- Upgrade cern-leir-transfer-line-env requirement to 0.3.1.

### Visible changes

- Expose option *nsamples* from BOBYQA, which allows you to evaluate the cost
  function multiple times and optimize on the average.

## v0.1.9

- Upgrade cern-sps-zs-alignment-env requirement to 0.3.2.
- Upgrade cern-leir-transfer-line-env requirement to 0.3.0.

## v0.1.8

### Build changes

- Upgrade cernml-svd to 3.0.0. This reverts the way action normalization is
  done and finishes the initial prototype phase.
- Upgrade cernml-coi to 0.7.6. This is the last version that contains both
  interaces and utilities. Authors of optimization problems are encouraged to
  use [cernml-coi-utils][] for the latter. If their code works with cernml-coi
  0.7.6 without deprecation warnings, it will likely work with the upcoming
  cernml-coi 0.8.0 as well.
- Upgrade cernml-coi-funcs to 0.2.4. This is the final release. The
  `FunctionOptimizable` interface has been integrated into cernml-coi; the LSA
  utilities have been integrated into [cernml-coi-utils][]. Authors of
  optimization problems are encouraged to change their code accordingly.
- Add dependency on cernml-coi-utils v0.2.2. Having both the new utilities
  package and a cernml-coi version that still has its utilities will make
  transitioning to the new API easier.

### Bug fixes

- Fix crash when resetting after an aborted optimization due to unequal lengths
  in action/objective logs.

## v0.1.7

### Visible changes

- Change the way exceptions are logged. The exception message now always
  appears last, making it more visible in the log console.
- Increase the default value of BOBYQA's `rhobeg` parameter to 0.5 (was 0.1).
  Too many built-in environments failed to optimize speedily when the initial
  trust region was too small.
- When an environment is reset after numeric optimization, the associated actor
  values and loss are now appended to the respective history plots.

### Build changes

- Upgrade cern-sps-tune-env requirement to 0.3.0.
- Upgrade cern-sps-zs-alignment-env requirement to 0.3.0.

## v0.1.6

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

- Add [Singular Value Decomposition (SVD)][cernml-svd] as an RL algorithm. It
  works best on linear problems that can be described by an invertible response
  matrix. Thanks to @ivojskov for the implementation!
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
  via [Stable Baselines 3][].
- Add more built-in optimization problems:
    - [SPS ZS Alignment][sps-zs-alignment],
    - [SPS Tune][sps-tune],
    - [LEIR Transfer Line][leir-transfer-line].
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
  [AccWidgets][].
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
- Fix conflicting test dependencies (Require PyTest as modern as required by
  PyTest-Mock).

## v0.0.1

- Initial release.

[coi-utils-docs-hooks]: https://acc-py.web.cern.ch/gitlab/geoff/cernml-coi-utils/docs/stable/guide/lsa_utils.html#global-trim-request-hooks
[cernml-coi-utils-issues]: https://gitlab.cern.ch/geoff/cernml-coi-utils/-/issues
[cernml-coi-optimizers]: https://gitlab.cern.ch/geoff/cernml-coi-optimizers/
[setuptools-docs-src-layout]: https://setuptools.pypa.io/en/latest/userguide/package_discovery.html#src-layout
[cernml-extremum-seeking]: https://gitlab.cern.ch/geoff/optimizers/cernml-extremum-seeking/
[setuptools-scm]: https://pypi.org/project/setuptools-scm/
[`importlib.metadata`]: https://docs.python.org/3/library/importlib.metadata.html
[`importlib_metadata`]: https://importlib_metadata.readthedocs.io/
[coi-docs-cancellation]: https://cernml-coi.docs.cern.ch/guide/cancellation.html#cancellation
[coi-docs-funcopt]: https://cernml-coi.docs.cern.ch/guide/funcopt.html
[scikit-optimize]: https://scikit-optimize.github.io/
[cernml-coi-utils]: https://gitlab.cern.ch/geoff/cernml-coi-utils/
[cernml-svd]: https://gitlab.cern.ch/geoff/optimizers/cernml-svd/
[Stable Baselines 3]: https://stable-baselines3.readthedocs.io/
[sps-zs-alignment]: https://gitlab.cern.ch/geoff/example-envs/sps-zs-alignment
[sps-tune]: https://gitlab.cern.ch/geoff/example-envs/sps-tune/
[leir-transfer-line]: https://gitlab.cern.ch/geoff/example-envs/leir-transfer-line
[AccWidgets]: https://acc-py.web.cern.ch/gitlab/acc-co/accsoft/gui/accsoft-gui-pyqt-widgets/docs/stable/widgets/lsa_selector/index.html
