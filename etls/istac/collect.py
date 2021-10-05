#!/usr/bin/env python
# pylint: disable=line-too-long
"""Load yearly data from istacpy API"""

import logging
import sys
import traceback
from typing import Mapping, List, Any, Generator, Iterable, Iterator, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor

import configargparse
from istacpy.indicators.lite import indicators
from istacpy.exceptions import GranularityNotAvailableError
from orion import Session, ContextBroker

JsonData = Mapping[str, Any]
JsonList = List[JsonData]
BATCH_SIZE = 8


def ind_as_kpi(ind: indicators.Indicator,
               geo_grain: str,
               year: int = None) -> Generator[JsonData, None, None]:
    """Ind_as_kpi generates KeyPerformanceIndicator entities from an Indicator object"""
    time_query = 'Y' if year is None else f'Y|{year}'
    try:
        ind_data = ind.get_data(geo=geo_grain, time=time_query)
    except GranularityNotAvailableError as grain_err:
        logging.warning("GRANULARITY NOT AVAILABLE FOR %s, ID %s, YEAR %s, %s", ind.code,
                      geo_grain, time_query, grain_err)
        return
    except:
        logging.error("EXCEPTION WITH CODE %s, ID %s, YEAR %s", ind.code,
                      geo_grain, time_query)
        raise

    entityid = f'{ind.code}:{ind_data.geographical_granularity}:{ind_data.time_granularity}:{ind_data.measure}'
    source = f'istac:{ind.code}'
    totals = 0
    for geo, values in ind_data.data.items():
        count = 0
        for data_year, value in zip(ind_data.index, values):
            totals += 1
            count += 1
            yield {
                'id': entityid,
                'type': 'KeyPerformanceIndicator',
                'TimeInstant': {
                    'type': 'DateTime',
                    'value': f'{data_year}-12-31T00:00:00Z'
                },
                'source': {
                    'type': 'Text',
                    'value': source
                },
                'product': {
                    'type': 'TextUnrestricted',
                    'value': geo
                },
                'name': {
                    'type': 'TextUnrestricted',
                    'value': ind.title
                },
                'description': {
                    'type': 'TextUnrestricted',
                    'value': ind.description
                },
                'kpiValue': {
                    "type": 'Number',
                    'value': value
                },
                'aggregatedData': {
                    'type': 'TextUnrestricted',
                    'value': ind_data.geographical_granularity
                }
            }
        logging.info("ENTRIES %s [%s]: %d", entityid, geo, count)
    logging.info("TOTAL ENTRIES %s: %d", entityid, totals)


def rotate(
    iterables: Iterator[Iterable[JsonData]]
) -> Generator[JsonData, None, None]:
    """Rotate across a set of iterables"""
    iterators: List[Optional[Iterator[JsonData]]] = [
        iter(item) for item in iterables
    ]
    while len(iterators) > 0:
        depleted = False
        for index, item in enumerate(iterators):
            try:
                if item is None:
                    depleted = True
                else:
                    value = next(item)
                    yield value
            except StopIteration:
                iterators[index] = None
                depleted = True
        if depleted:
            iterators = [item for item in iterators if item is not None]


def indicators_by_subject(
    pool: ThreadPoolExecutor
) -> Generator[Mapping[str, indicators.Indicator], None, None]:
    """All_indicators enumerates all available indicators"""
    for subject, _ in indicators.get_subjects():
        codes = [
            code for code, _ in indicators.get_indicators(subject_code=subject)
        ]
        yield {
            ind.code: ind
            for ind in pool.map(indicators.get_indicator, codes)
        }


def yearly_absolute_data(pool: ThreadPoolExecutor,
                         session: Session,
                         orion_cb: ContextBroker,
                         inds: Mapping[str, indicators.Indicator],
                         year: Optional[int] = None):
    """Get absolute data for the given indicators and years"""
    granularities: List[Tuple[indicators.Indicator, str,
                              Optional[int]]] = list()
    for ind in inds.values():
        for geo_grain in ind.geographical_granularities.values():
            granularities.append((ind, geo_grain, year))

    batches = [
        granularities[base:(base + BATCH_SIZE)]
        for base in range(0, len(granularities), BATCH_SIZE)
    ]
    for batch in batches:
        logging.info("Batching indicators %s",
                     ", ".join("%s:%s" % (item[0].code, item[1]) for item in batch))
        orion_cb.batch(session,
                       rotate(pool.map((lambda g: ind_as_kpi(*g)), batch)))


# pylint: disable=too-many-locals
def main():
    """Main ETL function"""

    parser = configargparse.ArgParser(default_config_files=['istac.ini'])
    parser.add('-c',
               '--config',
               required=False,
               is_config_file=True,
               env_var='CONFIG_FILE',
               help='config file path')
    parser.add('--keystone-url',
               required=False,
               help='Keystone URL',
               env_var='KEYSTONE_URL',
               default="https://auth.iotplatform.telefonica.com:15001")
    parser.add('--orion-url',
               required=False,
               help='Orion URL',
               env_var='ORION_URL',
               default="https://cb.iotplatform.telefonica.com:10027")
    parser.add('--orion-service',
               required=True,
               help='Orion service name',
               env_var="ORION_SERVICE")
    parser.add('--orion-subservice',
               required=True,
               help='Orion subservice name',
               env_var="ORION_SUBSERVICE")
    parser.add('--orion-username',
               required=True,
               help='Orion username',
               env_var="ORION_USERNAME")
    parser.add('--orion-password',
               required=True,
               help='Orion password',
               env_var="ORION_PASSWORD")
    parser.add('--istac-year',
               required=False,
               help='Year to collect info for',
               env_var="ISTAC_YEAR")
    options = parser.parse_args()

    session = Session()
    logging.info("Authenticating to url %s, service %s, username %s",
                 options.keystone_url, options.orion_service,
                 options.orion_username)
    orion_cb = ContextBroker(keystoneURL=options.keystone_url,
                             orionURL=options.orion_url,
                             service=options.orion_service,
                             subservice=options.orion_subservice)
    orion_cb.auth(session, options.orion_username, options.orion_password)

    with ThreadPoolExecutor(max_workers=BATCH_SIZE) as pool:
        for inds in indicators_by_subject(pool):
            yearly_absolute_data(pool, session, orion_cb, inds,
                                 options.istac_year)


if __name__ == "__main__":

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    root.addHandler(handler)

    try:
        main()
        print("ETL OK")
    # pylint: disable=broad-except
    except Exception as err:
        print("ETL KO: ", err)
        traceback.print_exc()
