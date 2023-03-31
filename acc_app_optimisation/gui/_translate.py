"""Translate accelerator names between various domains."""

import typing as t

import pyjapc
from accwidgets.lsa_selector import LsaSelectorAccelerator
from accwidgets.timing_bar import TimingBarDomain
from cernml import coi
from pylogbook import NamedActivity


class InitialSelection:
    """Turn command-line arguments for --machine and --user into domain objects.

    Examples:

        >>> InitialSelection(None, None)
        InitialSelection('NO_MACHINE', None)
        >>> InitialSelection("LINAC_3", None)
        InitialSelection('LINAC_3', None)
        >>> InitialSelection(None, "LEI.USER.ALL")
        InitialSelection('LEIR', 'LEI.USER.ALL')
        >>> InitialSelection("LINAC_4", "PSB.USER.ALL")
        InitialSelection('LINAC_4', 'PSB.USER.ALL')
        >>> InitialSelection("LEIR", "PSB.USER.ALL")
        Traceback (most recent call last):
        ...
        ValueError: mismatched timing domain: ...
        >>> InitialSelection("AWAKE", "PSB.USER.ALL")
        Traceback (most recent call last):
        ...
        ValueError: machine 'AWAKE' has no timing domain
        >>> InitialSelection("AWAKE", "PSB.USER.ALL")
        Traceback (most recent call last):
        ...
        ValueError: machine 'AWAKE' has no timing domain
        >>> InitialSelection("SPS", "FOO.USER.NONE")
        Traceback (most recent call last):
        ...
        ValueError: unknown timing domain: FOO.USER.NONE
        >>> InitialSelection(None, "FOO.USER.NONE")
        Traceback (most recent call last):
        ...
        ValueError: unknown timing domain: FOO.USER.NONE
    """

    machine: coi.Machine
    user: t.Optional[str]

    def __init__(self, machine: t.Optional[str], user: t.Optional[str]) -> None:
        if machine and user:
            self.machine = coi.Machine[machine]
            self.user = user
            machine_domain = machine_to_timing_domain(self.machine)
            if not machine_domain:
                raise ValueError(f"machine {self.machine.name!r} has no timing domain")
            user_domain = user_to_timing_domain(self.user)
            if not user_domain:
                raise ValueError(f"unknown timing domain: {user}")
            if machine_domain != user_domain:
                raise ValueError(
                    f"mismatched timing domain: machine {self.machine.name!r} "
                    f"expects {machine_domain.name!r}: {self.user!r}"
                )
        elif user:
            domain = user_to_timing_domain(user)
            if not domain:
                raise ValueError(f"unknown timing domain: {user}")
            translated_machine = timing_domain_to_machine(domain)
            if not translated_machine:
                raise ValueError(
                    f"no machine associated with timing domain {domain.name!r}"
                )
            self.machine = translated_machine
            self.user = user
        elif machine:
            self.machine = coi.Machine[machine]
            self.user = None
        else:
            self.machine = coi.Machine.NO_MACHINE
            self.user = None

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.machine.name!r}, {self.user!r})"

    def get_japc(self, no_set: bool = False) -> pyjapc.PyJapc:
        """Get a PyJapc instance with the selected user and machine.

        Args:
            no_set: If passed and True, no SETs are actually send to the
                machine and a message is logged in its stead.

        Returns:
            A PyJapc object. The selected user is set as the default
            timing selector. If no user is selected, no selector is set
            either, which is suitable for non-PPM devices. The selected
            machine is used to determine which InCA server to contact
            for initialization data. If no machine is selected, AD is
            contacted. This ensures that InCA is always available.
        """
        inca_accelerator = self.machine and machine_to_inca_server(self.machine)
        return pyjapc.PyJapc(
            selector=self.user or "",
            incaAcceleratorName=inca_accelerator or "AD",
            noSet=no_set,
        )


def machine_to_inca_server(machine: coi.Machine) -> t.Optional[str]:
    """Return the InCA server to contact for a given machine.

    Note that the mapping is surjective: some machines map to the same
    domain.
    """
    return {
        coi.Machine.NO_MACHINE: None,
        coi.Machine.LINAC_2: "PSB",
        coi.Machine.LINAC_3: "LEIR",
        coi.Machine.LINAC_4: "PSB",
        coi.Machine.LEIR: "LEIR",
        coi.Machine.PS: "PS",
        coi.Machine.PSB: "PSB",
        coi.Machine.SPS: "SPS",
        coi.Machine.AWAKE: "AWAKE",
        coi.Machine.LHC: "LHC",
        coi.Machine.ISOLDE: "ISOLDE",
        coi.Machine.AD: "AD",
        coi.Machine.ELENA: "ELENA",
    }.get(machine)


