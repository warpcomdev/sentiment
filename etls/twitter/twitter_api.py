#!/usr/bin/env python
"""Twitter API v2 utilities"""

from typing import Sequence, Optional, Mapping, Dict, Any, Generator, Iterable

import os
import itertools
from datetime import date, datetime, timedelta
import logging

import pandas as pd
import requests
from ratelimit import limits, RateLimitException
from backoff import on_exception, expo


# pylint: disable=too-few-public-methods
class Api:
    """Twitter API v2 encapsulation"""
    def __init__(self,
                 api_url: Optional[str] = None,
                 api_key: Optional[str] = None,
                 api_secret_key: Optional[str] = None,
                 bearer_token: Optional[str] = None):
        """Build credentials wrapper"""
        self.api_url = api_url or 'https://api.twitter.com/2/'
        self.api_key = api_key or os.getenv('TWITTER_API_KEY')
        self.api_secret_key = api_secret_key or os.getenv(
            'TWITTER_API_SECRET_KEY')
        self.bearer_token = bearer_token or os.getenv('TWITTER_BEARER_TOKEN')
        self.headers = {
            'Authorization': f'Bearer {self.bearer_token}',
        }

    # Twitter API limits to 300 requests per 15 minutes
    @on_exception(expo, RateLimitException, max_tries=8)
    @limits(calls=300, period=900)
    def query(self, path: str, params: Mapping[str, str]) -> Any:
        """Perform HTTP query and return json reply"""
        url = f'{self.api_url}{path}'
        logging.info("Api::query::url = '%s'", url)
        with requests.get(url, headers=self.headers, params=params) as resp:
            if resp.status_code != 200:
                raise ValueError("Api::query got response [%s] %s" %
                                 (resp.status_code, resp.text))
            return resp.json()


class Reference:
    """
    Represents a reference from a 'data' field to an 'include' table.

    v2 API replies include references amongst the data they return.
    a reference is an ID that points to an entry belonging to the 'includes'
    section of the reply.

    E.g. an v2 reply for a tweet search query can be like:
    {
        'data': [
            {'text': 'This is the tweet', 'geo': { 'place_id': 19384723 } }
        ],
        'includes': {
            'places': [
                {'place_id': 19384723, 'country_code': 'es' }
            ]
        }
    }

    In the reply above, data.geo.place_id is a reference to a 'place'
    object included in the 'includes' section.

    We will usually want to transform this representation into a
    tabular format that can be loaded into a pandas DataFrame, e.g
    [
        {'text': 'This is the tweet', 'place_cc': 'es' }
    ]

    In order to do so, we represent each reference with two pieces
    of information:

    - The path to the attribute in the 'data' object, e.g.
      ['geo', 'place_id'])

    - A mapping of input attrib to output column, e.g.
      { 'country_code': 'place_cc' }
    """
    def __init__(self, path: Sequence[str], fields: Mapping[str, str]):
        self.path = path
        self.fields = fields

    def join(self, item: Any, catalog: Mapping[str, Any]) -> Any:
        """Join attributes from catalog into the item"""
        key = item
        # Get the key by drilling down the path
        for field in self.path:
            key = key.get(field, None)
            if key is None:
                return item
        # Get the referenced mapping from the catalog
        val = catalog.get(key, None)
        if val is None:
            return item
        # Copy catalog fields to item
        for src, dst in self.fields.items():
            item[dst] = val.get(src, None)
        return item

    def output(self) -> Sequence[str]:
        """Return list of output field names"""
        return tuple(self.fields.values())


