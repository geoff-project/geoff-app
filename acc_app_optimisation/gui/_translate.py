"""Translate accelerator names between various domains."""

import typing as t

from accwidgets.lsa_selector import LsaSelectorAccelerator
from accwidgets.timing_bar import TimingBarDomain
from cernml import coi
from pylogbook import NamedActivity


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
