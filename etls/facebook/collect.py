#!/usr/bin/env python3
"""Collect facebook analytics statistics"""

import sys
import os
import json
import logging
from multiprocessing.pool import ThreadPool
from typing import Sequence, Mapping, Optional, Generator, Any
from itertools import chain

import requests
import attr
import pandas as pd
import numpy as np
from dotenv import load_dotenv

# import sqlalchemy
# import pangres

# ---------------------
# HTTP helper functions
# ---------------------


@attr.s(auto_attribs=True, auto_exc=True)
class FetchError(Exception):
    """Exception raised when Fetch fails"""
    url: str
    resp: requests.Response
    headers: Optional[Mapping[str, str]] = None
    params: Optional[Mapping[str, str]] = None

    def __str__(self):
        return '(url={}, headers={}, params={}) -> HTTP {}'.format(
            repr(self.url), repr(self.headers), repr(self.params),
            self.resp.status_code)


def fetch(url: str,
          headers: Optional[Mapping[str, str]] = None,
          params: Optional[Mapping[str, str]] = None) -> Any:
    """Fetches JSON body from url, raise FetchError on error"""
    data = requests.get(url, params=params, headers=headers)
    if data.status_code != 200:
        raise FetchError(url=url, resp=data, headers=headers, params=params)
    return data.json()


def follow(
    url: str,
    headers: Optional[Mapping[str, str]] = None,
    params: Optional[Mapping[str, str]] = None
) -> Generator[Mapping[str, Any], None, None]:
    """Uses pagination to keep fetching JSON data from url, raise FetchError on error"""
    while url != "":
        body = fetch(url, headers, params)
        for item in body['data']:
            yield item
        # Find out if there are pages left
        paging = body.get('paging', None)
        if paging is None:
            return
        next_page = paging.get('next', "").strip()
        if next_page == url:
            return
        # Params are attached to the paging url
        url = next_page
        params = None


# --------------------------
# Dataframe helper functions
# --------------------------


def get_metrics(metrics_file: str) -> pd.DataFrame:
    """Read metrics CSV file. Return DataFrame indexed by metric name."""
    metrics = pd.read_csv(metrics_file).dropna().set_index('Metric')
    metrics.index = metrics.index.str.strip("*")
    return metrics


def explode_df_column(frame: pd.DataFrame, colname: str) -> pd.DataFrame:
    """Explode a dict-like column into additional columns"""
    return pd.concat(
        [frame.drop([colname], axis=1), frame[colname].apply(pd.Series)],
        axis=1)


# -------------------------
# Database helper functions
# -------------------------


def build_postgres_uri() -> str:
    """Build connection URL"""
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASS")
    host = os.getenv("POSTGRES_HOST")
    port = os.getenv("POSTGRES_PORT")
    dbname = os.getenv("POSTGRES_DB")
    return f'postgresql://{user}:{password}@{host}:{port}/{dbname}'


# ----------------------
# Facebook API functions
# ----------------------


#pylint: disable=too-few-public-methods
@attr.s(auto_attribs=True)
class Page:
    """Facebook Page"""
    name: str
    id: str
    token: str

    def insights(self,
                 pool: ThreadPool,
                 metrics: Sequence[str],
                 period: str = 'day',
                 chunk_size: int = 16) -> pd.DataFrame:
        """Get page insights"""
        # Facebook page insights API:
        # See https://developers.facebook.com/docs/graph-api/reference/v8.0/insights
        logging.info("Page[%s].insights(metrics=%s, period=%s, chunk_size=%d)",
                     self.name, metrics, period, chunk_size)
        headers = {'Accept': 'application/json'}
        mchunks = [
            metrics[i:i + chunk_size]
            for i in range(0, len(metrics), chunk_size)
        ]

        def follower(chunk):
            url = f'https://graph.facebook.com/v8.0/{self.id}/insights'
            params = {
                'date_preset': 'yesterday',
                'period': period,
                'access_token': self.token,
                'metric': json.dumps(chunk)
            }
            return tuple(follow(url, headers=headers, params=params))

        data = pd.DataFrame(chain(*pool.map(follower, mchunks)))
        logging.info("Page[%s].insights input columns: %s", self.name,
                     data.columns)

        # 'Values' column is a list of values.
        # Concatenate all lists in a single row per metric,
        # and then explode into one row per value.
        data = data.groupby(by='name').agg({
            'title': 'last',
            'description': 'last',
            'values': 'sum',
        }).explode('values')

        # Now, each value is a dict with keys 'value'
        # and 'end_time'. Split that into columns.
        data = explode_df_column(data, 'values')
        logging.info("Page[%s].insights intermediate columns: %s", self.name,
                     data.columns)

        # One more step: Some of the values are themselves dicts,
        # we want to split them in columns again.
        def as_tuple(item):
            # If value is not a dict, key is NaN.
            if not hasattr(item, 'items'):
                return [{'key': np.nan, 'value': item}]
            # If value is an empty dict, both key and val are NaN.
            if len(item) <= 0:
                return [{'key': np.nan, 'value': np.nan}]
            # If value is a ppulated dict, turn into list of dicts.
            return [{'key': k, 'value': v} for k, v in item.items()]

        data['keyed'] = data['value'].apply(as_tuple)
        data = data.explode('keyed')
        data = explode_df_column(data.drop(columns=['values']), 'keyed')
        logging.info("Page[%s].insights final columns: %s", self.name,
                     data.columns)
        return data


@attr.s(auto_attribs=True)
class Api:
    """Facebook API analytics wrapper"""
    user_token: str
    pages: Mapping[str, Page]

    @classmethod
    def from_file(cls, cred_filename: str):
        """Load the provided credential file"""
        # Ejemplo fichero de credenciales:
        # {
        #     'user_token': '...',
        #     'pages': [
        #         {
        #             'name': 'Analytics Test',
        #             'id': '104712934460896',
        #             'access_token': '...'
        #         }
        #     ]
        # }
        with open(cred_filename, "r", encoding="utf-8") as infile:
            data = json.loads(infile.read())
            pages = {
                page['name']: Page(name=page['name'],
                                   id=page['id'],
                                   token=page['access_token'])
                for page in data['pages']
            }
        return cls(user_token=data['user_token'], pages=pages)


if __name__ == "__main__":
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    root.addHandler(handler)

    ETL_CONFIG_PATH = os.path.realpath(os.getenv('ETL_CONFIG_PATH') or '.')
    logging.info("READING CONFIG FROM '%s'", ETL_CONFIG_PATH)
    load_dotenv(dotenv_path=os.path.join(ETL_CONFIG_PATH, '.env'))

    API = Api.from_file(
        sys.argv[1] if len(sys.argv) > 1 else 'credentials_turismo.json')
    #pylint: disable=broad-except
    # ENGINE = sqlalchemy.create_engine(build_postgres_uri(),
    #     pool_use_lifo=True, pool_pre_ping=True)
    # try:
    #     ENGINE.connect()
    # except Exception as err:
    #     logging.error("KO - Failed to connect to database: %s", err)
    #     sys.exit(-1)

    METRICS = get_metrics("metrics.csv")
    DAILY_METRICS = tuple(METRICS[METRICS['Granularity'] == 'day'].index)
    logging.info("Collecting daily metrics %s", DAILY_METRICS)

    with ThreadPool(8) as POOL:
        for name, page in API.pages.items():
            logging.info("Processing page %s", name)
            print(page.insights(POOL, DAILY_METRICS))
