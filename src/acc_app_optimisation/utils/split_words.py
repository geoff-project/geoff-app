# SPDX-FileCopyrightText: 2020-2023 CERN
# SPDX-FileCopyrightText: 2023 GSI Helmholtzzentrum für Schwerionenforschung
# SPDX-FileNotice: All rights not expressly granted are reserved.
#
# SPDX-License-Identifier: GPL-3.0-or-later OR EUPL-1.2+

"""Provide `split_words_and_spaces()`."""

import typing as t


class Token(t.NamedTuple):
    """Item type of iterator returned by `split_words_and_spaces()`."""

    text: str
    begin: int
    end: int

    def isspace(self) -> bool:
        """Return True if the text contains only whitespace."""
        return self.text.isspace()


def split_words_and_spaces(text: str) -> t.Iterator[Token]:
    """Return an iterator over words and spaces in the given text.

    The iterator alternates between `Token`s that contain only
    non-whitespace characters and `Token`s that only contain whitespace
    characters.

        >>> for token in split_words_and_spaces('  A BC \n D '):
        ...     print(token)
        Token(text='  ', begin=0, end=2)
        Token(text='A', begin=2, end=3)
        Token(text=' ', begin=3, end=4)
        Token(text='BC', begin=4, end=6)
        Token(text=' \n ', begin=6, end=9)
        Token(text='D', begin=9, end=10)
        Token(text=' ', begin=10, end=11)
    """
    # Split string into parts that may contain leading, but no trailing
    # whitespace. Yield first the whitespace, then the word.
    span_begin = span_end = 0
    for word in text.split():
        span_begin = span_end
        word_begin = text.find(word, span_end)
        span_end = word_begin + len(word)
        if span_begin != word_begin:
            yield Token(text[span_begin:word_begin], span_begin, word_begin)
        yield Token(word, word_begin, span_end)
    # Handle trailing whitespace.
    if span_end != len(text):
        yield Token(text[span_end:], span_end, len(text))
