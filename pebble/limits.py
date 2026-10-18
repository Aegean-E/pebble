"""Resource limits that keep v1 predictable on any host.

They are small enough to explain in one error and large enough for real scripts: call depth,
integer exponent, integer size, range length and sequence length.
"""

MAX_CALL_DEPTH = 100
MAX_EXPONENT = 10_000
MAX_INT_DIGITS = 4_000
MAX_INT_BITS = 13_280
MAX_RANGE_LENGTH = 1_000_000
MAX_SEQUENCE_LENGTH = 1_000_000
