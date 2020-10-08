import enum


class IncaAccelerators(enum.Enum):

    def __init__(self, acc_name,lsa_name):
        self.acc_name = acc_name
        self.lsa_name = lsa_name


    SPS = "SPS","sps"
    PSB = "PSB","psb"
    PS = 'PS','ps'
    LEIR = 'LEIR','leir'
