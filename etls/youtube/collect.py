#!/usr/bin/env python3
"""Collect youtube analytics statistics"""
# pylint: disable=too-many-arguments

import sys
import os
import json
import logging
import io
import traceback
from datetime import datetime, timezone, timedelta
from multiprocessing.pool import ThreadPool
from collections import defaultdict
from typing import Sequence, Mapping, Any, Optional, Generator

import urllib3
import pandas as pd
from dotenv import load_dotenv

import google.oauth2.credentials
import google.auth.transport.urllib3
import googleapiclient.discovery
import orion


def kpi_object(entity_id: str,
               timeinstant: str,
               source: str,
               product: str,
               name: str,
               description: str,
               value: str,
               agg: Optional[str] = None):
    """Build NGSIv2 KeyPerformanceIndicator entity from fields"""
    data = {
        "id": entity_id,
        "type": "KeyPerformanceIndicator",
        "TimeInstant": {
            "type": "DateTime",
            "value": timeinstant
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
            "value": name
        },
        "description": {
            "type": "TextUnrestricted",
            "value": description
        },
        "kpiValue": {
            "type": "Number",
            "value": value
        }
    }
    if agg is not None:
        data["aggregatedData"] = {"type": "TextUnrestricted", "value": agg}
    return data


class Api:
    """Youtube youtube_api analytics wrapper"""
    def __init__(self, cred_filename: str):
        """Load the provided credential file"""
        with open(cred_filename, "r", encoding="utf-8") as infile:
            credentials = google.oauth2.credentials.Credentials(
                **json.load(infile))
            with urllib3.PoolManager() as http:
                request = google.auth.transport.urllib3.Request(http)
                credentials.refresh(request)
        self._credentials = credentials
        self._apis: Mapping[str, Any] = defaultdict(dict)

    def service(self, api: str, version: str):
        """Return a service youtube_api object (possibly cached)"""
        last = self._apis[api].get(version, None)
        if last is None:
            last = googleapiclient.discovery.build(
                api,
                version,
                credentials=self._credentials,
                cache_discovery=False)
            self._apis[api][version] = last
        return last

    def token(self):
        """Return current auth bearer token"""
        return self._credentials.token


def explode_df_column(frame: pd.DataFrame, colname: str) -> pd.DataFrame:
    """Explode a dict-like column into additional columns"""
    return pd.concat(
        [frame.drop([colname], axis=1), frame[colname].apply(pd.Series)],
        axis=1)


def channel_stats(api: Api) -> pd.DataFrame:
    """Get channel basic stats"""
    # Youtube data youtube_api:
    # See https://developers.google.com/youtube/v3/docs/subscriptions/list
    service = api.service('youtube', 'v3')
    stats = service.channels().list(part="statistics,brandingSettings",
                                    mine=True).execute()

    items = pd.DataFrame(stats['items'])
    items['date'] = datetime.today().strftime("%Y-%m-%dT00:00:00Z")
    logging.info("channel_stats::items = %s", items.to_csv())
    # extract inner 'brandingSettings.channel' column
    items['channel'] = items['brandingSettings'].apply(
        lambda item: item['channel'])
    items = items.drop('brandingSettings', axis=1)
    # explode 'statistics' and 'channel' dict into columns
    items = explode_df_column(items, 'channel')
    items = explode_df_column(items, 'statistics')
    items = items.set_index('id')
    items['subscribedCount'] = None

    for channel in items.index:
        subs = service.subscriptions().list(part="id",
                                            channelId=channel).execute()
        # Solo nos interesan los totalResults
        logging.info("channel_stats::subscriptions[%s] = %s", channel, subs)
        items.at[channel, 'subscribedCount'] = subs['pageInfo']['totalResults']

    logging.info("channel_stats::return = %s", items.to_csv())
    return items


def get_jobs(api: Api, report_types: Sequence[str]) -> pd.DataFrame:
    """Get jobs for the given report types"""

    service = api.service('youtubereporting', 'v1')
    # Get available report types
    rtypes = {
        rtype['id']: rtype['name']
        for rtype in service.reportTypes().list().execute().get(
            'reportTypes', tuple())
    }
    logging.info("get_jobs::rtypes = %s", rtypes.keys())

    # Get scheduled jobs
    jobs = {
        job['reportTypeId']: job
        for job in service.jobs().list().execute().get('jobs', tuple())
    }
    logging.info("get_jobs::jobs = %s", jobs.keys())

    # Build new scheduled jobs for any reportType not already present
    for missing in (rtype for rtype in report_types if not rtype in jobs):
        logging.info("get_jobs::missing = %s", missing)
        service.jobs().create(
            body=dict(reportTypeId=missing, name=rtypes[missing])).execute()

    # Return already available jobs
    available = [job for key, job in jobs.items() if key in report_types]
    if not available:
        return None
    result = pd.DataFrame(available)
    logging.info("get_jobs::return = %s", result.to_csv())
    return result


def get_reports(api: Api, jobs: Sequence[str], days=2) -> pd.DataFrame:
    """Get reports generated by given job ids, since given days"""

    service = api.service('youtubereporting', 'v1')
    after = (datetime.now(timezone.utc).astimezone() -
             timedelta(days=days)).isoformat('T')

    reports = list()
    for job_id in jobs:
        logging.info("get_reports::job_id = %s", job_id)
        reports.extend(service.jobs().reports().list(
            jobId=job_id,
            createdAfter=after).execute().get('reports', tuple()))

    if not reports:
        return None
    result = pd.DataFrame(reports)
    logging.info("get_reports::return = %s", result.to_csv())
    return result


