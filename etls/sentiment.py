#!/usr/bin/env python
"""Twitter collector"""

from typing import Optional, Dict, Mapping

import os
import re
from collections import defaultdict

import pandas as pd
import preprocessor
preprocessor.set_options(
    preprocessor.OPT.URL,  #pylint: disable=no-member
    preprocessor.OPT.MENTION,  #pylint: disable=no-member
    preprocessor.OPT.RESERVED,  #pylint: disable=no-member
    preprocessor.OPT.NUMBER  #pylint: disable=no-member
)


def load_mispell(path: str) -> Dict[str, Dict[str, str]]:
    """Load mispell dictionary"""
    data: Mapping[str, Dict[str, str]] = defaultdict(dict)
    csv = pd.read_csv(path)
    # rows are 'lang', 'wrong', 'right'
    for row in csv.values.tolist():
        data[row[0]][row[1]] = row[2]
    return dict(data)


class Api:
    #pylint: disable=too-few-public-methods
    """Sentiment API v0 alpha 1 encapsulation"""
    REPEATED_WORDS_RE = re.compile(r'(.)\1{2,}')
    HASHTAGS_RE = re.compile(r'#(\S+)')
    LAUGH_RE = [
        re.compile(r'\b[haHA]{3,}\b'),
        re.compile(r'\b[heHE]{3,}\b'),
        re.compile(r'\b[hiHI]{3,}\b'),
        re.compile(r'\b[hoHO]{3,}\b'),
        re.compile(r'\b[huHU]{3,}\b'),
        re.compile(r'\b[jaJA]{3,}\b'),
        re.compile(r'\b[jeJE]{3,}\b'),
        re.compile(r'\b[jiJI]{3,}\b'),
        re.compile(r'\b[joJO]{3,}\b'),
        re.compile(r'\b[juJU]{3,}\b'),
    ]
    MISPELL_RE = load_mispell('mispell.csv')

    def __init__(self,
                 sentiment_url: Optional[str] = None,
                 sentiment_token: Optional[str] = None):
        self.sentiment_url = sentiment_url or os.getenv('SENTIMENT_URL')
        self.sentiment_token = sentiment_token or os.getenv('SENTIMENT_TOKEN')

    @staticmethod
    def clean_tweet(lang: str, tweet: str) -> str:
        """Clean a tweet before trying to analyze it"""
        # Clean URLs, Mentions, Reserved words and Numbers
        cleaned = preprocessor.clean(tweet)
        # Remove repeated letters
        cleaned = Api.REPEATED_WORDS_RE.sub(r'\1\1', cleaned)
        # Remove '#' from hashtags
        cleaned = Api.HASHTAGS_RE.sub(r'\1', cleaned)
        # Replace all kinds of laughter with "haha"
        for l_re in Api.LAUGH_RE:
            # Use capital letters so that spell checker will not
            # try to correct
            cleaned = l_re.sub('HAHA', cleaned)
        mispell = Api.MISPELL_RE.get(lang, None)
        if mispell is not None:
            for wrong, right in mispell.items():
                cleaned = cleaned.replace(wrong, right)
        mispell_all = Api.MISPELL_RE.get('all', None)
        if mispell_all is not None:
            for wrong, right in mispell_all.items():
                cleaned = cleaned.replace(wrong, right)
        return cleaned
