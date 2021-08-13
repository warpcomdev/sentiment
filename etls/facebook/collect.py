#!/usr/bin/env python3
"""Collect facebook analytics statistics"""

import sys
import os
import json
import traceback
import logging
from multiprocessing.pool import ThreadPool
from typing import Sequence, Mapping, Optional, Generator, Any
from itertools import chain
from operator import itemgetter
from collections import defaultdict
from datetime import datetime

import attr
import pandas as pd
import numpy as np
from dotenv import load_dotenv

import orion

# ---------------------
# HTTP helper functions
# ---------------------


def follow(
    session: orion.Session,
    url: str,
    headers: Optional[Mapping[str, str]] = None,
    params: Optional[Mapping[str, str]] = None
) -> Generator[Mapping[str, Any], None, None]:
    """Uses pagination to keep fetching JSON data from 'next' url, raise FetchError on error"""
    while url != "":
        resp = session.get(url, headers=headers, params=params)
        # If not found, return
        if resp is None:
            return
        body = resp.json()
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


def backwards(
    session: orion.Session,
    url: str,
    headers: Optional[Mapping[str, str]] = None,
    params: Optional[Mapping[str, str]] = None,
    max_backwards: Optional[int] = 3
) -> Generator[Mapping[str, Any], None, None]:
    """Uses pagination to keep fetching JSON data from 'previous' url, raise FetchError on error"""
    count = 0
    while url != "":
        resp = session.get(url, headers=headers, params=params)
        # If not found, return
        if resp is None:
            return
        body = resp.json()
        for item in body['data']:
            yield item
        # Find out if there are pages left
        paging = body.get('paging', None)
        if paging is None:
            return
        next_page = paging.get('previous', "").strip()
        if next_page == url:
            return
        # Params are attached to the paging url
        count += 1
        if count >= max_backwards:
            return
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

def row_to_kpi(row, id: str, timeinstant: str, source: str, product: str, name: str, description: str, value: str, agg: str):
    data = {
        "id": row[id],
        "type": "KeyPerformanceIndicator",
        "TimeInstant": {
            "type": "DateTime",
            "value": row[timeinstant]
        },
        "source": {
            "type": "Text",
            "value": source
        },
        "product": {
            "type": "Text",
            "value": product
        },
        "name": {
            "type": "TextUnrestricted",
            "value": row[name]
        },
        "description": {
            "type": "TextUnrestricted",
            "value": row[description]
        },
        "kpiValue": {
            "type": "Number",
            "value": row[value]
        }
    }
    if agg in row and row[agg]:
        data["aggregatedData"] = {
            "type": "TextUnrestricted",
            "value": row[agg]
        }
    return data
        

# ----------------------
# Facebook API functions
# ----------------------


#pylint: disable=too-few-public-methods
@attr.s(auto_attribs=True)
class Page:
    """Facebook Page"""
    name: str
    id: str
    instagram_id: str
    token: str

    def facebook_insights(self,
                 pool: ThreadPool,
                 session: orion.Session,
                 metrics: pd.DataFrame,
                 chunk_size: int = 16) -> pd.DataFrame:
        """Get page insights"""

        # Facebook page insights API:
        # See https://developers.facebook.com/docs/graph-api/reference/v11.0/insights
        # All metrics are considered daily
        metrics = tuple(metrics.index)
        logging.info("Page[%s].insights(metrics=%s, period=%s, chunk_size=%d)",
                     self.name, metrics, 'day', chunk_size)
        headers = {'Accept': 'application/json'}
        mchunks = [
            metrics[i:i + chunk_size]
            for i in range(0, len(metrics), chunk_size)
        ]
        def follower(chunk):
            url = f'https://graph.facebook.com/v11.0/{self.id}/insights'
            params = {
                'period': 'day',
                'access_token': self.token,
                'metric': json.dumps(chunk),
                'date_preset': 'last_7d'
            }
            return tuple(follow(session, url, headers=headers, params=params))
        return pd.DataFrame(chain(*pool.map(follower, mchunks)))

    def instagram_insights(self,
                 pool: ThreadPool,
                 session: orion.Session,
                 metrics: Sequence[str],
                 period: str = 'day',
                 chunk_size: int = 16) -> pd.DataFrame:
        """Get page insights"""
        # Instagram page insights API:
        # See https://developers.facebook.com/docs/instagram-api/guides/insights
        daily_metrics = tuple(metrics[metrics["Granularity"]=="day"].index)
        lifetime_metrics = tuple(metrics[metrics["Granularity"]=="lifetime"].index)
        logging.info("Page[%s].instagram_insights(metrics=%s, chunk_size=%d)",
                     self.name, metrics, chunk_size)
        headers = {'Accept': 'application/json'}
        daily_chunks = [
            ('day', daily_metrics[i:i + chunk_size])
            for i in range(0, len(daily_metrics), chunk_size)
        ]
        lifetime_chunks = [
            ('lifetime', lifetime_metrics[i:i + chunk_size])
            for i in range(0, len(lifetime_metrics), chunk_size)
        ]
        def follower(period_chunk):
            period, chunk = period_chunk
            url = f'https://graph.facebook.com/v11.0/{self.instagram_id}/insights'
            params = {
                'period': period,
                'access_token': self.token,
                'metric': json.dumps(chunk)
            }
            return tuple(backwards(session, url, headers=headers, params=params))
        return pd.DataFrame(chain(*pool.map(follower, chain(daily_chunks, lifetime_chunks))))

    def normalize(self, data: pd.DataFrame):
        """Normalize a DataFrame of events built from insights"""
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
            # If value is a populated dict, turn into list of dicts.
            return [{'key': k, 'value': v} for k, v in item.items()]

        data['keyed'] = data['value'].apply(as_tuple)
        data = data.explode('keyed')
        data = explode_df_column(data.drop(columns=['value']), 'keyed')
        data = data.dropna(subset=['value'])
        data = data.reset_index()
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
                                   instagram_id=page['instagram_id'],
                                   token=page['access_token'])
                for page in data['pages']
            }
        return cls(user_token=data['user_token'], pages=pages)


