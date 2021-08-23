#!/usr/bin/env python
"""Twitter collector"""

from typing import Dict, Mapping, Set

import re
from collections import defaultdict
import datetime

import pandas as pd
import preprocessor
import sentiment

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


def load_stopwords(path: str) -> Set[str]:
    """Load stop words dictionary"""
    data: Set[str] = set()
    csv = pd.read_csv(path)
    # rows are 'lang', 'word'
    for row in csv.values.tolist():
        data.add(row[0])
    return data


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
    STOP_WORDS = load_stopwords('stopwords.csv')

    def __init__(self, model_name: str, model_cache_dir: str):
        #  sentiment_url: Optional[str] = None,
        #  sentiment_token: Optional[str] = None):
        self.pipeline = sentiment.Pipeline(model_name,
                                           cache_dir=model_cache_dir)
        self.spellcheck = sentiment.Spellcheck()
        # self.sentiment_url = sentiment_url or os.getenv('SENTIMENT_URL')
        # self.sentiment_token = sentiment_token or os.getenv('SENTIMENT_TOKEN')
        # self.headers = {'Authorization': f'Bearer {self.sentiment_token}'}

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

    @staticmethod
    def clean(tweets: pd.DataFrame) -> pd.DataFrame:
        """uses 'lang' and 'text' to generate 'clean'"""
        spacy_langs = ('es', 'en', 'de', 'fr', 'it', 'pt', 'gl', 'ca')
        # Drop retweets
        tweets = tweets[~tweets['text'].str.startswith('RT ')]
        # Drop unsupported languages
        tweets = tweets[tweets['lang'].isin(spacy_langs)]
        # Reindex dataframe
        if len(tweets) > 0:
            tweets = tweets.reset_index().drop('index', axis=1)
            tweets['clean'] = tweets.apply(
                lambda row: {
                    'lang': row['lang'],
                    'text': Api.clean_tweet(row['lang'], row['text']),
                },
                axis=1)
        return tweets

    def sentiment(self, cleaned: pd.DataFrame) -> pd.DataFrame:
        """Uses 'clean' to generate 'score'"""
        sentences = cleaned['clean'].tolist()
        # url = f'{self.sentiment_url}/api/sentiment'
        # body = {'sentences': sentences }
        scores = self.pipeline(list(item['text'] for item in sentences))
        if scores:
            # with requests.post(url, headers=self.headers, json=body) as resp:
            # scores = resp.json()['scores']
            # Transform score into polarity (-1, 0, 1)
            average = (sum(i * x for i, x in enumerate(item, 1))
                       for item in scores)
            score = tuple(1 if s >= 3.66 else -1 if s < 2.33 else 0
                          for s in average)
            cleaned = cleaned.assign(score=score)
        return cleaned

    def terms(self, cleaned: pd.DataFrame) -> pd.DataFrame:
        """Uses 'clean' to generate 'terms', 'termcount'"""
        sentences = cleaned['clean'].tolist()
        # url = f'{self.sentiment_url}/api/terms'
        # body = {'sentences': sentences }
        terms = list(self.spellcheck(sentences))
        if terms:
            #with requests.post(url, headers=self.headers, json=body) as resp:
            # terms = resp.json()['terms']
            cleaned = cleaned.assign(terms=terms)
        # Turn dict o terms into item list
        cleaned['terms'] = cleaned['terms'].apply(lambda d: tuple({
            'term': k,
            'repeat': v
        } for k, v in d.items() if k not in Api.STOP_WORDS))
        # Remove tweets without terms
        cleaned['termcount'] = cleaned['terms'].map(len)
        cleaned = cleaned[cleaned['termcount'] > 0].reset_index()
        return cleaned

    @staticmethod
    def round_time(cleaned: pd.DataFrame) -> pd.DataFrame:
        """Uses 'created_at' to generate:
        - 'day': Time of message rounded to hour below.
        """
        # Round to the closest hour
        cleaned['day'] = pd.to_datetime(
            cleaned['created_at']).apply(lambda dt: datetime.datetime(
                dt.year, dt.month, dt.day, dt.hour, 0))
        return cleaned

    @staticmethod
    def normalize(cleaned: pd.DataFrame) -> pd.DataFrame:
        """Uses 'impact', 'score' and 'termcount'
        to generate:
        - 'pos': Positive impacts including the term.
        - 'neg': Negative impacts including the term.
        - 'neutral': Neutral impacts including the term.
        - 'impact_per_term': impact / number of terms in message.
        - 'pos_per_term': pos / number of terms in message.
        - 'neg_per_term': neg / number of terms in message.
        - 'neutral_per_term': Neutral / number of terms in message.
        """
        # Normalize impact dividing by number of terms
        cleaned['impact_per_term'] = cleaned['impact'] / cleaned['termcount']
        # Split impact amongst pos, neg and neutral
        details = {
            'pos': ('impact', 1),
            'neg': ('impact', -1),
            'neutral': ('impact', 0),
            'pos_per_term': ('impact_per_term', 1),
            'neg_per_term': ('impact_per_term', -1),
            'neutral_per_term': ('impact_per_term', 0),
        }
        for detail, (impact, score) in details.items():
            cleaned[detail] = cleaned[impact] * (cleaned['score'] == score)
        # Explode terms, one per line
        cleaned = cleaned.explode('terms')
        # Pivot the terms cell into two columns,
        # and concatenate with the terms series
        pivot = cleaned['terms'].apply(pd.Series)
        cleaned = pd.concat([cleaned.drop(['terms'], axis=1), pivot], axis=1)
        # Aggregate by unique fields (day, lang, term)
        unique = ['day', 'lang', 'term']
        agg = {
            'impact': 'sum',
            'impact_per_term': 'sum',
            'repeat': 'sum',
            'termcount': 'sum'
        }
        agg.update({k: 'sum' for k in details})
        return cleaned.groupby(unique).agg(agg).reset_index()
