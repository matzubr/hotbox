"""Rename many nodes at once: find / replace (text or regex), a name pattern with numbers, prefix, suffix, case."""
from __future__ import annotations

import re
from dataclasses import dataclass

import hou

INVALID = re.compile(r"[^A-Za-z0-9_.]")  # what Houdini doesn't take in a node name
CASES = ("Keep case", "lower", "UPPER")
ORDERS = ("Selection", "Top to bottom", "Left to right", "Name")


@dataclass
class Rule:
    """pattern: the new name, '{name}' = the name (after find / replace), '{type}' = the node type,
    '#' = the number ('###' = 001), empty = the name"""
    pattern: str = ""
    find: str = ""
    replace: str = ""
    regex: bool = False
    prefix: str = ""
    suffix: str = ""
    start: int = 1
    step: int = 1
    case: str = CASES[0]
    order: str = ORDERS[0]


def newName(name: str, type_name: str, index: int, rule: Rule) -> str:
    """The name the rule gives the index-th node; raises ValueError on a broken regex"""
    base = name
    if rule.find:
        if rule.regex:
            try:
                base = re.sub(rule.find, rule.replace, base)
            except re.error as e:
                raise ValueError(f"Find: {e}") from e
        else:
            base = base.replace(rule.find, rule.replace)
    if rule.pattern:
        number = rule.start + index * rule.step
        numbered = re.sub("#+", lambda m: str(number).zfill(len(m.group())), rule.pattern)
        base = numbered.replace("{name}", base).replace("{type}", type_name)
    base = rule.prefix + base + rule.suffix
    if rule.case == "lower":
        base = base.lower()
    elif rule.case == "UPPER":
        base = base.upper()
    return INVALID.sub("_", base)


def _natural(text: str):
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", text)]


def ordered(nodes, order: str) -> list:
    nodes = list(nodes)
    if order == "Top to bottom":
        return sorted(nodes, key=lambda n: (-n.position()[1], n.position()[0]))
    if order == "Left to right":
        return sorted(nodes, key=lambda n: (n.position()[0], -n.position()[1]))
    if order == "Name":
        return sorted(nodes, key=lambda n: _natural(n.name()))
    return nodes


@dataclass
class Change:
    node: object
    old: str
    new: str
    problem: str = ""


def plan(nodes, rule: Rule) -> list[Change]:
    """What each node becomes; a problem: empty name, the same name twice in one network, a name taken by a node
    that isn't renamed"""
    changes = []
    for index, node in enumerate(ordered(nodes, rule.order)):
        changes.append(Change(node, node.name(), newName(node.name(), node.type().name(), index, rule)))
    renamed = {c.node.path() for c in changes}
    by_parent: dict[str, list[Change]] = {}
    for change in changes:
        by_parent.setdefault(change.node.parent().path(), []).append(change)
    for siblings in by_parent.values():
        others = {n.name() for n in siblings[0].node.parent().children() if n.path() not in renamed}
        seen: dict[str, int] = {}
        for change in siblings:
            seen[change.new] = seen.get(change.new, 0) + 1
        for change in siblings:
            if not change.new:
                change.problem = "empty name"
            elif change.new[0].isdigit():
                change.problem = "starts with a digit"
            elif seen[change.new] > 1:
                change.problem = "same name twice"
            elif change.new in others:
                change.problem = "taken by another node"
    return changes


def apply(changes: list[Change]) -> int:
    """Rename (one undo); names swapped between the nodes work: temporary names first. Returns how many changed."""
    todo = [c for c in changes if c.new != c.old]
    if any(c.problem for c in todo):
        raise ValueError("Fix the names marked red first")
    with hou.undos.group("Rename nodes"):
        for k, change in enumerate(todo):
            change.node.setName(f"hotbox_rename_tmp_{k}", unique_name=True)
        for change in todo:
            change.node.setName(change.new)
    return len(todo)
