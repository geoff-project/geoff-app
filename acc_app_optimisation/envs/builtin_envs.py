#!/usr/bin/env python
"""All environments that are supported out of the box.

This module should contain only imports of third-party modules. Each
module should, by virtue of being imported, register its environment
using the `cernml.coi.register()` API.
"""

# pylint: disable = unused-import

import cern_awake_env.machine
import cern_awake_env.simulation
import cern_leir_transfer_line_env
import cern_sps_tune_env
import cern_sps_zs_alignment_env
import linac3_lebt_tuning
import cern_sps_splitter_opt_env
