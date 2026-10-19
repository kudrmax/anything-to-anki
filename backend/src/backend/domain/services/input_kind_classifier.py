from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.value_objects.input_kind import InputKind

if TYPE_CHECKING:
    from backend.domain.entities.token_data import TokenData

ROOT_DEP = "ROOT"
SUBJECT_DEPS = frozenset({"nsubj", "nsubjpass", "csubj", "csubjpass", "expl"})
# spaCy reads many noun queries as clauses: "modal | verbs for advice", "animals | sounds".
# A subject counts only when the clause is unmistakable: a pronoun or "there" ("She smiled",
# "There is a cat"), a noun with a determiner ("The plan fell through", "Her hair was…"),
# an auxiliary ("Dirt had accumulated"), a past tense ("Prices rose sharply"), a linking verb
# ("Effort is the real lever") or a verb with an object or an adverb ("Slowness makes room",
# "People adapt quickly"): a bare preposition after the "verb" is how noun queries get misread.
PRONOUN_POS = "PRON"
LINKING_VERB_POS = "AUX"
EXPLETIVE_DEP = "expl"
DETERMINER_DEPS = frozenset({"det", "poss"})
CLAUSE_MARKER_DEPS = frozenset({
    "aux", "auxpass",
    "dobj", "advmod", "acomp", "attr", "xcomp", "ccomp", "prt", "npadvmod", "oprd", "dative",
})
PAST_TENSE_TAG = "VBD"
# "soldiers live by…" agrees as a clause: a plural noun with a plain present verb, and the line
# goes on after the verb. A misread noun query gets the "-s" form instead ("modal | verbs",
# "animals | sounds") or ends on the verb ("sounds animals make"), so it stays a query.
PLURAL_NOUN_TAG = "NNS"
PLAIN_PRESENT_TAG = "VBP"
SENTENCE_END_MARKS = frozenset({".", "!", "?", "…"})
CLOSING_QUOTES = frozenset({'"', "'", "”", "’", "»", ")"})
# Without a subject a line is a phrase only when it ends like a sentence and is long enough:
# "Get out of here!" is a phrase, "Help!" and "Thanks." are too short to learn a target from.
MIN_PHRASE_WORDS = 3
# Nobody types a topic this long: "how to complain about a noisy neighbour" is seven words.
MAX_TOPIC_WORDS = 8


class InputKindClassifier:
    """Tells a phrase from a topic in one English sentence typed on the Add screen.

    A phrase is a statement: its main predicate clearly has a subject, it ends like a sentence,
    or it is longer than any topic. A topic is a query: a word, a word group, an area or
    a situation ("make a decision", "phrasal verbs with get"), short, no subject, no full stop.
    """

    def classify(self, tokens: list[TokenData]) -> InputKind:
        words = sum(1 for token in tokens if not token.is_punct)
        if words > MAX_TOPIC_WORDS or self._has_clear_clause(tokens):
            return InputKind.PHRASE
        if self._ends_like_a_sentence(tokens) and words >= MIN_PHRASE_WORDS:
            return InputKind.PHRASE
        return InputKind.TOPIC

    @classmethod
    def _has_clear_clause(cls, tokens: list[TokenData]) -> bool:
        by_index = {token.index: token for token in tokens}
        roots = (token for token in tokens if token.dep == ROOT_DEP)
        return any(cls._is_clear_clause(root, by_index) for root in roots)

    @classmethod
    def _is_clear_clause(cls, root: TokenData, by_index: dict[int, TokenData]) -> bool:
        children = [by_index[i] for i in root.children_indices if i in by_index]
        subjects = [child for child in children if child.dep in SUBJECT_DEPS]
        if not subjects:
            return False
        if root.tag == PAST_TENSE_TAG or root.pos == LINKING_VERB_POS:
            return True
        if any(child.dep in CLAUSE_MARKER_DEPS for child in children):
            return True
        if cls._agrees_and_goes_on(root, subjects, children):
            return True
        return any(cls._is_clear_subject(subject, by_index) for subject in subjects)

    @staticmethod
    def _agrees_and_goes_on(
        root: TokenData, subjects: list[TokenData], children: list[TokenData],
    ) -> bool:
        agrees = (
            root.tag == PLAIN_PRESENT_TAG
            and len(subjects) == 1
            and subjects[0].tag == PLURAL_NOUN_TAG
        )
        return agrees and any(child.index > root.index for child in children)

    @staticmethod
    def _is_clear_subject(subject: TokenData, by_index: dict[int, TokenData]) -> bool:
        if subject.pos == PRONOUN_POS or subject.dep == EXPLETIVE_DEP:
            return True
        modifiers = (by_index[i] for i in subject.children_indices if i in by_index)
        return any(modifier.dep in DETERMINER_DEPS for modifier in modifiers)

    @staticmethod
    def _ends_like_a_sentence(tokens: list[TokenData]) -> bool:
        tail = [token.text for token in tokens if token.text.strip()]
        while tail and tail[-1] in CLOSING_QUOTES:
            tail.pop()
        return bool(tail) and tail[-1][-1] in SENTENCE_END_MARKS
