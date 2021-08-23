#!/usr/bin/env python
"""Twitter collector"""

import sys
import os
import logging
import itertools
import traceback
from typing import Sequence, Generator, Any

#import sqlalchemy
#import pangres

import pandas as pd
from dotenv import load_dotenv
import orion

import twitter_api
import twitter_sentiment

# def build_postgres_uri() -> str:
#     """Build connection URL"""
#     user = os.getenv("POSTGRES_USER")
#     password = os.getenv("POSTGRES_PASS")
#     host = os.getenv("POSTGRES_HOST")
#     port = os.getenv("POSTGRES_PORT")
#     dbname = os.getenv("POSTGRES_DB")
#     return f'postgresql://{user}:{password}@{host}:{port}/{dbname}'


# def upsert_user_data(engine: Any, api: twitter_api.Api,
#                      screen_names: Sequence[str], schema: Optional[str],
#                      table: str):
def upsert_user_data(
        api: twitter_api.Api,
        screen_names: Sequence[str]) -> Generator[Any, None, None]:
    """Upsert user data into database"""
    logging.info("upsert_user_data::screen_names = %s", screen_names)
    frame = twitter_api.UserData().frames(api, screen_names).reset_index()
    # Align information to database columns
    metrics = {
        'followers_count': 'Total number of followers',
        'following_count': 'Total number of following',
        'tweet_count': 'Total tweets sent',
        'id_count': 'Daily tweets sent',
        'retweet_count_sum': 'Daily retweets',
        'reply_count_sum': 'Daily tweet replies',
        'like_count_sum': 'Daily tweet likes',
        'quote_count_sum': 'Daily tweet quotes',
    }
    for _, row in frame.iterrows():
        for metric, desc in metrics.items():
            kpi = {
                'id': metric,
                'type': 'KeyPerformanceIndicator',
                'name': {
                    'type': 'Text',
                    'value': metric,
                },
                'description': {
                    'type': 'Text',
                    'value': desc,
                },
                'TimeInstant': {
                    'type': 'DateTime',
                    'value': row['day'].isoformat()
                },
                "source": {
                    "type": "Text",
                    "value": 'twitter'
                },
                "product": {
                    "type": "Text",
                    "value": row['username']
                },
                "kpiValue": {
                    "type": "Number",
                    "value": row[metric]
                },
            }
            yield kpi

    # columns = {
    #     'username': 'channel',
    #     'day': 'day',
    #     'followers_count': 'total_followers',
    #     'following_count': 'total_followed',
    #     'tweet_count': 'total_posts',
    #     'id_count': 'daily_posts',
    #     'retweet_count_sum': 'daily_repost',
    #     'reply_count_sum': 'daily_reply',
    #     'like_count_sum': 'daily_like',
    #     'quote_count_sum': 'daily_quote',
    # }
    # frame = frame.drop([col for col in frame.columns if col not in columns],
    #                    axis=1).rename(columns=columns)
    # # Add source columns
    # frame['source'] = 'twitter'
    # frame = frame.set_index(['source', 'channel', 'day'])
    # logging.info("upsert_user_data::result = %s", frame)
    # pangres.upsert(engine,
    #                df=frame,
    #                table_name=table,
    #                schema=schema,
    #                if_row_exists='update',
    #                create_schema=False,
    #                add_new_columns=False,
    #                adapt_dtype_of_empty_db_columns=False)


