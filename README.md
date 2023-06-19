<!--
SPDX-FileCopyrightText: 2020-2023 CERN
SPDX-FileCopyrightText: 2023 GSI Helmholtzzentrum für Schwerionenforschung
SPDX-FileNotice: All rights not expressly granted are reserved.

SPDX-License-Identifier: GPL-3.0-or-later OR EUPL-1.2+
-->

Generic Optimisation Frontend and Framework (GeOFF)
===================================================

This is the graphical application for generic numerical optimisation and
reinforcement learning on CERN accelerators. It bundles:
1. interfaces to the machines and simulations thereof, and
2. numerical optimisers and reinforcement learners that can use these
   interfaces.

This repository is available on CERN's [Gitlab][].

[Gitlab]: https://gitlab.cern.ch/geoff/geoff-app

Table of Contents
=================

[[_TOC_]]

Basic Usage
===========

We use [acc-py-deploy][] to manage a central installation of the app on the
General and Technical Networks.

[acc-py-deploy]: https://gitlab.cern.ch/acc-co/devops/python/acc-py-deploy

Setup
-----

To use [acc-py-deploy][], run either of these lines in your shell. You don't
have to run them if you have already set up Acc-Py in your init script:

```shell-session
$ # Activate Acc-Py Base.
$ # This is the "base" distribution containing only the bare minimum of
$ # pre-installed packages.
$ source /acc/local/share/python/acc-py/base/pro/setup.sh
```

```shell-session
$ # Activate Acc-Py.
$ # This is the "full" distribution with lots of pre-installed packages. As of
$ # April 2021, this still lags behind Acc-Py Base by one Python release.
$ source /acc/local/share/python/acc-py/pro/setup.sh
```

Running
-------

Once this setup is done, you can run the GUI by executing the following line:

```shell-session
$ # Run the latest production release. `acc-app-optimisation` was the prototype
$ # name of the application
$ acc-py app run acc-app-optimisation
```

```shell-session
$ # Run a specific version.
$ acc-py app run --version 0.11.0 acc-app-optimisation
```

This runs the GUI in a completely sealed virtual environment. This means that
it is independent of the Python version, installed packages, etc. of your
current environment.

Installation
============

The information in this section is only relevant if you want to install this
application into your own environment. You typically want to do this when
developing a plugin for your own optimization problem. This section is
up-to-date as of July 2023.

Step 1: Acc-Py and Venv
-----------------------

As before, you have the choice between basing your environment either on the
Base or the Interactive distribution of Acc-Py. See [*Getting Started with
Acc-Py*][Acc-Py] for a full explanation. Once this is set up, you can create
and activate a *virtual environment*, or [*venv*][venv] for short. This helps
isolate installed dependencies from your system and makes it easier to work on
multiple independent projects.

```shell-session
$ # Set up production-stage release of Acc-Py Base, switch to Python 3.7.
$ source /acc/local/share/python/acc-py/base/pro/setup.sh

$ # At CERN, HOME is on the AFS filesystem and is strictly limited in space.
$ # Because GeOFF has some very large dependencies, we recommend putting your
$ # venv somewhere else when on a CERN machine. If you have a BE-provided VPC,
$ # one possibility is /opt/venvs.
$ mkdir -p ~/venvs

$ # Make a virtual environment based on Acc-Py base and activate it.
$ acc-py venv ~/venvs/geoff
$ source ~/venvs/geoff/bin/activate
```

[Acc-Py]: https://wikis.cern.ch/display/ACCPY/Getting+started+with+Acc-Py
[venv]: https://docs.python.org/3/library/venv.html

Of course, you're free to set up your virtual environment however you prefer.
The steps above have been tested to work.

Step 2: Installing the App
--------------------------

Once you've activated a virtual environment of your choice, installing the
application is dead-simple:

```shell-session
$ pip install acc-app-optimisation
```

And you can run the installed version via:

```shell-session
$ python -m acc_app_optimisation
```

If you have decided to clone this repository, you can install this clone
(instead of a published verison) like this:

