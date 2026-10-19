"""One status model: a card's choice, the word's status and the learning timer are read and
written only by the files that hold the model. Everywhere else asks their predicates.

Outside `ALLOWED`, the backend may not:
- compare a choice or a status (the enums of the model, their sets, the fields that hold
  them, their stored columns or their stored strings);
- name the learning timer (`timer_due`, `LEARNING_KNOWN_AFTER_DAYS`);
- write a card's choice;
- move a choice from one card to another.

The web may not compare a card's choice, status, section or the like with a value: that
is a rule. It may render them: map a value to a label or a tone, group or find cards by a
value it was given, and check whether the backend sent a value at all (`=== null`).
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
WEB_ROOT = REPO_ROOT / "frontends" / "web" / "src"

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
    "note_kind", "section",
})
STORED_COLUMNS = frozenset({
    ("StoredCandidateModel", "status"), ("PhraseModel", "choice"),
    ("AnkiSyncedCardModel", "note_kind"),
})
MODEL_VALUES = frozenset(
    member.value
    for enum in (CardChoice, NoteKind, DecisionStatus, WordStatus, ElsewhereStatus,
                 ShownStatus, CandidateSection)
    for member in enum
)
TIMER_NAMES = frozenset({"timer_due", "LEARNING_KNOWN_AFTER_DAYS"})
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
        self._guarded_names = MODEL_SETS | _module_constants_of_the_model(tree)
        self.offences: list[Offence] = []

    def _report(self, node: ast.AST, rule: str) -> None:
        line = getattr(node, "lineno", 0)
        self.offences.append(Offence(f"{self._relative}:{line}", rule, ast.unparse(node)[:120]))

    def _names_the_model(self, node: ast.AST) -> bool:
        for found in ast.walk(node):
            if isinstance(found, ast.Attribute) and isinstance(found.value, ast.Name) and (
                found.value.id in MODEL_ENUMS
                or (found.value.id, found.attr) in STORED_COLUMNS
            ):
                return True
            if isinstance(found, ast.Name) and found.id in self._guarded_names:
                return True
        return False

    def _holds_the_model(self, node: ast.AST) -> bool:
        """A field that holds a choice or a status, read off anything."""
        return any(
            isinstance(found, ast.Attribute) and found.attr in MODEL_FIELDS
            for found in ast.walk(node)
        )

    def visit_Compare(self, node: ast.Compare) -> None:
        operands = [node.left, *node.comparators]
        presence = any(isinstance(o, ast.Constant) and o.value is None for o in operands)
        stored_string = any(
            isinstance(o, ast.Constant) and isinstance(o.value, str) and o.value in MODEL_VALUES
            for o in operands
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
        if any(alias.name in TIMER_NAMES for alias in node.names):
            self._report(node, "reads the timer")


def _module_constants_of_the_model(tree: ast.Module) -> frozenset[str]:
    """Module-level names bound to sets or values of the model, such as a local copy of
    CHOSEN_TO_LEARN."""
    found: set[str] = set()
    for statement in tree.body:
        targets: list[ast.expr] = []
        if isinstance(statement, ast.Assign):
            targets = statement.targets
        elif isinstance(statement, ast.AnnAssign) and statement.value is not None:
            targets = [statement.target]
        value = getattr(statement, "value", None)
        if value is None or isinstance(value, ast.Dict | ast.Call) and _is_a_table(value):
            continue
        mentions = any(
            (isinstance(n, ast.Name) and (n.id in MODEL_SETS or n.id in found))
            or (isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
                and n.value.id in MODEL_ENUMS)
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


# --- the web ----------------------------------------------------------------------------

_WEB_SUFFIXES = frozenset({".ts", ".tsx"})
_CARD_FIELD = (
    r"(?:\??\.(?:choice|section|where|command|refused|note|pressed|button|word_status)"
    r"|\bshown\??\.status"
    r"|(?<![\w.])(?:choice|section|where|command|refused|note){shown_status})\b"
)
_VALUE = r"(?:'[^']*'|\"[^\"]*\"|`[^`]*`|\b[A-Z][A-Z0-9_]+\b(?![\[.(]))"
_EQUALS = r"\s*(?:===|!==|==|!=)\s*"
# `status` names the shown status only where it is destructured from a Shown.
_SHOWN_DESTRUCTURED = re.compile(r"\{[^}]*\bstatus\b[^}]*\}\s*:\s*Shown\b")
_SWITCH = re.compile(r"\bswitch\s*\(\s*[\w?.]*\.(?:choice|section|where|command|refused|note)\b")
_LITERAL_SET = re.compile(
    r"\[[^\]]*['\"][a-z_]+['\"][^\]]*\]\.includes\(\s*[\w?.]*\.(?:choice|section|where|status)\b",
)


def _web_rule(shown_status: bool) -> re.Pattern[str]:
    field = _CARD_FIELD.format(shown_status="|status" if shown_status else "")
    return re.compile(f"{field}{_EQUALS}{_VALUE}|{_VALUE}{_EQUALS}{field}")


def _is_web_source(path: Path) -> bool:
    return (
        path.suffix in _WEB_SUFFIXES
        and "node_modules" not in path.parts
        and ".test." not in path.name
        and path.stem != "reviewFixtures"
    )


def web_offences() -> list[Offence]:
    offences: list[Offence] = []
    for path in sorted(p for p in WEB_ROOT.rglob("*") if _is_web_source(p)):
        source = path.read_text(encoding="utf-8")
        rule = _web_rule(shown_status=bool(_SHOWN_DESTRUCTURED.search(source)))
        relative = path.relative_to(REPO_ROOT).as_posix()
        for number, line in enumerate(source.splitlines(), start=1):
            if rule.search(line) or _SWITCH.search(line) or _LITERAL_SET.search(line):
                offences.append(Offence(f"{relative}:{number}", "web rule", line.strip()))
    return offences


@pytest.mark.unit
def test_only_the_status_model_compares_writes_or_times_choices() -> None:
    assert [str(o) for o in backend_offences()] == []


@pytest.mark.unit
def test_the_web_renders_the_status_model_without_rules() -> None:
    assert [str(o) for o in web_offences()] == []


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
    ],
)
def test_the_guard_lets_through(code: str) -> None:
    assert _scan(code) == []


@pytest.mark.unit
@pytest.mark.parametrize(
    ("line", "shown_status", "found"),
    [
        ("if (c.section === 'ready') return", False, True),
        ("const open = c.shown.status !== 'new'", False, True),
        ("if (button.command === 'edit_cloze') open()", False, True),
        ("skipped && status === 'new'", True, True),
        ("skipped && status === 'new'", False, False),
        ("if (source.status === REVIEWED) done()", False, False),
        ("disabled={button.command === null}", False, False),
        ("cards.filter(c => c.section === section)", False, False),
        ("const tone = TONE[candidate.shown.status]", False, False),
        ("bootstrap?.status === 'ready'", False, False),
    ],
)
def test_the_web_guard(line: str, shown_status: bool, found: bool) -> None:
    assert bool(_web_rule(shown_status).search(line)) is found
