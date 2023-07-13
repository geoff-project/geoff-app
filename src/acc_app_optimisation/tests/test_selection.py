# SPDX-FileCopyrightText: 2020-2023 CERN
# SPDX-FileCopyrightText: 2023 GSI Helmholtzzentrum für Schwerionenforschung
# SPDX-FileNotice: All rights not expressly granted are reserved.
#
# SPDX-License-Identifier: GPL-3.0-or-later OR EUPL-1.2+

# pylint: disable = missing-function-docstring
# pylint: disable = missing-class-docstring
# pylint: disable = import-outside-toplevel
# pylint: disable = redefined-outer-name

"""Tests for `acc_app_optimisation.gui.InitialSelection`."""

import itertools
import typing as t

import pytest
from cernml.coi import Machine

from acc_app_optimisation.translate import InitialSelection

# Every tuple in this list describes one set of `coi.Machine`, timing
# selectors and LSA servers that correspond to each other. There are
# some complications:
# - the empty timing selector `""` appears in multiple tuples;
# - the empty timing selector `""` is compatible with everything;
# - `NO_MACHINE` is compatible with all LSA servers;
# - the generic LSA servers (NEXT, …) are compatible with everything;
GROUPS = [
    (
        "NO_MACHINE",
        "",
        {"next", "next_inca", "gpn", "dev", "local", "integration", "testbed"},
    ),
    ({"LINAC_2", "LINAC_4", "PSB"}, "PSB.USER.ALL", "psb"),
    ({"LINAC_3", "LEIR"}, "LEI.USER.ALL", "leir"),
    ("PS", "CPS.USER.ALL", {"next_inca_ps", "ps", "testbed_ps"}),
    ("SPS", "SPS.USER.ALL", "sps"),
    ("AWAKE", "", "awake"),
    ("LHC", "LHC.USER.ALL", {"lhc", "testbed_lhc"}),
    ("ISOLDE", "", "isolde"),
    ("AD", "ADE.USER.ALL", "ad"),
    ("ELENA", "LNA.USER.ALL", "elena"),
]

ALL_MISMATCHED_GROUPS = [
    group for group in itertools.product(*zip(*GROUPS)) if group not in GROUPS
]


def test_default_selection() -> None:
    selection = InitialSelection(None, None, None)
    assert selection.machine == Machine.NO_MACHINE
    assert selection.user == ""
    assert selection.lsa_server == "gpn"


def test_user_sct_is_not_usable() -> None:
    with pytest.raises(ValueError, match="no machine found for timing domain 'SCT'"):
        InitialSelection(None, "SCT.USER.ALL", None)
    with pytest.raises(ValueError, match="no machine found for timing domain 'SCT'"):
        InitialSelection(None, "SCT.USER.ALL", "sps")
    with pytest.raises(ValueError, match="selector is in domain 'SCT', but machine"):
        InitialSelection("SPS", "SCT.USER.ALL", None)


def test_server_ctf_is_not_usable() -> None:
    with pytest.raises(ValueError, match="no machine found for LSA server 'CTF'"):
        InitialSelection(None, None, "ctf")
    with pytest.raises(ValueError, match="implies LSA database 'SPS', but 'CTF'"):
        InitialSelection("SPS", None, "ctf")
    with pytest.raises(ValueError, match="implies LSA database 'SPS', but 'CTF'"):
        InitialSelection(None, "SPS.USER.ALL", "ctf")


def _flatten_groups(*groups: t.Union[str, t.Set[str]]) -> t.Iterator[t.Tuple[str, ...]]:
    """Flatten the sets in `GROUPS`.

    Example:

        >>> sorted(_flatten_groups("a", "b"))
        [('a', 'b')]
        >>> sorted(_flatten_groups("a", {"b", "c"}))
        [('a', 'b'), ('a', 'c')]
        >>> sorted(_flatten_groups({"a", "c"}, "b"))
        [('a', 'b'), ('c', 'b')]
        >>> sorted(_flatten_groups({"a", "b"}, {"c", "d"}))
        [('a', 'c'), ('a', 'd'), ('b', 'c'), ('b', 'd')]

    The function also works with just one argument:

        >>> sorted(_flatten_groups("abcde"))
        [('abcde',)]
        >>> sorted(_flatten_groups({"abcde", "defgh"}))
        [('abcde',), ('defgh',)]
    """
    yield from itertools.product(
        *(
            [item_or_set] if isinstance(item_or_set, str) else item_or_set
            for item_or_set in groups
        )
    )


