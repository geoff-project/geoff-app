Generic Optimisation Frontend and Framework (GeOFF)
===================================================

This is the graphical application for generic numerical optimisation and
reinforcement learning on CERN accelerators. It bundles:
1. interfaces to the machines and simulations thereof, and
2. numerical optimisers and reinforcement learners that can use these
   interfaces.

This repository is available on [CERN's Gitlab][Gitlab].

Table of Contents
=================

[[_TOC_]]


Basic Usage
===========

We manage an [acc-py-deployed][acc-py-deploy] version of the app on the General
and Technical Networks.

Setup
-----

To use [acc-py-deploy][], you need to activate the September 2020 Beta
version of AccPy. There are two ways to do this. One is to stay on the stable
Acc-Py release and only activate the deploy tool:

```bash
# Activate stable Acc-Py.
# This is not necessary if you do this in your init script already.
source /acc/local/share/python/acc-py/pro/setup.sh

# Add Acc-Py-Deploy to your executable path.
export PATH=/acc/local/share/python/tmp/deploy-beta/acc-py-cli/pro/bin:$PATH
```

The other way is to completely switch to the upcoming Acc-Py release. Note that
this might break your existing setup, as the release changes a lot of things.
It is based on Python 3.7 instead of 3.6, it has a much slimmer set of
pre-installed packages, etc.

```bash
# Activate Acc-Py 2020.09 Beta.
# If you already source Acc-Py in your init script, you might have to modify
# that line.
source /acc/local/share/python/acc-py/base/2020.9b/setup.sh
```

Running
-------

Once this setup is done, you can run the GUI by executing the following line:

```bash
# Run the latest production release.
acc-py app run acc-app-optimisation

# Run a specific version.
acc-py appp run --version 0.0.1 acc-app-optimisation
```

This runs the GUI in a completely sealed virtual environment. This means that
it is independent of the Python version, installed packages, etc. of your
current environment.

Installation
============

The information on other packages in this section is up-to-date as of November
2020.

This application vendors the unpublished project [Qt LSA Selector][] (to be
published separately as part of [Accwidgets][]), which in turn depends on
[Pjlsa 0.2][Pjlsa]. This is _not_ part of the currently stable Acc-Py release,
which only provides [Pjlsa 0.0.14][Pjlsa]. Due to this, installing this package
is a bit awkward at the moment. It is our hope that the [Acc-Py-Deploy][]
project will significantly streamline the process.

Step 1: Acc-Py and Venv
-----------------------

You can use either the stable Acc-Py release or the September 2020 Beta
release. In the former case, you **will need an insolated virtual environment**
because of the Pjlsa compatibility issue outlined above.

```bash
# Use the stable release, Python 3.6. Note that the venv is isolated from the
# Acc-Py environment (no `--system-site-packages`).
source /acc/local/share/python/acc-py-pyqt/pro/setup.sh
python -m venv /opt/venvs/acc-app-optimisation
source /opt/venvs/acc-app-optimisation/bin/activate

# Use the beta release, Python 3.7. Because the Acc-Py environment does not
# supply Pjlsa nor JPype nor PyJapc, we are free to include it in the venv.
source /acc/local/share/python/acc-py/base/2020.9b/setup.sh
python -m venv /opt/venvs/acc-app-optimisation --system-site-packages
source /opt/venvs/acc-app-optimisation/bin/activate
```

Step 2: Installing the App
--------------------------

Clone the app and install it. You can verify that it works by executing its
Python package.

```bash
cd ~/Projects
git clone https://gitlab.cern.ch/vkain/acc-app-optimisation.git
cd acc-app-optimisation
pip install .
python -m acc_app_optimisation
```

Step 3: Using Your Own Optimisation Problem
------------------------------------------------

The app provides a number of built-in problems to solve; but it also provides a
_foreign-imports_ mechanism to temporarily add your own problem to its list.
This is a great fit for experimenting with your code from within the GUI and
preview it before submitting it for official inclusion.

To include your own code in the GUI, simply pass the path to it when running
the GUI:

```bash
# Import some_file.py from the current working directory.
acc-py app run acc-app-optimisation some_file.py

# Go to ../path/to and import the package `directory` from there. The package
# must contain an __init__.py file.
acc-py app run acc-app-optimisation ../path/to/directory/

# First import `package`, then import `package.submodule`.
acc-py app run acc-app-optimisation path/to/package::submodule
```

Note the curious syntax in the third example; simply importing
`path/to/package/submodule.py` would not work, as Python would be unable to
resolve any package-relative imports in `submodule.py`. The double-colon chain
can obviously be extended to import the submodule of a submodule.

To import more than one module, simply pass the paths to all of them as
separate arguments.

Step 3: (Alternative) Adding Your Problem to the Built-In List
--------------------------------------------------------------

If the recommended procedure in step 3 doesn't work for you, it is also
possible to modify your local copy of the app to include your optimization
problem in its built-in list – but the procedure is more complicated.

You first have to install your own package (which requires a `setup.py`,
`setup.cfg` or `pyproject.toml` file). By choosing an *editable install*, you
can keep developing your environment without the need to reinstall it on each
change. (Pip actually installs symlinks to your source tree in this case.)

To make your project installable, refer to the [packaging guide of the
PyPA][pack-guide].

```bash
cd ~/Projects/my-project
pip install --editable .
```

The app imports all the environments and other optimisable problems in
[builtin\_envs.py][]. If you call [`coi.register()`][] in your package as
expected, all that is needed is that you add an import of your package to this
file. After a reinstall, your environment should appear in the GUI.

```bash
cd ~/Projects/acc-app-optimisation
# Add the line `import my_package` or `import my_package.module` to the list of
# imports in this file.
$EDITOR acc_app_optimisation/envs/builtin_envs.py
# Reinstall and execute the GUI. Your environment should now appear in it.
pip install .
python -m acc_app_optimisation
```

[Acc-Py-Deploy]: https://gitlab.cern.ch/acc-co/devops/python/acc-py-deploy
[Gitlab]: https://gitlab.cern.ch/vkain/acc-app-optimisation
[Pjlsa]: https://gitlab.cern.ch/scripting-tools/pjlsa
[Qt LSA Selector]: https://gitlab.cern.ch/nmadysa/qt-lsa-selector/
[`coi.register()`]: https://gitlab.cern.ch/be-op-ml-optimization/cernml-coi/blob/master/cernml/coi/_registration.py
[acc-py-deploy]: https://gitlab.cern.ch/acc-co/devops/python/acc-py-deploy
[accwidgets]: https://gitlab.cern.ch/acc-co/accsoft/gui/accsoft-gui-pyqt-widgets/
[builtin\_envs.py]: /acc_app_optimisation/envs/builtin_envs.py
[pack-guide]: https://packaging.python.org/tutorials/packaging-projects/
