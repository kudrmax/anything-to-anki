"""One status model: a card's choice, the word's status and the learning timer are read and
written only by the files that hold the model. Everywhere else asks their predicates.

Outside `ALLOWED`, the backend may not:
- compare a choice or a status (the enums of the model, their sets, the fields that hold
  them, their stored columns or their stored strings);
- name the learning timer (`timer_due`, `LEARNING_KNOWN_AFTER_DAYS`);
- write a card's choice;
- move a choice from one card to another.

The web half of the guard is `frontends/web/src/architecture/statusModelGuard.test.ts`: it
reads the TypeScript types, so it knows which values are the card's.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

import pytest
from backend.application.dto.source_dtos import ShownStatus
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.card_choice import CardChoice, DecisionStatus, NoteKind
from backend.domain.value_objects.elsewhere import ElsewhereStatus
from backend.domain.value_objects.word_status import WordStatus

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend" / "src" / "backend"

# The files that hold the status model.
ALLOWED = frozenset({
    "domain/value_objects/card_choice.py",
    "domain/value_objects/learning_timer.py",
    "domain/services/decision_rules.py",
    "domain/services/card_view.py",
    "application/utils/decision_effects.py",
    # The knowledge snapshot: the scope and the per-lemma knowledge it hands out.
    "application/utils/knowledge_scope.py",
    "domain/value_objects/lemma_knowledge.py",
    # The persistence mapping: the stored columns, their SQL forms, and the one writer of
    # a word's choices and status.
    "infrastructure/persistence/models.py",
    "infrastructure/persistence/sqla_word_state_repository.py",
    "alembic/versions/0049_words_and_phrases.py",
    "alembic/versions/0050_binding_card_choice.py",
})
# Migrations before 0049 are shipped history: they are never edited again.
SHIPPED_MIGRATION = re.compile(r"alembic/versions/00(?:[0-3]\d|4[0-8])_")

MODEL_ENUMS = frozenset({
    "CardChoice", "NoteKind", "DecisionStatus", "WordStatus", "ElsewhereStatus",
    "ShownStatus", "CandidateSection", "Press", "Role", "Refusal", "Where", "Command", "Actor",
})
MODEL_SETS = frozenset({"CHOSEN_TO_LEARN", "DECISION_CHOICES"})
MODEL_FIELDS = frozenset({
    "choice", "word_status", "decision_status", "decision_choice", "decision_note",
    "note_kind", "section", "card_choice",
})
STORED_COLUMNS = frozenset({
    ("StoredCandidateModel", "status"), ("PhraseModel", "choice"),
    ("AnkiSyncedCardModel", "note_kind"), ("AnkiSyncedCardModel", "card_choice"),
})
MODEL_VALUES = frozenset(
    member.value
    for enum in (CardChoice, NoteKind, DecisionStatus, WordStatus, ElsewhereStatus,
                 ShownStatus, CandidateSection)
    for member in enum
)
# Bare locals that hold a choice or a status.
MODEL_LOCALS = frozenset({"choice", "status"})
TIMER_NAMES = frozenset({"timer_due", "LEARNING_KNOWN_AFTER_DAYS"})
TIMER_MODULE = "learning_timer"
SQL_MEMBERSHIP = frozenset({"in_", "not_in", "notin_", "is_", "is_not", "isnot"})
SQL_WRITES = frozenset({"values", "update", "insert", "execute", "bulk_update_mappings"})
RAW_CHOICE_WRITE = re.compile(r"\b(?:update|set)\b[^;]*\bchoice\b", re.IGNORECASE)


@dataclass(frozen=True)
class Offence:
    where: str
    rule: str
    code: str

    def __str__(self) -> str:
        return f"{self.where}: [{self.rule}] {self.code}"


class _ModelScan(ast.NodeVisitor):
    """The offences of one Python file."""

    def __init__(self, relative: str, tree: ast.Module) -> None:
        self._relative = relative
        self._enums = MODEL_ENUMS | _aliases_of_the_model_enums(tree)
        self._guarded_names = MODEL_SETS | _constants_of_the_model(tree, self._enums)
        self.offences: list[Offence] = []

    def _report(self, node: ast.AST, rule: str) -> None:
        line = getattr(node, "lineno", 0)
        self.offences.append(Offence(f"{self._relative}:{line}", rule, ast.unparse(node)[:120]))

    def _names_the_model(self, node: ast.AST) -> bool:
        for found in ast.walk(node):
            if isinstance(found, ast.Attribute) and isinstance(found.value, ast.Name) and (
                found.value.id in self._enums
                or (found.value.id, found.attr) in STORED_COLUMNS
            ):
                return True
            if isinstance(found, ast.Name) and found.id in self._guarded_names:
                return True
        return False

    def _holds_the_model(self, node: ast.AST) -> bool:
        """A field that holds a choice or a status, read off anything, or a bare local
        named so."""
        return any(
            (isinstance(found, ast.Attribute) and found.attr in MODEL_FIELDS)
            or (isinstance(found, ast.Name) and found.id in MODEL_LOCALS)
            for found in ast.walk(node)
        )

    def visit_Compare(self, node: ast.Compare) -> None:
        operands = [node.left, *node.comparators]
        presence = any(isinstance(o, ast.Constant) and o.value is None for o in operands)
        stored_string = any(
            text in MODEL_VALUES for o in operands for text in _texts(o)
        ) and any(_mentions_status_or_choice(o) for o in operands)
        if (
            self._names_the_model(node)
            or stored_string
            or (not presence and self._holds_the_model(node))
        ):
            self._report(node, "compares a choice or status")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if name in SQL_MEMBERSHIP and (
            self._names_the_model(node) or self._holds_the_model(func)
        ):
            self._report(node, "compares a choice or status")
        choice_kw = next((kw for kw in node.keywords if kw.arg == "choice"), None)
        if choice_kw is not None and (name == "replace" or name in SQL_WRITES):
            self._report(node, _write_or_move(choice_kw.value))
        if name == "with_cards":
            self._report(node, "moves a choice between cards")
        if name == "CardState" and _takes_another_cards_choice(node):
            self._report(node, "moves a choice between cards")
        if name == "setattr" and len(node.args) > 1 and _is_text(node.args[1], "choice"):
            self._report(node, "writes a choice")
        self.generic_visit(node)

    def _visit_targets(
        self, node: ast.AST, targets: list[ast.expr], value: ast.AST | None,
    ) -> None:
        for target in targets:
            if isinstance(target, ast.Attribute) and target.attr == "choice":
                self._report(node, _write_or_move(value))

    def visit_Assign(self, node: ast.Assign) -> None:
        self._visit_targets(node, node.targets, node.value)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self._visit_targets(node, [node.target], node.value)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self._visit_targets(node, [node.target], node.value)
        self.generic_visit(node)

    def visit_Match(self, node: ast.Match) -> None:
        patterns = [case.pattern for case in node.cases]
        if (
            self._holds_the_model(node.subject)
            or self._names_the_model(node.subject)
            or any(self._names_the_model(pattern) for pattern in patterns)
            or (
                _mentions_status_or_choice(node.subject)
                and any(text in MODEL_VALUES for pattern in patterns for text in _texts(pattern))
            )
        ):
            self._report(node.subject, "compares a choice or status")
        self.generic_visit(node)

    def visit_Dict(self, node: ast.Dict) -> None:
        if any(key is not None and _is_text(key, "choice") for key in node.keys):
            self._report(node, "writes a choice")
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str) and RAW_CHOICE_WRITE.search(node.value):
            self._report(node, "writes a choice")

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in TIMER_NAMES:
            self._report(node, "reads the timer")

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr in TIMER_NAMES:
            self._report(node, "reads the timer")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        star_of_the_timer = (node.module or "").endswith(TIMER_MODULE) and any(
            alias.name == "*" for alias in node.names
        )
        if star_of_the_timer or any(alias.name in TIMER_NAMES for alias in node.names):
            self._report(node, "reads the timer")


def _aliases_of_the_model_enums(tree: ast.Module) -> frozenset[str]:
    """Other names a file gives the model's enums: `import ... as`, or `C = CardChoice` at
    any level."""
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            found.update(
                alias.asname for alias in node.names
                if alias.asname is not None and alias.name in MODEL_ENUMS
            )
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign) and isinstance(node.value, ast.Name)
            and node.value.id in MODEL_ENUMS | found
        ):
            found.update(t.id for t in node.targets if isinstance(t, ast.Name))
    return frozenset(found)


def _texts(node: ast.AST) -> list[str]:
    """The strings of a constant, or of a tuple, set or list of constants; of a match
    pattern too."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.Tuple | ast.Set | ast.List):
        return [text for element in node.elts for text in _texts(element)]
    if isinstance(node, ast.MatchValue):
        return _texts(node.value)
    if isinstance(node, ast.MatchOr):
        return [text for pattern in node.patterns for text in _texts(pattern)]
    return []


