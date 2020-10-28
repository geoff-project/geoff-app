Generic Optimization Frontend and Framework (GeOFF)
===================================================

This is the graphical application for generic numerical optimization and
reinforcement learning on CERN accelerators. It bundles:
1. interfaces to the machines and simulations thereof, and
2. numerical optimizers and reinforcement learners that can use these
   interfaces.

This repository is available on [CERN's Gitlab][Gitlab].

[Gitlab]: https://gitlab.cern.ch/vkain/acc-app-optimisation

Table of Contents
-----------------

[[_TOC_]]

Installation
------------

If you have access to the CERN Technical Network and the [AccPy][] package
repository, you can install this package via Pip:

```bash
$ pip install acc-app-optimisation
```

Otherwise, you can clone this repository and install it via the Setuptools:

```bash
$ git clone https://gitlab.cern.ch/vkain/acc-app-optimisation
$ pip install .
```

[AccPy]: https://acc-py-repo.cern.ch/

Deployment
==========

TBD