def load_metrics(api: Api, cb: orion.ContextBroker, session: orion.Session, metrics_file: str, bookmark: str, insightFunc: str):
    """
    Load metrics from file, using the provided insightFunc
    (any of 'facebook_insights', 'instagram_insights')
    """
    # Collecting the metrics is the easy part
    metrics  = get_metrics(metrics_file)
    logging.info("Collecting %s metrics %s", bookmark, metrics)
    entities = list()
    with ThreadPool(8) as pool:
        for name, page in api.pages.items():
            logging.info("Processing page %s", name)
            insights = page.normalize(getattr(page, insightFunc)(pool, session, metrics))
            entities.extend(row_to_kpi(row, 'name', 'end_time', bookmark, name, 'title', 'description', 'value', 'key')
                for index, row in insights.fillna('').iterrows())

    # Now we try not to load same data twice, by using a "Bookmark" singleton
    bookmarkType = "Bookmark"
    bookmarkId = bookmark
    logging.info("Collecting base timestamp for updates from entity %s type %s", bookmarkId, bookmarkType)
    singleton = cb.get(session, bookmarkId, bookmarkType)
    basestamp = ""
    if singleton is not None:
        if "TimeInstant" in singleton:
            basestamp = singleton["TimeInstant"]["value"]

    # Group entities by day
    logging.info("Splitting entities by day to skip before '%s'", basestamp)
    dailyentities = defaultdict(list)
    for entity in entities:
        dailyentities[entity['TimeInstant']['value']].append(entity)

    # Only keep days between last basestamp, and today
    logging.info("Filtering out duplicated or future days")
    today = datetime.today().strftime('%Y-%m-%dT%H:%M:%S')
    days = [day for day in sorted(dailyentities.keys()) if
            day[:19] < today[:19] and
           ((basestamp == "") or (day[:19] > basestamp[:19]))
    ]

    for day in days:
        logging.info("Batching updates for %s, day %s", bookmarkId, day)
        cb.batch(session, dailyentities[day])
        logging.info("Updating bookmark id %s, type %s, day %s", bookmarkId, bookmarkType, day)
        updateBookmark = cb.putAttribs
        if basestamp == "":
            updateBookmark = cb.post
            basestamp = day
        updateBookmark(session, bookmarkId, bookmarkType, { "TimeInstant": { "type": "DateTime", "value": day }})


def main():

    etlConfigPath = os.path.realpath(os.getenv('ETL_CONFIG_PATH') or '.')
    logging.info("READING CONFIG FROM '%s'", etlConfigPath)
    load_dotenv(dotenv_path=os.path.join(etlConfigPath, '.env'))

    api = Api.from_file(
        sys.argv[1] if len(sys.argv) > 1 else 'credentials_turismo.json')

    keystoneURL = os.getenv("KEYSTONE_URL")
    orionURL = os.getenv("ORION_URL")
    service = os.getenv("ORION_SERVICE")
    subservice = os.getenv("ORION_SUBSERVICE")
    username = os.getenv("ORION_USERNAME")
    password = os.getenv("ORION_PASSWORD")
    
    logging.info("Authenticating to url %s, service %s, username %s", keystoneURL, service, username)
    session = orion.Session()
    cb = orion.ContextBroker(
        keystoneURL=keystoneURL,
        orionURL=orionURL,
        service=service,
        subservice=subservice)
    cb.auth(session, username, password)
    
    load_metrics(api, cb, session, 'facebook_metrics.csv',  'facebook',  'facebook_insights')
    load_metrics(api, cb, session, 'instagram_metrics.csv', 'instagram', 'instagram_insights')


if __name__ == "__main__":
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    root.addHandler(handler)
    try:
        main()
        print("ETL OK")
    except Exception as err:
        print("ETL KO: ", err)
        traceback.print_exc()
