Generic Optimisation Frontend and Framework (GeOFF)
===================================================

This is the graphical application for generic numerical optimisation and
reinforcement learning on CERN accelerators. It bundles:
1. interfaces to the machines and simulations thereof, and
2. numerical optimisers and reinforcement learners that can use these
   interfaces.

This repository is available on [CERN's Gitlab][Gitlab].

[Gitlab]: https://gitlab.cern.ch/vkain/acc-app-optimisation

Table of Contents
=================

[[_TOC_]]

Installation
============

The information on other packages in this section is up-to-date as of November
2020.

This application depends on a fork of an unpublished project [Qt LSA
Selector][] (to be published as part of [Accwidgets][]), which in turn depends
on [Pjlsa 0.2][Pjlsa]. This is _not_ part of the currently stable Acc-Py
release, which only provides [Pjlsa 0.0.14][Pjlsa]. Due to this, installing
this package is a bit awkward at the moment. It is our hope that the
[Acc-Py-Deploy][] project will significantly streamline the process.

[Qt LSA Selector]: https://gitlab.cern.ch/nmadysa/qt-lsa-selector/
[Pjlsa]: https://gitlab.cern.ch/scripting-tools/pjlsa
[accwidgets]: https://gitlab.cern.ch/acc-co/accsoft/gui/accsoft-gui-pyqt-widgets/
[Acc-Py-Deploy]: https://gitlab.cern.ch/acc-co/devops/python/acc-py-deploy

Step 1: Acc-Py and Venv
-----------------------

You can use either the stable Acc-Py release or the September 2020 Beta
release. In the former case, you _will_ need an insolated virtual environment
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

Step 2: Qt LSA Selector
-----------------------

Clone the [Qt LSA Selector][] and install it. You can verify that it works by
executing the package itself.

```bash
cd ~/Projects
git clone --depth=1 https://gitlab.cern.ch/nmadysa/qt-lsa-selector.git
cd qt-lsa-selector
pip install .
python -m qt_lsa_selector
```

Step 3: The App Itself
----------------------

Once you've installed the LSA selector, you can clone and install the app
itself. Once again, you can give it a test run by executing its Python package.

```bash
cd ~/Projects
git clone https://gitlab.cern.ch/vkain/acc-app-optimisation.git
cd acc-app-optimisation
pip install .
python -m acc_app_optimisation
```

Step 4: Installing Your Own Optimisation Problem
------------------------------------------------

In order to optimise your own environment in this application, you first have
to install it and then import it in the app. By choosing an *editable install*,
you can keep developing your environment without the need to reinstall it on
each change. (Pip actually installs symlinks to your source tree in this case.)

To make your project installable, refer to the [packaging guide of the
PyPA][pack-guide].

```bash
cd ~/Projects/my-project
pip install --editable .
```

[pack-guide]: https://packaging.python.org/tutorials/packaging-projects/

Step 5: Importing your Problem in the App
-----------------------------------------

The app imports all the environments and other optimisable problems in
[envs\_prep.py][]. If you call [`coi.register()`][] in your package as
expected, all that is needed is that you add an import of your package to this
file. After a reinstall, your environment should appear in the GUI.

```bash
cd ~/Projects/acc-app-optimisation
# Add the line `import my_package` or `import my_package.module` to the list of
# imports in this file.
$EDITOR acc_app_optimisation/envs/envs_prep.py
# Reinstall and execute the GUI.
pip install .
python -m acc_app_optimisation
```

[envs\_prep.py]: https://gitlab.cern.ch/vkain/acc-app-optimisation/blob/master/acc_app_optimisation/envs/envs_prep.py