def machine_to_timing_domain(machine: coi.Machine) -> t.Optional[TimingBarDomain]:
    """Return the timing domain for a given CERN machine.

    Note that the mapping is surjective: some machines map to the same
    domain.
    """
    return {
        coi.Machine.NO_MACHINE: None,
        coi.Machine.LINAC_2: TimingBarDomain.PSB,
        coi.Machine.LINAC_3: TimingBarDomain.LEI,
        coi.Machine.LINAC_4: TimingBarDomain.PSB,
        coi.Machine.LEIR: TimingBarDomain.LEI,
        coi.Machine.PS: TimingBarDomain.CPS,
        coi.Machine.PSB: TimingBarDomain.PSB,
        coi.Machine.SPS: TimingBarDomain.SPS,
        coi.Machine.AWAKE: None,
        coi.Machine.LHC: TimingBarDomain.LHC,
        coi.Machine.ISOLDE: None,
        coi.Machine.AD: TimingBarDomain.ADE,
        coi.Machine.ELENA: TimingBarDomain.LNA,
    }.get(machine)


def timing_domain_to_machine(domain: TimingBarDomain) -> t.Optional[coi.Machine]:
    """Return the machine most closely linked to the giving timing domain.

    Note that the mapping is injective: not every machine is returned.
    """
    return {
        TimingBarDomain.LHC: coi.Machine.LHC,
        TimingBarDomain.SPS: coi.Machine.SPS,
        TimingBarDomain.CPS: coi.Machine.PS,
        TimingBarDomain.PSB: coi.Machine.PSB,
        TimingBarDomain.LNA: coi.Machine.ELENA,
        TimingBarDomain.LEI: coi.Machine.LEIR,
        TimingBarDomain.ADE: coi.Machine.AD,
    }.get(domain)


def user_to_timing_domain(user: str) -> t.Optional[TimingBarDomain]:
    """Extract the timing domain from a user string."""
    domain, _, _ = user.partition(".")
    return TimingBarDomain.__members__.get(domain)


def machine_to_activity(machine: coi.Machine) -> t.Union[None, str, NamedActivity]:
    """Return the pylogbook activity for a given CERN machine.

    Note that the mapping is not complete: Not every activity is
    returned and not every machine has an associated activity.
    """
    return {
        coi.Machine.NO_MACHINE: None,
        coi.Machine.LINAC_2: NamedActivity.LINAC4,
        coi.Machine.LINAC_3: NamedActivity.LINAC3,
        coi.Machine.LINAC_4: NamedActivity.LINAC4,
        coi.Machine.LEIR: NamedActivity.LEIR,
        coi.Machine.PS: NamedActivity.PS,
        coi.Machine.PSB: NamedActivity.PSB,
        coi.Machine.SPS: NamedActivity.SPS,
        coi.Machine.AWAKE: None,
        coi.Machine.LHC: NamedActivity.LHC,
        coi.Machine.ISOLDE: None,
        coi.Machine.AD: "ADE",
        coi.Machine.ELENA: NamedActivity.ELENA,
    }.get(machine)


def machine_to_lsa_accelerator(
    machine: coi.Machine,
) -> t.Optional[LsaSelectorAccelerator]:
    """Return the LSA accelerator for a given CERN machine.

    Note that the mapping is surjective: some machines map to the same
    domain.
    """
    return {
        coi.Machine.LINAC_3: LsaSelectorAccelerator.LEIR,
        coi.Machine.LINAC_4: LsaSelectorAccelerator.PSB,
        coi.Machine.LEIR: LsaSelectorAccelerator.LEIR,
        coi.Machine.PS: LsaSelectorAccelerator.PS,
        coi.Machine.PSB: LsaSelectorAccelerator.PSB,
        coi.Machine.SPS: LsaSelectorAccelerator.SPS,
        coi.Machine.AWAKE: LsaSelectorAccelerator.AWAKE,
        coi.Machine.LHC: LsaSelectorAccelerator.LHC,
        coi.Machine.ISOLDE: LsaSelectorAccelerator.ISOLDE,
        coi.Machine.AD: LsaSelectorAccelerator.AD,
        coi.Machine.ELENA: LsaSelectorAccelerator.ELENA,
    }.get(machine)