def _constants_of_the_model(tree: ast.Module, enums: frozenset[str]) -> frozenset[str]:
    """Names bound, at any level, to sets or values of the model, such as a local copy of
    CHOSEN_TO_LEARN."""
    found: set[str] = set()
    for statement in ast.walk(tree):
        if isinstance(statement, ast.Assign):
            targets, value = statement.targets, statement.value
        elif isinstance(statement, ast.AnnAssign) and statement.value is not None:
            targets, value = [statement.target], statement.value
        else:
            continue
        if isinstance(value, ast.Dict | ast.Call) and _is_a_table(value):
            continue
        mentions = any(
            (isinstance(n, ast.Name) and (n.id in MODEL_SETS or n.id in found))
            or (isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
                and n.value.id in enums)
            for n in ast.walk(value)
        )
        if mentions:
            found.update(t.id for t in targets if isinstance(t, ast.Name))
    return frozenset(found)


def _is_a_table(value: ast.AST) -> bool:
    """A mapping from the model's values to something else: rendering, not a rule."""
    return isinstance(value, ast.Dict) or (
        isinstance(value, ast.Call) and getattr(value.func, "id", "") == "MappingProxyType"
    )


def _mentions_status_or_choice(node: ast.AST) -> bool:
    return any(
        (isinstance(n, ast.Name) and ("status" in n.id or "choice" in n.id))
        or (isinstance(n, ast.Attribute) and ("status" in n.attr or "choice" in n.attr))
        for n in ast.walk(node)
    )