def iterable_to_stream(iterable, buffer_size=io.DEFAULT_BUFFER_SIZE):
    """
    Lets you use an iterable (e.g. a generator) that yields bytestrings as a read-only
    input stream.

    The stream implements Python 3's newer I/O youtube_api (available in Python 2's io module).
    For efficiency, the stream is buffered.
    """
    class IterStream(io.RawIOBase):
        """Iterator-based stream"""
        def __init__(self):
            """Build empty stream object"""
            super().__init__()
            self.leftover = None

        def readable(self):
            """Stream is read-only"""
            return True

        def readinto(self, b):
            """Implements stream, reads bytes into given buffer"""
            try:
                buflen = len(b)  # We're supposed to return at most this much
                chunk = self.leftover or next(iterable)
                output, self.leftover = chunk[:buflen], chunk[buflen:]
                b[:len(output)] = output
                return len(output)
            except StopIteration:
                return 0  # indicate EOF

    return io.BufferedReader(IterStream(), buffer_size=buffer_size)


def download_reports(session: orion.Session,
                     api: Api,
                     urls: Sequence[str],
                     threads=4) -> pd.DataFrame:
    """Download reports given by downloadUrl"""
    headers = {'Authorization': "Bearer %s" % api.token()}

    def download(session, url, headers):
        """Download single report"""
        logging.info("get_jobs::download_reports::download(%s)", url)
        with session.get(url, headers=headers, stream=True) as resp:
            if resp.status_code < 200 or resp.status_code > 204:
                raise ValueError("Failed to collect URL {}: {}".format(
                    url, resp.status_code))
            csv = pd.read_csv(iterable_to_stream(resp.iter_content()))
            # Date format is YYYYMMDD, I need YYYY-MM-DD
            csv['date'] = csv['date'].apply(lambda item: "%04d-%02d-%02d" % (
                item / 10000, (item % 10000) / 100, item % 100))
            return csv

    with ThreadPool(threads) as tpool:
        result = pd.concat(tpool.map(
            lambda url: download(session, url, headers), urls),
                           axis=0,
                           ignore_index=True)
        logging.info("download_reports::return = %s", result.to_csv())
        return result


def df_to_kpis(reports: pd.DataFrame,
               metrics: pd.DataFrame) -> Generator[Any, None, None]:
    """Build KPIs from dataframe with 'date', 'title', <Agg> and <Metric> columns"""
    for _, metric in metrics.iterrows():
        value = metric['Metric']
        description = metric['Description']
        agg = metric['Agg'] if 'Agg' in metric else None
        agg_data = reports
        if not agg:
            entity_id = value
            agg = None
        else:
            agg_data = reports[[
                'date', 'title', agg, value
            ]].groupby(by=['date', 'title', agg]).agg('sum').reset_index()
            entity_id = f'{value}:{agg}'
        for _, row in agg_data.iterrows():
            aggval = None if agg is None else row[agg]
            yield kpi_object(entity_id=entity_id,
                             timeinstant=row["date"],
                             source="youtube",
                             product=row['title'],
                             name=value,
                             description=description,
                             value=row[value],
                             agg=aggval)


def cb_from_env(session: orion.Session) -> orion.ContextBroker:
    """Build an orion.ContextBroker instance with config settings from env"""
    keystone_url = os.getenv("KEYSTONE_URL")
    orion_url = os.getenv("ORION_URL")
    service = os.getenv("ORION_SERVICE")
    subservice = os.getenv("ORION_SUBSERVICE")
    username = os.getenv("ORION_USERNAME")
    password = os.getenv("ORION_PASSWORD")

    logging.info("Authenticating to url %s, service %s, username %s",
                 keystone_url, service, username)
    orion_cb = orion.ContextBroker(keystoneURL=keystone_url,
                                   orionURL=orion_url,
                                   service=service,
                                   subservice=subservice)
    orion_cb.auth(session, username, password)
    return orion_cb


def main():
    """Read the APIs and update contextbroker entities"""
    # Load ENV
    etl_config_path = os.path.realpath(os.getenv('etl_config_path') or '.')
    logging.info("READING CONFIG FROM '%s'", etl_config_path)
    load_dotenv(dotenv_path=os.path.join(etl_config_path, '.env'))

    channel_metrics = pd.read_csv("channel_metrics.csv")
    reports_metrics = pd.read_csv("reports_metrics.csv")

    youtube_api = Api(
        sys.argv[1] if len(sys.argv) > 1 else 'credentials.json')
    session = orion.Session()
    orion_cb = cb_from_env(session)

    # Get and upsert channel data
    channels = channel_stats(youtube_api)
    orion_cb.batch(session, df_to_kpis(channels, channel_metrics))

    # Get jobs with reportTypeId
    jobs = get_jobs(youtube_api,
                    reports_metrics['Report'].unique()).set_index('id')
    reports = get_reports(youtube_api, jobs.index).set_index('jobId').join(
        jobs['reportTypeId'])
    # Add channel title to report

    for report_type_id in reports['reportTypeId'].unique():
        metrics = reports_metrics[reports_metrics['Report'] == report_type_id]
        report = download_reports(
            session, youtube_api,
            reports[reports['reportTypeId'] == report_type_id]['downloadUrl'])
        report = report.join(channels[['title']], how='left', on='channel_id')
        orion_cb.batch(session, df_to_kpis(report, metrics))


if __name__ == "__main__":

    # Setp up logging
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    root.addHandler(handler)
    try:
        main()
        print("ETL OK")
    # pylint: disable=broad-except
    except Exception as err:
        print("ETL KO: ", err)
        traceback.print_exc()
