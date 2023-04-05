"""Translate accelerator names between various domains."""

import typing as t

import pyjapc
from accwidgets.lsa_selector import LsaSelectorAccelerator
from accwidgets.timing_bar import TimingBarDomain
from cernml import coi
from pylogbook import NamedActivity


class InitialSelection:
    """Unify CLI arguments --machine, --user and --lsa-server.

    Examples:

        >>> InitialSelection(None, None, None)
        InitialSelection('NO_MACHINE', '', 'gpn')
        >>> InitialSelection("LINAC_3", None, None)
        InitialSelection('LINAC_3', '', 'leir')
        >>> InitialSelection(None, None, 'sps')
        InitialSelection('SPS', '', 'sps')
        >>> InitialSelection(None, "LEI.USER.ALL", None)
        InitialSelection('LEIR', 'LEI.USER.ALL', 'leir')
        >>> InitialSelection("LINAC_4", "PSB.USER.ALL", "next")
        InitialSelection('LINAC_4', 'PSB.USER.ALL', 'next')
        >>> InitialSelection("PSB", "SPS.USER.ALL", None)
        Traceback (most recent call last):
        ...
        ValueError: timing selector is in domain 'SPS', but machine is 'PSB'
    """

    machine: coi.Machine
    user: str
    lsa_server: str

    def __init__(
        self,
        machine: t.Optional[str],
        user: t.Optional[str],
        lsa_server: t.Optional[str],
    ) -> None:
        self.user = user or ""
        user_timing_domain = user_to_timing_domain(self.user)
        self.machine = _deduce_machine(machine, user_timing_domain, lsa_server)
        self.lsa_server = _deduce_lsa_server(lsa_server, self.machine)
        # Consistency checks:
        # It's fine to have picked a machine, but no user. Picking a
        # user and no matching machine is bad.
        if self.user:
            # user_timing_domain is only None if `self.user == ""`.
            assert user_timing_domain
            _assert_consistent_timing_domain(self.machine, user_timing_domain)
        _assert_consistent_lsa_accelerator(self.machine, self.lsa_server)

    def __repr__(self) -> str:
        cls = type(self).__name__
        return f"{cls}({self.machine.name!r}, {self.user!r}, {self.lsa_server!r})"

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
            selector=self.user,
            incaAcceleratorName=inca_accelerator or "AD",
            noSet=no_set,
        )


def _deduce_machine(
    machine: t.Optional[str],
    timing_domain: t.Optional[TimingBarDomain],
    lsa_server: t.Optional[str],
) -> coi.Machine:
    if machine:
        # If this fails, we don't want to try other options.
        return coi.Machine[machine.upper()]
    if timing_domain:
        translated_machine = timing_domain_to_machine(timing_domain)
        if not translated_machine:
            raise ValueError(
                f"no machine found for timing domain {timing_domain.name!r}"
            )
        return translated_machine
    if lsa_server:
        try:
            translated_machine = lsa_server_to_machine(lsa_server)
        except KeyError:
            raise ValueError(
                f"no machine found for LSA server {lsa_server.upper()!r}"
            ) from None
        if translated_machine:
            return translated_machine
        # Fall through.
    return coi.Machine.NO_MACHINE


def _deduce_lsa_server(lsa_server: t.Optional[str], machine: coi.Machine) -> str:
    if lsa_server:
        return lsa_server.lower()
    if machine:
        accelerator = machine_to_lsa_accelerator(machine)
        if accelerator:
            return lsa_accelerator_to_server(accelerator)
        # Fall through.
    return "gpn"


def _assert_consistent_timing_domain(
    machine: coi.Machine, timing_domain: TimingBarDomain
) -> None:
    machine_timing_domain = machine_to_timing_domain(machine)
    if not machine_timing_domain:
        raise ValueError(
            "timing selector was passed but machine "
            f"{machine.name!r} has no timing domain"
        )
    if machine_timing_domain != timing_domain:
        if machine_timing_domain.name == machine.name:
            raise ValueError(
                f"timing selector is in domain {timing_domain.name!r}, "
                f"but machine is {machine.name!r}"
            )
        raise ValueError(
            f"timing selector is in domain {timing_domain.name!r}, "
            f"but machine {machine.name!r} has domain "
            f"{machine_timing_domain.name!r}"
        )


