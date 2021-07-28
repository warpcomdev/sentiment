#!/usr/bin/env python3
"""Collect facebook analytics statistics"""

import sys
import os
import json
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
    """Uses pagination to keep fetching JSON data from url, raise FetchError on error"""
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
            "type": "Text",
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
            "type": "Text",
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
    token: str

    def insights(self,
                 pool: ThreadPool,
                 session: orion.Session,
                 metrics: Sequence[str],
                 period: str = 'day',
                 chunk_size: int = 16) -> pd.DataFrame:
        """Get page insights"""
        # Facebook page insights API:
        # See https://developers.facebook.com/docs/graph-api/reference/v11.0/insights
        logging.info("Page[%s].insights(metrics=%s, period=%s, chunk_size=%d)",
                     self.name, metrics, period, chunk_size)
        headers = {'Accept': 'application/json'}
        mchunks = [
            metrics[i:i + chunk_size]
            for i in range(0, len(metrics), chunk_size)
        ]

        def follower(chunk):
            url = f'https://graph.facebook.com/v11.0/{self.id}/insights'
            params = {
                'period': period,
                'access_token': self.token,
                'metric': json.dumps(chunk)
            }
            if period == 'day':
                params['date_preset']: 'last_7d'
            return tuple(follow(session, url, headers=headers, params=params))

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
            # If value is a populated dict, turn into list of dicts.
            return [{'key': k, 'value': v} for k, v in item.items()]

        data['keyed'] = data['value'].apply(as_tuple)
        data = data.explode('keyed')
        data = explode_df_column(data.drop(columns=['value']), 'keyed')
        data = data.dropna(subset=['value'])
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


def main():

    etlConfigPath = os.path.realpath(os.getenv('ETL_CONFIG_PATH') or '.')
    logging.info("READING CONFIG FROM '%s'", etlConfigPath)
    load_dotenv(dotenv_path=os.path.join(etlConfigPath, '.env'))

    api = Api.from_file(
        sys.argv[1] if len(sys.argv) > 1 else 'credentials_turismo.json')
    #pylint: disable=broad-except
    # ENGINE = sqlalchemy.create_engine(build_postgres_uri(),
    #     pool_use_lifo=True, pool_pre_ping=True)
    # try:
    #     ENGINE.connect()
    # except Exception as err:
    #     logging.error("KO - Failed to connect to database: %s", err)
    #     sys.exit(-1)

    metrics = get_metrics("metrics.csv")
    #DAILY_METRICS = tuple(METRICS[METRICS['Granularity'] == 'day'].index)
    daily_metrics = tuple(metrics.index)
    logging.info("Collecting daily metrics %s", daily_metrics)

    session = orion.Session()
    entities = list()
    with ThreadPool(8) as pool:
        for name, page in api.pages.items():
            logging.info("Processing page %s", name)
            insights = page.insights(pool, session, daily_metrics).reset_index()
            entities.extend(row_to_kpi(row, 'name', 'end_time', 'facebook', name, 'title', 'description', 'value', 'key')
                for index, row in insights.fillna('').iterrows())

    keystoneURL = os.getenv("KEYSTONE_URL")
    orionURL = os.getenv("ORION_URL")
    service = os.getenv("ORION_SERVICE")
    subservice = os.getenv("ORION_SUBSERVICE")
    username = os.getenv("ORION_USERNAME")
    password = os.getenv("ORION_PASSWORD")
    
    logging.info("Authenticating to url %s, service %s, username %s", keystoneURL, service, username)
    cb = orion.ContextBroker(
        keystoneURL=keystoneURL,
        orionURL=orionURL,
        service=service,
        subservice=subservice)
    cb.auth(session, username, password)

    # Get day singleton
    bookmarkType = "Bookmark"
    bookmarkId = "facebook"
    logging.info("Collecting base timestamp for updates from entity %s type %s", bookmarkId, bookmarkType)
    singleton = cb.get(session, bookmarkId, bookmarkType)
    basestamp = ""
    if singleton is not None:
        if "TimeInstant" in singleton:
            basestamp = singleton["TimeInstant"]["value"]

    logging.info("Splitting entities by day to skip before '%s'", basestamp)
    dailyentities = defaultdict(list)
    for entity in entities:
        dailyentities[entity['TimeInstant']['value']].append(entity)

    today = datetime.today().strftime('%Y-%m-%dT%H:%M:%S')
    days = sorted(dailyentities.keys())
    for day in days:
        if basestamp != "" and day[:19] <= basestamp[:19]:
            logging.info("Skipping entities for day %s", day)
            continue
        if day[:19] >= today[:19]:
            logging.info("Skipping entities for day %s", day)
            continue
        logging.info("Posting Entities to url %s, subservice %s, day %s", orionURL, subservice, day)
        cb.batch(session, dailyentities[day])
        logging.info("Updating bookmark id %s, type %s, day %s", bookmarkId, bookmarkType, day)
        if not basestamp:
            cb.post(session, bookmarkId, bookmarkType, { "TimeInstant": { "type": "DateTime", "value": day }})
        else:
            cb.putAttribs(session, bookmarkId, bookmarkType, { "TimeInstant": { "type": "DateTime", "value": day }})


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
        print("ETL KO")
        print(err)