# def upsert_tweet_data(engine: Any, api: twitter_api.Api,
#                       sent_api: twitter_sentiment.Api, terms: Sequence[str],
#                       screen_names: Sequence[str], schema: Optional[str],
#                       table: str):
def upsert_tweet_data(
        api: twitter_api.Api, sent_api: twitter_sentiment.Api,
        terms: Sequence[str],
        screen_names: Sequence[str]) -> Generator[Any, None, None]:
    """Upsert user data into database"""
    logging.info("upsert_tweet_data::terms = %s", terms)
    logging.info("upsert_tweet_data::screen_names = %s", screen_names)
    terms_list = list()
    for frame in twitter_api.TweetData(days_back=2, size=50).frames_to(
            api, terms, screen_names):
        logging.info("upsert_tweet_data::len(frame) = %d", len(frame))
        cleaned = twitter_sentiment.Api.clean(frame)
        if len(cleaned) > 0:
            score_batch = sent_api.sentiment(cleaned)
            terms_list.append(sent_api.terms(score_batch))

    # Columns of score_list dataframe:
    # id,lang,text,created_at,retweet_count,reply_count,like_count,quote_count,place_type,
    # country,country_code,country_name,country_fullname,author_id,author_name,username,author_location,
    # impact,clean,score
    if len(terms_list) <= 0:
        return
    scores = pd.concat(terms_list, ignore_index=True)
    scores['pos'] = scores[scores['score'] == 1]['impact']
    scores['neg'] = scores[scores['score'] == -1]['impact']
    scores['neu'] = scores[scores['score'] == 0]['impact']

    # Round time to the closest hour for every tweet, so we can aggregate easily
    scores = twitter_sentiment.Api.round_time(scores)

    # Round time to the closest hour for every tweet, so we can aggregate easily
    # TODO: Group by category
    hourly_scores = twitter_sentiment.Api.round_time(scores).groupby(
        by=['day']).agg({
            'pos': 'sum',
            'neg': 'sum',
            'neu': 'sum',
        }).reset_index()
    hourly_scores['nps'] = hourly_scores['pos'] - hourly_scores['neg']
    metrics = {
        'positive_impact': ('pos', 'Impact of positive tweets'),
        'negative_impact': ('neg', 'Impact of negative tweets'),
        'neutral_impact': ('neu', 'Impact of neutral tweets'),
        'nps_impact': ('nps', 'Net Promoter Score impact'),
    }
    for _, row in hourly_scores.iterrows():
        for metric, (attrib, desc) in metrics.items():
            kpi = {
                'id': metric,
                'type': 'KeyPerformanceIndicator',
                'name': {
                    'type': 'Text',
                    'value': metric,
                },
                'description': {
                    'type': 'Text',
                    'value': desc,
                },
                'TimeInstant': {
                    'type': 'DateTime',
                    'value': row['day'].isoformat()
                },
                "source": {
                    "type": "Text",
                    "value": 'twitter'
                },
                "kpiValue": {
                    "type": "Number",
                    "value": row[attrib]
                },
            }
            yield kpi

    # HACK: Save tweet info
    # tweets = terms[['id', 'created_at', 'clean', 'terms']]
    # tweets['terms'] = tweets['terms'].apply(json.dumps)
    # tweets = pd.concat(
    #     [tweets.drop(['clean'], axis=1), tweets['clean'].apply(pd.Series)],
    #     axis=1)
    # tweets = tweets.set_index('id')
    # pangres.upsert(engine,
    #                df=tweets,
    #                table_name='cx_tweets',
    #                schema=schema,
    #                if_row_exists='update',
    #                create_schema=False,
    #                add_new_columns=False,
    #                adapt_dtype_of_empty_db_columns=False)

    # We must concatenate and round time before normalizing, otherwise aggregations
    # may yield several rows with the same keys
    norms = twitter_sentiment.Api.normalize(scores)
    top_terms = norms.sort_values(['day', 'repeat', 'impact'],
                                  axis=0,
                                  ascending=False)
    top_terms['rank'] = top_terms.groupby(by=['day']).cumcount() + 1
    top_terms = top_terms[top_terms['rank'] <= 20].reset_index()
    # top_terms columns:
    # day,lang,term,impact,impact_per_term,repeat,termcount,pos,neg,neutral,pos_per_term,neg_per_term,neutral_per_term,rank
    for _, row in top_terms.iterrows():
        rank = row['rank']
        kpi = {
            'id': f'top_term:{rank}',
            'type': 'KeyPerformanceIndicator',
            'name': {
                'type': 'Text',
                'value': 'top_term',
            },
            'description': {
                'type': 'Text',
                'value': 'Top Term',
            },
            'TimeInstant': {
                'type': 'DateTime',
                'value': row['day'].isoformat()
            },
            'source': {
                'type': 'Text',
                'value': 'twitter'
            },
            'product': {
                'type': 'TextUnrestricted',
                'value': row['term']
            },
            'aggData': {
                'type': 'Text',
                'value': row['lang']
            },
            'kpiValue': {
                'type': 'Number',
                'value': row['repeat']
            },
        }
        yield kpi

    # Align terms information to database columns
    # columns = {
    #     'day': 'day',
    #     'lang': 'lang',
    #     'term': 'term',
    #     'repeat': 'repeat',
    #     'pos_per_term': 'pos_per_term',
    #     'neg_per_term': 'neg_per_term',
    #     'neutral_per_term': 'neutral_per_term',
    #     'pos': 'pos',
    #     'neg': 'neg',
    #     'neutral': 'neutral',
    # }
    # norms = norms.drop([col for col in norms.columns if col not in columns],
    #                    axis=1).rename(columns=columns)
    # Add source columns
    # norms['source'] = 'twitter'
    # norms['hour'] = norms['day'].dt.hour
    # norms['category'] = None
    # norms['nps_per_term'] = norms['pos_per_term'] - norms['neg_per_term']
    # norms['nps'] = norms['pos'] - norms['neg']
    # norms = norms.set_index(['source', 'day', 'hour', 'lang', 'term'])
    # pangres.upsert(engine,
    #                df=norms,
    #                table_name=table,
    #                schema=schema,
    #                if_row_exists='update',
    #                create_schema=False,
    #                add_new_columns=False,
    #                adapt_dtype_of_empty_db_columns=False)


