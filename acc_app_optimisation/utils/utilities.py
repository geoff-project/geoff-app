import enum


class IncaAccelerators(enum.Enum):
    def __init__(self, acc_name, lsa_name):
        self.acc_name = acc_name
        self.lsa_name = lsa_name

    SPS = "SPS", "sps"
    PSB = "PSB", "psb"
    PS = "PS", "ps"
    LEIR = "LEIR", "leir"
    AWAKE = "AWAKE", "awake"
    LINAC3 = "Linac3", "linac3"
    LINAC4 = "Linac4", "linac4"


def getAcceleratorFromAcceleratorName(name):
    for acc in IncaAccelerators:
        if acc.acc_name == name or acc.lsa_name == name:
            return acc

    return None
