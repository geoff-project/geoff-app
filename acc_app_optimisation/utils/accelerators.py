from enum import Enum

from cernml.coi import Machine


class IncaAccelerators(Enum):
    def __init__(self, lsa_name: str, machine: Machine) -> None:
        self.lsa_name = lsa_name
        self.machine = machine

    SPS = "sps", Machine.SPS
    PSB = "psb", Machine.PSB
    PS = "ps", Machine.PS
    LEIR = "leir", Machine.Leir
    Awake = "awake", Machine.Awake
    # Dirty hack: The LSA selector widget can't handle Linac3, so we replace it
    # with LEIR, which has the same cycles.
    Linac3 = "leir", Machine.Linac3
    Linac4 = "ln4", Machine.Linac4