# pylint: disable=too-many-locals,invalid-name
def main():
    """Main ETL function"""

    etl_config_path = os.path.realpath(os.getenv('etl_config_path') or '.')
    logging.info("READING CONFIG FROM '%s'", etl_config_path)
    load_dotenv(dotenv_path=os.path.join(etl_config_path, '.env'))

    #pylint: disable=broad-except
    # ENGINE = sqlalchemy.create_engine(build_postgres_uri(),
    #                                   pool_use_lifo=True,
    #                                   pool_pre_ping=True)
    # try:
    #     ENGINE.connect()
    # except Exception as err:
    #     logging.error("KO - Failed to connect to database: %s", err)
    #     sys.exit(-1)

    keystoneURL = os.getenv("KEYSTONE_URL")
    orionURL = os.getenv("ORION_URL")
    service = os.getenv("ORION_SERVICE")
    subservice = os.getenv("ORION_SUBSERVICE")
    username = os.getenv("ORION_USERNAME")
    password = os.getenv("ORION_PASSWORD")

    logging.info("Authenticating to url %s, service %s, username %s",
                 keystoneURL, service, username)
    session = orion.Session()
    orion_cb = orion.ContextBroker(keystoneURL=keystoneURL,
                                   orionURL=orionURL,
                                   service=service,
                                   subservice=subservice)
    orion_cb.auth(session, username, password)

    sentiment_api = twitter_sentiment.Api(
        'nlptown/bert-base-multilingual-uncased-sentiment', '/tmp/sentiment')
    api = twitter_api.Api()
    screen_names = pd.read_csv(
        os.path.join(etl_config_path, 'screen_names.csv'))
    terms = pd.read_csv(os.path.join(etl_config_path, 'terms.csv'))

    # upsert_user_data(ENGINE, api, screen_names['screen_names'],
    #                  os.getenv('POSTGRES_SCHEMA'), 'cx_engagement')
    # upsert_tweet_data(ENGINE, api, sentiment_api, terms['terms'],
    #                   screen_names['screen_names'],
    #                   os.getenv('POSTGRES_SCHEMA'), 'cx_sentiment')
    entities = itertools.chain(
        upsert_user_data(api, screen_names['screen_names']),
        upsert_tweet_data(api, sentiment_api, terms['terms'],
                          screen_names['screen_names']))
    orion_cb.batch(session, entities)


if __name__ == "__main__":

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    root.addHandler(handler)

    try:
        main()
        logging.info("OK - Data inserted")
    # pylint: disable=broad-except
    except Exception as err:
        logging.error("KO - Failed to read CSV config files: %s", err)
        traceback.print_exc()
        sys.exit(-2)
