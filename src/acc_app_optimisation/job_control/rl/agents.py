# SPDX-FileCopyrightText: 2020-2023 CERN
# SPDX-FileCopyrightText: 2023 GSI Helmholtzzentrum für Schwerionenforschung
# SPDX-FileNotice: All rights not expressly granted are reserved.
#
# SPDX-License-Identifier: GPL-3.0-or-later OR EUPL-1.2+

import typing as t
from pathlib import Path

import stable_baselines3 as sb3
from cernml import coi
from cernml.svd import SvdOptimizer
from stable_baselines3.common.base_class import BaseAlgorithm

BaseAlgorithm.register(SvdOptimizer)


class GenericAgentFactory(coi.CustomPolicyProvider):
    ALGORITHMS: t.Final[t.Mapping[str, t.Type["BaseAlgorithm"]]] = {
        "A2C": sb3.A2C,
        "DDPG": sb3.SAC,
        "PPO": sb3.PPO,
        "SAC": sb3.SAC,
        "SVD": t.cast(t.Type["BaseAlgorithm"], SvdOptimizer),
        "TD3": sb3.TD3,
    }

    def __init__(self) -> None:
        self.file_path: t.Optional[Path] = None

    @classmethod
    def get_policy_names(cls) -> t.List[str]:
        return list(cls.ALGORITHMS)

    def load_policy(self, name: str) -> coi.Policy:
        if self.file_path is None:
            raise ValueError(f"no file with {name} trained weights selected")
        try:
            agent_class = self.ALGORITHMS[name]
        except KeyError:
            raise KeyError(f"unknown generic RL algorithm: {name}") from None
        agent = agent_class.load(self.file_path)
        assert isinstance(agent, coi.Policy), "not a policy"
        return agent