class Model:
    """Base Model class for tweet API v2 Replies"""
    def __init__(self, columns: Sequence[str], packed: Mapping[str,
                                                               Sequence[str]],
                 referenced: Mapping[str, Reference]):
        """Build Model with the following info:
        - List of data attributes
        - List of packed attributes (attributes inside an object in data)
        - List of referenced attributes
        """
        self.columns = tuple(
            itertools.chain(
                columns, itertools.chain(*(packed.values())),
                itertools.chain(*(ref.output()
                                  for ref in referenced.values()))))
        self.packed = packed
        self.referenced = referenced

    def merged(self,
               resp_json: Any) -> Generator[Mapping[str, Any], None, None]:
        """Generate a dict merging metrics, place and author data"""
        includes = resp_json.get('includes', dict())
        for key, val in includes.items():
            includes[key] = {item['id']: item for item in val}
        for item in resp_json.get('data', list()):
            # Unpack packed atributes
            for attr in self.packed:
                packed = item.get(attr, None)
                if packed is not None:
                    item.update(packed)
                    del item[attr]
            # Resolve referenced fields
            for key, ref in self.referenced.items():
                catalog = includes.get(key, None)
                if catalog is None:
                    continue
                item = ref.join(item, catalog)
            # yield merged item
            yield item

    def follow(self, api: Api, url: str,
               params: Dict[str, Any]) -> Generator[pd.DataFrame, None, None]:
        """Generate dataframes"""
        empty_meta: Mapping[str, Any] = {}
        while True:
            resp_json = api.query(url, params)
            yield pd.DataFrame(self.merged(resp_json), columns=self.columns)
            next_token = resp_json.get('meta',
                                       empty_meta).get('next_token', None)
            if next_token is None:
                return
            logging.info("Model::follow:next_token = %s", next_token)
            params['next_token'] = next_token


class TweetData:
    """Data Model to turn tweet object into pandas DataFrame"""
    @staticmethod
    def build_query_to(terms: Sequence[str],
                       screen_names: Sequence[str]) -> str:
        """Build a query for a set of terms or replies to screen names"""
        query = " OR ".join(
            itertools.chain(
                terms,
                # Replies
                (f'to:{screen_name}' for screen_name in screen_names),
                # Mentions
                (f'@{screen_name}' for screen_name in screen_names)))

        # Exclude tweets from my own account(s)
        not_from = ")(".join(f'-from:{screen_name}'
                             for screen_name in screen_names)
        result = f'({query})({not_from})'
        logging.info("TweetData::build_query_to::query = '%s'", result)
        if len(result) >= 512:
            raise ValueError("ERROR: query is too large. " +
                             "You need to either remove some query terms, " +
                             "or remove some screen names")
        return result

    @staticmethod
    def build_query_from(screen_names: Sequence[str]) -> str:
        """Build a query for a set of terms sent by particular screen names"""
        query = " OR ".join(f'from:{screen_name}'
                            for screen_name in screen_names)

        logging.info("TweetData::build_query_from::query = '%s'", query)
        if len(query) >= 512:
            raise ValueError("ERROR: query is too large. " +
                             "You need to either remove some query terms, " +
                             "or remove some screen names")
        return query

    def build_params(self, query: str) -> Dict[str, str]:
        """Build the parameter set to query twitter for terms and screen names"""
        return {
            'expansions': 'author_id,geo.place_id',
            'tweet.fields': 'id,lang,text,created_at,public_metrics',
            'user.fields': 'name,username,location',
            'place.fields': 'place_type,country,country_code,name,full_name',
            'start_time': self.start_time.isoformat('T') + 'Z',
            'end_time': self.end_time.isoformat('T') + 'Z',
            'max_results': str(self.size),
            'query': query,
        }

    _api_path = 'tweets/search/recent'

    # Attributes returned in query reply data
    _columns = ['id', 'lang', 'text', 'created_at']
    # Attributes returned in query reply data (packed)
    _packed = {
        'public_metrics':
        ['retweet_count', 'reply_count', 'like_count', 'quote_count']
    }
    # Attributes returned in 'includes' (referenced)
    _referenced = {
        'places':
        Reference(
            ('geo', 'place_id'), {
                'place_type': 'place_type',
                'country': 'country',
                'country_code': 'country_code',
                'place_name': 'country_name',
                'place_fullname': 'country_fullname',
            }),
        'users':
        Reference(
            ('author_id', ), {
                'id': 'author_id',
                'name': 'author_name',
                'username': 'username',
                'location': 'author_location'
            })
    }

    def __init__(self, days_back: int = 1, size: int = 100):
        """
        Save initial parameters:
        - days_back: How far to go back in the timeline (up to 6 days)
        - size: How many tweets to collect per request (max. 100)
        """
        # the API support max 6 days back
        days_back = min(days_back, 6)
        self.end_time = datetime.combine(date.today(), datetime.min.time())
        self.start_time = self.end_time - timedelta(days=days_back)
        self.last_day = self.start_time + timedelta(days=days_back - 1)
        self.size = size
        self.model = Model(TweetData._columns, TweetData._packed,
                           TweetData._referenced)

    @staticmethod
    def _process(
            frames: Iterable[pd.DataFrame]
    ) -> Generator[pd.DataFrame, None, None]:
        """Post-process frames before yielding them"""
        for frame in frames:
            # Remove retweets
            frame = frame[~frame['text'].str.startswith('RT ')]
            # Calculate impact
            frame['impact'] = frame['retweet_count'] + frame['like_count'] + 1
            yield frame

    def frames_from(
        self,
        api: Api,
        screen_names: Sequence[str],
    ) -> Generator[pd.DataFrame, None, None]:
        """Generate dataframes from tweets sent from given accounts"""
        params = self.build_params(TweetData.build_query_from(screen_names))
        return TweetData._process(
            self.model.follow(api, TweetData._api_path, params))

    def frames_to(
        self,
        api: Api,
        terms: Sequence[str],
        screen_names: Sequence[str],
    ) -> Generator[pd.DataFrame, None, None]:
        """Generate dataframes from tweets sent to given accounts"""
        params = self.build_params(
            TweetData.build_query_to(terms, screen_names))
        return TweetData._process(
            self.model.follow(api, TweetData._api_path, params))