def _reads_a_choice(node: ast.AST) -> bool:
    return any(isinstance(n, ast.Attribute) and n.attr == "choice" for n in ast.walk(node))


def _takes_another_cards_choice(node: ast.Call) -> bool:
    """A card built with a choice read off something else than the card's own id comes
    from: `CardState(new_id, old.choice)`. `CardState(self.id, self.choice)` only reads."""
    args = {**dict(enumerate(node.args)), **{kw.arg: kw.value for kw in node.keywords}}
    card_id, choice = args.get(0, args.get("card_id")), args.get(1, args.get("choice"))
    if choice is None or not _reads_a_choice(choice):
        return False
    return card_id is None or _base_name(card_id) != _base_name(choice)


def _base_name(node: ast.AST) -> str | None:
    while isinstance(node, ast.Attribute | ast.Subscript | ast.Call):
        node = node.func if isinstance(node, ast.Call) else node.value
    return node.id if isinstance(node, ast.Name) else None


def _write_or_move(value: ast.AST | None) -> str:
    if value is not None and _reads_a_choice(value):
        return "moves a choice between cards"
    return "writes a choice"


def _is_text(node: ast.AST, text: str) -> bool:
    return isinstance(node, ast.Constant) and node.value == text


def backend_offences() -> list[Offence]:
    offences: list[Offence] = []
    for path in sorted(BACKEND_ROOT.rglob("*.py")):
        relative = path.relative_to(BACKEND_ROOT).as_posix()
        if relative in ALLOWED or SHIPPED_MIGRATION.match(relative):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        scan = _ModelScan(relative, tree)
        scan.visit(tree)
        offences.extend(scan.offences)
    return offences


