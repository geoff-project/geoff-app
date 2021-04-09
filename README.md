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

To use [acc-py-deploy][], run either of these lines in your shell. You don't
have to run them if you have already set up Acc-Py in your init script:

```bash
# Activate Acc-Py Base.
# This is the "base" distribution containing only the bare minimum of
# pre-installed packages.
source /acc/local/share/python/acc-py/base/pro/setup.sh

# Activate Acc-Py.
# This is the "full" distribution with lots of pre-installed packages. As of
# April 2021, this still lags behind Acc-Py Base by one Python release.
source /acc/local/share/python/acc-py/pro/setup.sh
```

Running
-------

Once this setup is done, you can run the GUI by executing the following line:

```bash
# Run the latest production release.
acc-py app run acc-app-optimisation

# Run a specific version.
acc-py app run --version 0.1.3 acc-app-optimisation
```

This runs the GUI in a completely sealed virtual environment. This means that
it is independent of the Python version, installed packages, etc. of your
current environment.

Installation
============

The information in this section is only relevant if you want to install this
application into your own environment. You typically want to do this when
developing a plugin for your own optimization problem. This section is
up-to-date as of December 2020.

This application currently vendors the [Qt LSA Selector][] widget (to be
published as part of [Accwidgets][] 0.5). This project in turn depends on
[Pjlsa 0.2][Pjlsa]. This is _not_ part of the current Acc-Py release (19.5.2),
which only provides [Pjlsa 0.0.14][Pjlsa]. Due to this, installing this package
is a bit awkward at the moment.

Step 1: Acc-Py and Venv
-----------------------

You can start out with two base distributions:
- Acc-Py Base 2020.11 (slim distribution, incldudes the bare minimum);
- Acc-Py 19.5.2 (full distribution, includes [Pjlsa][]).

If you use Acc-Py Base, you can create a virtual environment based on it as
follows:

```bash
# Set up production-stage release of Acc-Py Base, switch to Python 3.7.
source /acc/local/share/python/acc-py/base/pro/setup.sh

# Make some space for virtual environments. If you run out of space in your
# HOME, consider putting them into /opt/venvs instead.
mkdir -p ~/venvs

# Make a virtual environment based on Acc-Py base and activate it.
python -m venv --system-site-packages ~/venvs/acc-app-optimisation
source ~/venvs/acc-app-optimisation/bin/activate
```

If you use Acc-Py 19.5.2, the setup is very similar, but you need to *isolate*
your environment from the packages provided by it.

```bash
# Use the production-stage release of Acc-Py (19.5.2 at the moment), stay on
# Python 3.6.
source /acc/local/share/python/acc-py-pyqt/pro/setup.sh

# Make some space for virtual environments. If you run out of space in your
# HOME, consider putting them into /opt/venvs instead.
mkdir -p ~/venvs

# Make a virtual environment isolated from Acc-Py and activate it.
python -m venv ~/venvs/acc-app-optimisation
source ~/venvs/acc-app-optimisation
```

Of course, you're free to set up your virtual environment however you prefer.
The steps above have been tested to work.

Step 2: Installing the App
--------------------------

Once you've activated a virtual environment of your choice, installing the
application is dead-simple:

```bash
pip install acc-app-optimisation
```

And you can run the installed version via:

```bash
python -m acc_app_optimisation
```

If you have decided to clone this repository, you can install this clone
(instead of a published verison) like this:

```bash
git clone https://gitlab.cern.ch/vkain/acc-app-optimisation.git
cd acc-app-optimisation
pip install .
```

Step 3: Using Your Own Optimisation Problem
-------------------------------------------

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

Of course, if you have installed the application into your own environment, you
need to replace `acc-py app run acc-app-optimisation` with `python -m
acc_app_optimisation`.

Step 4: (Deprecated) Adding Your Problem to the Built-In List
-------------------------------------------------------------

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