@pytest.mark.parametrize("machines,users,lsa_servers", GROUPS)
def test_coherent_results(
    machines: t.Union[str, t.Set[str]],
    users: t.Union[str, t.Set[str]],
    lsa_servers: t.Union[str, t.Set[str]],
) -> None:
    for machine, user, lsa_server in _flatten_groups(machines, users, lsa_servers):
        selection = InitialSelection(machine, user, lsa_server)
        assert selection.machine.name == machine
        assert selection.user == user
        assert selection.lsa_server == lsa_server


def _matches_str_or_set(result: str, expected: t.Union[str, t.Set[str]]) -> bool:
    return (result == expected) if isinstance(expected, str) else (result in expected)


@pytest.mark.parametrize("machines,_users,lsa_servers", GROUPS)
def test_only_machine_passed(
    machines: t.Union[str, t.Set[str]],
    _users: t.Union[str, t.Set[str]],
    lsa_servers: t.Union[str, t.Set[str]],
) -> None:
    for (machine,) in _flatten_groups(machines):
        selection = InitialSelection(machine, None, None)
        assert selection.machine.name == machine
        assert selection.user == ""
        assert _matches_str_or_set(selection.lsa_server, lsa_servers)


@pytest.mark.parametrize("machines,users,lsa_servers", GROUPS)
def test_only_user_passed(
    machines: t.Union[str, t.Set[str]],
    users: t.Union[str, t.Set[str]],
    lsa_servers: t.Union[str, t.Set[str]],
) -> None:
    assert isinstance(users, str)
    user = users
    if user == "" and machines != Machine.NO_MACHINE:
        # This test cannot and should not succeed -- it is an artifact
        # of how we've structured our test data (the `GROUPS` global).
        return
    selection = InitialSelection(None, user, None)
    assert _matches_str_or_set(selection.machine.name, machines)
    assert selection.user == user
    assert _matches_str_or_set(selection.lsa_server, lsa_servers)


@pytest.mark.parametrize("machines,_users,lsa_servers", GROUPS)
def test_only_lsa_server_passed(
    machines: t.Union[str, t.Set[str]],
    _users: t.Union[str, t.Set[str]],
    lsa_servers: t.Union[str, t.Set[str]],
) -> None:
    for (lsa_server,) in _flatten_groups(lsa_servers):
        selection = InitialSelection(None, None, lsa_server)
        assert _matches_str_or_set(selection.machine.name, machines)
        assert selection.user == ""
        assert selection.lsa_server == lsa_server


def _group_compatible(
    machines: t.Union[str, t.Set[str]],
    users: t.Union[str, t.Set[str]],
    lsa_servers: t.Union[str, t.Set[str]],
) -> bool:
    """Return if a mismatched group exceptionally passes.

    `ALL_MISMATCHED_GROUPS` is a list of all combinations of
    machine/user/server that *don't* line up as in `GROUPS`. However,
    some are compatible anyway. For example, the empty selection ``""``
    can be used with any machine.

    This returns True if a given group lines up to be compatible with
    each other due to these exceptional rules. Otherwise, this returns
    False.
    """
    if machines == "NO_MACHINE":
        # NO_MACHINE is compatible with all LSA servers, but
        # incompatible with any timing selector that isn't the empty
        # string.
        return users == ""
    # All machines are compatible with the generic LSA servers and
    # with no chosen timing selector (i.e. the empty string).
    if users == "" and _matches_str_or_set("gpn", lsa_servers):
        return True
    # With no chosen timing selector, check if the machine and the LSA
    # server line up.
    if users == "":
        return any(group[::2] == (machines, lsa_servers) for group in GROUPS)
    # With a generic LSA server chosen, check if the machine and the
    # timing selector line up.
    if _matches_str_or_set("gpn", lsa_servers):
        return any(group[:2] == (machines, users) for group in GROUPS)
    # All special cases checked, now they must really be mismatched.
    return False


@pytest.mark.parametrize("machines,users,lsa_servers", ALL_MISMATCHED_GROUPS)
def test_mismatched_args_fail(
    machines: t.Union[str, t.Set[str]],
    users: t.Union[str, t.Set[str]],
    lsa_servers: t.Union[str, t.Set[str]],
) -> None:
    if _group_compatible(machines, users, lsa_servers):
        for machine, user, lsa_server in _flatten_groups(machines, users, lsa_servers):
            selection = InitialSelection(machine, user, lsa_server)
            assert selection.machine.name == machine
            assert selection.user == user
            assert selection.lsa_server == lsa_server
    else:
        for machine, user, lsa_server in _flatten_groups(machines, users, lsa_servers):
            with pytest.raises(ValueError):
                InitialSelection(machine, user, lsa_server)
