# SPDX-FileCopyrightText: 2020-2023 CERN
# SPDX-FileCopyrightText: 2023 GSI Helmholtzzentrum für Schwerionenforschung
# SPDX-FileNotice: All rights not expressly granted are reserved.
#
# SPDX-License-Identifier: GPL-3.0-or-later OR EUPL-1.2+

"""All environments that are supported out of the box.

This module should contain only imports of third-party modules. Each
module should, by virtue of being imported, register its environment
using the `cernml.coi.register()` API.
"""

# pylint: disable = unused-import

import cern_awake_env.machine
import cern_awake_env.simulation
import cern_isolde_offline_env
import cern_leir_transfer_line_env
import cern_sps_splitter_opt_env
import cern_sps_tune_env
import cern_sps_zs_alignment_env
import linac3_lebt_tuning
import psb_extr_and_recomb_optim.optimizer
import sps_blowup

__all__ = [
    "cern_awake_env",
    "cern_isolde_offline_env",
    "cern_leir_transfer_line_env",
    "cern_sps_splitter_opt_env",
    "cern_sps_tune_env",
    "cern_sps_zs_alignment_env",
    "linac3_lebt_tuning",
    "psb_extr_and_recomb_optim",
    "sps_blowup",
]
