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


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, force=True)
    ETL_CONFIG_PATH = os.path.realpath(os.getenv('ETL_CONFIG_PATH') or '.')
    logging.info("READING CONFIG FROM '%s'", ETL_CONFIG_PATH)
    load_dotenv(dotenv_path=os.path.join(ETL_CONFIG_PATH, '.env'))

    #pylint: disable=broad-except
    ENGINE = sqlalchemy.create_engine(build_postgres_uri())
    try:
        ENGINE.connect()
    except Exception as err:
        logging.error("KO - Failed to connect to database: %s", err)
        sys.exit(-1)

    try:
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
        logging.info("OK - Data inserted")
    except Exception as err:
        logging.error("KO - Failed to upsert data: %s", err)
        sys.exit(-1)
