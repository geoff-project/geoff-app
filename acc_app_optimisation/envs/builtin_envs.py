#!/usr/bin/env python
"""All environments that are supported out of the box.

This module should contain only imports of third-party modules. Each
module should, by virtue of being imported, register its environment
using the `cernml.coi.register()` API.
"""

# pylint: disable = unused-import

import cern_awake_env.simulation
import cern_awake_env.machine
