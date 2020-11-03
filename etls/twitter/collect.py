#!/usr/bin/env python
"""Twitter collector"""

import sys
import os
import logging
from typing import Sequence, Optional

import sqlalchemy
import pangres

import pandas as pd
from dotenv import load_dotenv
import twitter
import sentiment


def build_postgres_uri() -> str:
    """Build connection URL"""
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASS")
    host = os.getenv("POSTGRES_HOST")
    port = os.getenv("POSTGRES_PORT")
    dbname = os.getenv("POSTGRES_DB")
    return f'postgresql://{user}:{password}@{host}:{port}/{dbname}'


def upsert_user_data(engine: sqlalchemy.engine, api: twitter.Api,
                     screen_names: Sequence[str], schema: Optional[str],
                     table: str):
    """Upsert user data into database"""
    logging.info("upsert_user_data::screen_names = %s", screen_names)
    frame = twitter.UserData().frames(api, screen_names).reset_index()
    # Align information to database columns
    columns = {
        'username': 'channel',
        'day': 'day',
        'followers_count': 'total_followers',
        'following_count': 'total_followed',
        'tweet_count': 'total_posts',
        'id_count': 'daily_posts',
        'retweet_count_sum': 'daily_repost',
        'reply_count_sum': 'daily_reply',
        'like_count_sum': 'daily_like',
        'quote_count_sum': 'daily_quote',
    }
    frame = frame.drop([col for col in frame.columns if col not in columns],
                       axis=1).rename(columns=columns)
    # Add source columns
    frame['source'] = 'twitter'
    frame = frame.set_index(['source', 'channel', 'day'])
    logging.info("upsert_user_data::result = %s", frame)
    pangres.upsert(engine,
                   df=frame,
                   table_name=table,
                   schema=schema,
                   if_row_exists='update',
                   create_schema=False,
                   add_new_columns=False,
                   adapt_dtype_of_empty_db_columns=False)


def upsert_tweet_data(engine: sqlalchemy.engine, api: twitter.Api,
                      sent_api: sentiment.Api, terms: Sequence[str],
                      screen_names: Sequence[str], schema: Optional[str],
                      table: str):
    """Upsert user data into database"""
    logging.info("upsert_tweet_data::terms = %s", terms)
    logging.info("upsert_tweet_data::screen_names = %s", screen_names)
    frames = list()
    for frame in twitter.TweetData(days_back=2,
                                   size=50).frames_to(api, terms,
                                                      screen_names):
        logging.info("upsert_tweet_data::len(frame) = %d", len(frame))
        cleaned = sentiment.Api.clean(frame)
        if len(cleaned) > 0:
            sents = sent_api.sentiment(cleaned)
            frames.append(sent_api.terms(sents))
    # We must concatenate before normalizing, otherwise aggregations
    # may yield several rows with the same keys
    if len(frames) <= 0:
        return
    terms = pd.concat(frames, ignore_index=True)
    norms = sentiment.Api.normalize(terms)
    # Align information to database columns
    columns = {
        'day': 'day',
        'lang': 'lang',
        'term': 'term',
        'repeat': 'repeat',
        'pos_per_term': 'pos_per_term',
        'neg_per_term': 'neg_per_term',
        'neutral_per_term': 'neutral_per_term',
        'pos': 'pos',
        'neg': 'neg',
        'neutral': 'neutral',
    }
    norms = norms.drop([col for col in norms.columns if col not in columns],
                       axis=1).rename(columns=columns)
    # Add source columns
    norms['source'] = 'twitter'
    norms['hour'] = norms['day'].dt.hour
    norms['category'] = None
    norms['nps_per_term'] = norms['pos_per_term'] - norms['neg_per_term']
    norms['nps'] = norms['pos'] - norms['neg']
    norms = norms.set_index(['source', 'day', 'hour', 'lang', 'term'])
    pangres.upsert(engine,
                   df=norms,
                   table_name=table,
                   schema=schema,
                   if_row_exists='update',
                   create_schema=False,
                   add_new_columns=False,
                   adapt_dtype_of_empty_db_columns=False)


if __name__ == "__main__":
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    root.addHandler(handler)

    ETL_CONFIG_PATH = os.path.realpath(os.getenv('ETL_CONFIG_PATH') or '.')
    logging.info("READING CONFIG FROM '%s'", ETL_CONFIG_PATH)
    load_dotenv(dotenv_path=os.path.join(ETL_CONFIG_PATH, '.env'))

    #pylint: disable=broad-except
    ENGINE = sqlalchemy.create_engine(build_postgres_uri(),
        pool_use_lifo=True, pool_pre_ping=True)
    try:
        ENGINE.connect()
    except Exception as err:
        logging.error("KO - Failed to connect to database: %s", err)
        sys.exit(-1)

    try:
        SENT_API = sentiment.Api()
        API = twitter.Api()
        SCREEN_NAMES = pd.read_csv(
            os.path.join(ETL_CONFIG_PATH, 'screen_names.csv'))
        TERMS = pd.read_csv(os.path.join(ETL_CONFIG_PATH, 'terms.csv'))
    except Exception as err:
        logging.error("KO - Failed to read CSV config files: %s", err)
        sys.exit(-2)

    try:
        upsert_user_data(ENGINE, API, SCREEN_NAMES['screen_names'],
                         os.getenv('POSTGRES_SCHEMA'), 'cx_engagement')
        upsert_tweet_data(ENGINE, API, SENT_API, TERMS['terms'],
                          SCREEN_NAMES['screen_names'],
                          os.getenv('POSTGRES_SCHEMA'), 'cx_sentiment')
        logging.info("OK - Data inserted")
    except Exception:
        logging.exception("KO - Failed to upsert data")
        sys.exit(-1)