```shell-session
$ git clone https://gitlab.cern.ch/geoff/geoff-app
$ cd geoff-app
$ pip install .
```

Step 2B: Installing the App outside of CERN
-------------------------------------------

Note that GeOFF has only been published on the [Acc-Py Package Index][]. If you
wish to install it outside the CERN network, you can create a proxy to tunnel
into the CERN network.

[Acc-Py Package Index]: https://wikis.cern.ch/display/ACCPY/Python+package+index

To tunnel into the CERN network, you first need to install SOCKS support for
Pip and starts a SOCKS proxy:

```shell-session
$ pip install -U requests[socks]
$ ssh -ND localhost:12345 lxtunnel.cern.ch &
```

Then you can install GeOFF from the Acc-Py index by specifying its URL and
telling Pip to use the proxy:

```shell-session
$ https_proxy=socks5://localhost:12345 pip install \
    --index-url https://acc-py-repo.cern.ch/repository/vr-py-releases/ \
    acc-app-optimisation
```

If you wish to use the Acc-Py package index permanently while inside your venv,
you can install a hook for this:

```shell-session
$ pip install git+https://gitlab.cern.ch/acc-co/devops/python/acc-py-pip-config
```

Step 3: Using Your Own Optimisation Problem
-------------------------------------------

The app provides a number of built-in problems to solve; but it also provides a
_foreign-imports_ mechanism to temporarily add your own problem to its list.
This is a great fit for experimenting with your code from within the GUI and
preview it before submitting it for official inclusion.

To include your own code in the GUI, simply pass the path to it when running
the GUI:

```shell-session
$ # Import some_file.py from the current working directory.
$ acc-py app run acc-app-optimisation some_file.py

$ # Go to ../path/to and import the package `directory` from there. The package
$ # must contain an __init__.py file.
$ acc-py app run acc-app-optimisation ../path/to/directory/

$ # First import `package`, then import `package.submodule`.
$ acc-py app run acc-app-optimisation path/to/package::submodule
```

Note the curious syntax in the third example; simply importing
`path/to/package/submodule.py` would not work, as Python would be unable to
resolve any package-relative imports in `submodule.py`. The double-colon chain
can obviously be extended to import the submodule of a submodule.

To import more than one module, simply pass the paths to all of them as
separate arguments. You can pass `--keep-going` to continue loading packages
even if one of them fails.

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

To make your project installable, refer to the [packaging guide][] of the
PyPA.

[packaging guide]: https://packaging.python.org/tutorials/packaging-projects/

```shell-session
$ cd ~/Projects/my-project
$ pip install --editable .
```

All built-in optimization problems are given in a list called `BUILTIN_ENVS` in
[envs.py](/acc_app_optimisation/envs/builtin_envs.py#L20) and and the app
imports them one-by-one via [`importlib.import_module()`][]. If you call
[`coi.register()`][] in your package (as is expected), you only need the
package name to this list. After a reinstall, your environment should appear in
the GUI.

[`importlib.import_module()`]: https://docs.python.org/3/library/importlib.html#importlib.import_module
[`coi.register()`]: https://gitlab.cern.ch/geoff/cernml-coi/blob/master/cernml/coi/_registration.py

```shell-session
$ cd ~/Projects/geoff-app

# Add the line `import my_package` or `import my_package.module` to the list of
# imports in this file.
$ $EDITOR acc_app_optimisation/envs/builtin_envs.py

# Reinstall and execute the GUI. Your environment should now appear in it.
$ pip install .
$ python -m acc_app_optimisation
```

License
-------

Except as otherwise noted, this work is licensed under either of [GNU Public
License, Version 3.0 or later](LICENSES/GPL-3.0-or-later.txt), or [European
Union Public License, Version 1.2 or later](LICENSES/EUPL-1.2.txt), at your
option. See [COPYING](COPYING) for details.

Unless You explicitly state otherwise, any contribution intentionally submitted
by You for inclusion in this Work (the Covered Work) shall be dual-licensed as
above, without any additional terms or conditions.

For full authorship information, see the version control history.