@pytest.mark.unit
def test_only_the_status_model_compares_writes_or_times_choices() -> None:
    assert [str(o) for o in backend_offences()] == []


# --- the guard itself -------------------------------------------------------------------


def _scan(code: str) -> list[str]:
    tree = ast.parse(code)
    scan = _ModelScan("sample.py", tree)
    scan.visit(tree)
    return [o.rule for o in scan.offences]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("code", "rule"),
    [
        ("card.choice is CardChoice.SKIP", "compares a choice or status"),
        ("word.status in _CHOSEN", "compares a choice or status"),
        ("x = DecisionStatus(s) in CHOSEN_TO_LEARN", "compares a choice or status"),
        ("Model.status == 'learn'", "compares a choice or status"),
        ("StoredCandidateModel.status.in_(values)", "compares a choice or status"),
        ("PhraseModel.choice.in_(values)", "compares a choice or status"),
        ("row.section == other", "compares a choice or status"),
        ("export_kind(card) is NoteKind.CLOZE", "compares a choice or status"),
        ("due = timer_due(since, now)", "reads the timer"),
        ("from x import LEARNING_KNOWN_AFTER_DAYS", "reads the timer"),
        ("card.choice = CardChoice.LEARN", "writes a choice"),
        ("update(PhraseModel).values(choice='learn')", "writes a choice"),
        ("session.execute(text('UPDATE phrases SET choice = :c'))", "writes a choice"),
        ("rows.append({'id': 1, 'choice': 'learn'})", "writes a choice"),
        ("replace(new, choice=old.choice)", "moves a choice between cards"),
        ("CardState(new_id, old.choice)", "moves a choice between cards"),
        ("word.with_cards(card)", "moves a choice between cards"),
        ("match card.choice:\n    case _:\n        pass", "compares a choice or status"),
        ("match x:\n    case CardChoice.LEARN:\n        pass", "compares a choice or status"),
        ("match status:\n    case 'learn' | 'skip':\n        pass", "compares a choice or status"),
        ("w.status in ('learn', 'learning')", "compares a choice or status"),
        ("w.choice in {'skip'}", "compares a choice or status"),
        ("row.status in ['known']", "compares a choice or status"),
        ("choice is wanted", "compares a choice or status"),
        ("status == other", "compares a choice or status"),
        ("def f():\n    C = CardChoice\n    return x is C.SKIP", "compares a choice or status"),
        ("from m import WordStatus as W\nx is W.NEW", "compares a choice or status"),
        ("def f():\n    wanted = {CardChoice.LEARN}\n    return x in wanted",
         "compares a choice or status"),
        ("from backend.domain.value_objects.learning_timer import *", "reads the timer"),
    ],
)
def test_the_guard_finds(code: str, rule: str) -> None:
    source = f"_CHOSEN = tuple(CHOSEN_TO_LEARN)\n{code}\n"
    assert rule in _scan(source)


@pytest.mark.unit
@pytest.mark.parametrize(
    "code",
    [
        "label = LABELS[card.choice]",
        "TONE = {WordStatus.NEW: 'idle'}\ntone = TONE[status]",
        "card.binding is not None",
        "row.section is None",
        "job.status is JobStatus.RUNNING",
        "CardDTO(choice=view.choice)",
        "chosen_to_learn(word)",
        "CardState(self.id, self.choice, self.binding)",
        "match job.kind:\n    case 'audio':\n        pass",
        "status is None",
        "choice = LABELS[view.choice]",
        "w.kind in ('learn', 'known')",
        "from backend.domain.value_objects.learning_timer import known_on",
        "tone = TONES[(status, skipped)]",
    ],
)
def test_the_guard_lets_through(code: str) -> None:
    assert _scan(code) == []