def _assert_consistent_lsa_accelerator(machine: coi.Machine, lsa_server: str) -> None:
    machine_accelerator = machine_to_lsa_accelerator(machine)
    # Using a machine-specific LSA database, but pre-selecting
    # NO_MACHINE is odd, but not really indicative of an error.
    if not machine_accelerator:
        assert machine == coi.Machine.NO_MACHINE
        return
    # Preselecting a machine but using a generic LSA database like NEXT
    # is perfectly acceptable.
    lsa_accelerator = lsa_server_to_accelerator(lsa_server)
    if not lsa_accelerator:
        return
    # If both have been selected by the user, they must agree.
    if lsa_accelerator != machine_accelerator:
        if machine.name == machine_accelerator.name:
            raise ValueError(
                f"selected machine implies LSA database "
                f"{machine_accelerator.name!r}, but "
                f"{lsa_accelerator.name!r} is selected"
            )
        raise ValueError(
            f"selected machine {machine.name!r} implies LSA database "
            f"{machine_accelerator.name!r}, but "
            f"{lsa_accelerator.name!r} is selected"
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
    """Extract the timing domain from a user string.

    Args:
        user: A *timing selector* string in format
        ``<domain>.USER.<cycle>``.

    Returns:
        The matching timing bar domain, or `None` if the empty string is
            passed (no selector).

    Raises:
        ValueError if the timing selector string is ill-formatted or the
            timing domain isn't known.
    """
    if not user:
        return None
    try:
        domain, user, _cycle = user.split(".")
    except ValueError:
        raise ValueError(f"expected format <domain>.USER.<cycle>: {user!r}") from None
    if user.upper() != "USER":
        raise ValueError(f"middle of timing selector must be 'USER': {user!r}")
    try:
        return TimingBarDomain[domain]
    except KeyError:
        raise ValueError(f"unknown timing domain: {user!r}") from None


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
    domain. The only way for this function to return `None` is by
    passing `~cernml.coi.Machine.NO_MACHINE`.
    """
    return {
        coi.Machine.LINAC_2: LsaSelectorAccelerator.PSB,
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


def lsa_accelerator_to_server(accelerator: LsaSelectorAccelerator) -> str:
    """Return the LSA server to contact for a given accelerator.

    This mapping never fails.
    """
    return accelerator.name.lower()


def lsa_server_to_accelerator(server: str) -> t.Optional[LsaSelectorAccelerator]:
    """Return the accelerator most closely linked to the given LSA server.

    Note that the mapping neither injective nor surjective: some
    accelerators are associated with more than one LSA server and some
    servers are not associated with any accelerator at all.
    """
    return {
        "next_inca_ps": LsaSelectorAccelerator.PS,
        "ad": LsaSelectorAccelerator.AD,
        "ps": LsaSelectorAccelerator.PS,
        "lhc": LsaSelectorAccelerator.LHC,
        "testbed_ps": LsaSelectorAccelerator.PS,
        "awake": LsaSelectorAccelerator.AWAKE,
        "elena": LsaSelectorAccelerator.ELENA,
        "leir": LsaSelectorAccelerator.LEIR,
        "next_inca_psb": LsaSelectorAccelerator.PSB,
        "sps": LsaSelectorAccelerator.SPS,
        "isolde": LsaSelectorAccelerator.ISOLDE,
        "testbed_lhc": LsaSelectorAccelerator.LHC,
        "psb": LsaSelectorAccelerator.PSB,
        "ctf": LsaSelectorAccelerator.CTF,
        "north": LsaSelectorAccelerator.NORTH,
    }.get(server.lower())


def lsa_server_to_machine(server: str) -> t.Optional[coi.Machine]:
    """Return the machine most closely linked to the giving timing domain.

    Note that the mapping is very arbitrary: not every machine is
    returned, some machines are returned for multiple servers, and some
    servers don't have an associated machine.
    """
    # Special-case: We already know that CTF (CLiC Test Facility) is an
    # LSA server that the COI don't support yet.
    server = server.lower()
    if server == "ctf":
        raise KeyError(server)
    return {
        "next_inca_ps": coi.Machine.PS,
        "ad": coi.Machine.AD,
        "ps": coi.Machine.PS,
        "lhc": coi.Machine.LHC,
        "testbed_ps": coi.Machine.PS,
        "awake": coi.Machine.AWAKE,
        "elena": coi.Machine.ELENA,
        "leir": coi.Machine.LEIR,
        "next_inca_psb": coi.Machine.PSB,
        "sps": coi.Machine.SPS,
        "isolde": coi.Machine.ISOLDE,
        "testbed_lhc": coi.Machine.LHC,
        "psb": coi.Machine.PSB,
    }.get(server.lower())