class UserData:
    """Data Model to turn user object into pandas DataFrame"""
    @staticmethod
    def build_params(screen_names: Sequence[str]) -> Dict[str, str]:
        """Build the parameter set to query twitter for users"""
        logging.info("UserData::build_params::screen_names = '%s'",
                     screen_names)
        return {
            'user.fields': 'public_metrics',
            'usernames': ','.join(screen_names)
        }

    # Attributes returned in query reply data
    _columns = ['id', 'username']
    # Attributes returned in query reply data (packed)
    _packed = {
        'public_metrics':
        ['followers_count', 'following_count', 'tweet_count', 'listed_count']
    }
    # Attributes returned in 'includes' (referenced)
    _referenced: Mapping[str, Reference] = dict()

    def __init__(self):
        """Save initial parameters"""
        self.model = Model(UserData._columns, UserData._packed,
                           UserData._referenced)

    def frames(self, api: Api, screen_names: Sequence[str]) -> pd.DataFrame:
        """Generate dataframes"""
        # Get user information
        users = pd.concat(self.model.follow(
            api, 'users/by', UserData.build_params(screen_names)),
                          ignore_index=True)
        users = users.rename(columns={'id': 'author_id'})
        # Get timeline information for users
        tdata = TweetData(days_back=1)
        tweets = pd.concat(tdata.frames_from(api, screen_names),
                           ignore_index=True)
        # Group by author id, get total of messages and sum of fields
        tweets['day'] = pd.to_datetime(tweets['created_at']).dt.date
        tweets = tweets.drop(['created_at'], axis=1)
        tweets = tweets.groupby(['author_id', 'day']).agg(['sum', 'count'])
        # Flatten aggregated column names
        tweets.columns = [
            '_'.join(col).strip() for col in tweets.columns.values
        ]
        # Reindex users with user id and day, the same as tweets
        users['day'] = pd.to_datetime(tdata.last_day)
        users['day'] = users['day'].dt.date
        users = users.set_index(['author_id', 'day'])
        # Join users with tweet count
        if len(tweets.index) > 0:
            return users.join(tweets, rsuffix='_tweet')
        # If the tweets df is empty, join would fail.
        # In that case, we just extend the users df with null columns.
        for col in tweets.columns:
            users[col] = None
        return users
