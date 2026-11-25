"""Compare validated builtin values using the pinned EvalPlus checker rules."""

import math

from numpy import allclose

SET_OUTPUT = frozenset({
    "similar_elements", "find_char_long", "common_in_nested_lists", "extract_singly",
    "larg_nnum", "intersection_array", "find_dissimilar", "Diff",
})
PRESENCE_OUTPUT = frozenset({"check_str", "text_match_three", "text_starta_endb"})


def floats(value):
    return type(value) is float or (
        type(value) in (tuple, list) and bool(value)
        and all(type(item) is float for item in value)
    )


class Comparator:
    """Keep the checker tolerance state for one ordered base or plus panel."""

    def __init__(self, dataset, entry, atol):
        self.dataset = dataset
        self.entry = entry
        self.atol = atol

    def compare(self, observed, expected, args_after):
        try:
            exact = observed == expected
            if self.dataset == "mbpp":
                exact = self.mbpp_rule(exact, observed, expected, args_after)
            elif self.entry == "find_zero":
                residual = sum(c * math.pow(observed, i) for i, c in enumerate(args_after[0]))
                return abs(residual) <= self.atol

            if self.atol == 0 and floats(expected):
                self.atol = 1e-6
            if exact or not self.atol:
                return bool(exact)
            if type(observed) is not type(expected):
                return False
            if type(expected) in (list, tuple) and len(observed) != len(expected):
                return False
            return bool(allclose(observed, expected, rtol=1e-7, atol=self.atol))
        except (TypeError, ArithmeticError, ValueError, IndexError):
            return False

    def mbpp_rule(self, exact, observed, expected, args):
        if self.entry == "are_equivalent":
            return True
        if self.entry == "sum_div":
            return exact or observed == 0
        if self.entry == "surface_Area":
            if exact:
                return True
            edge, height = args
            slant = math.sqrt((edge / 2) ** 2 + height ** 2)
            return abs(observed - round(edge ** 2 + 4 * (edge * slant) / 2)) <= self.atol
        if self.entry == "digit_distance_nums":
            if exact:
                return True
            left, right = map(str, args)
            width = max(len(left), len(right))
            return observed == sum(abs(int(a) - int(b))
                                   for a, b in zip(left.zfill(width), right.zfill(width)))
        if self.entry in SET_OUTPUT:
            return set(observed) == set(expected)
        if self.entry in PRESENCE_OUTPUT:
            return exact if type(observed) is bool else expected == (observed is not None)
        return exact
