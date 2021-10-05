#!/usr/bin/env python
# -*- coding: utf-8 -*-
# pylint: disable=line-too-long,invalid-name
# pylint: disable=missing-module-docstring,missing-class-docstring,missing-function-docstring

import threading
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Set, Iterable, Generator

import attr
import requests
from ratelimit import limits, sleep_and_retry # type: ignore


@attr.s(auto_attribs=True, auto_exc=True)
class FetchError(Exception):
    """
    FetchError encapsulates all parameters of an HTTP request and the erroneous response
    """

    response: requests.Response
    method: str
    url: str
    params: Optional[Any] = None
    headers: Optional[Any] = None
    body: Optional[Any] = None

    def __str__(self) -> str:
        return f"Failed to {self.method} {self.url} (headers: {self.headers}, params: {self.params}, body: {self.body}): [{self.response.status_code}] {self.response.text}"


class fetchMethod(Enum):
    """Supported fetch methods"""
    GET = 'get'
    POST = 'post'
    PUT = 'put'
    DELETE = 'delete'


class Session(threading.local):
    """ThreadSafe version of requests.Session"""
    def __init__(self):
        super().__init__()
        self.session = requests.Session()

    def get(self, url: str, headers: Optional[Any] = None, params: Optional[Any] = None, **kw):
        """Utility method to perform a GET"""
        resp = self.session.get(url, params=params, headers=headers, **kw)
        if resp.status_code == 404:
            return None
        if resp.status_code < 200 or resp.status_code > 204:
            raise FetchError(response=resp, method="GET", url=url, params=params, headers=headers)
        return resp

    def post(self, url: str, headers: Optional[Any] = None, params: Optional[Any] = None, body: Optional[Any] = None, **kw):
        """Utility method to perform a POST"""
        resp = self.session.post(url, params=params, headers=headers, json=body, **kw)
        if resp.status_code < 200 or resp.status_code > 204:
            raise FetchError(response=resp, method="POST", url=url, params=params, headers=headers, body=body)
        return resp

    def put(self, url: str, headers: Optional[Any] = None, params: Optional[Any] = None, body: Optional[Any] = None, **kw):
        """Utility method to perform a POST"""
        resp = self.session.put(url, params=params, headers=headers, json=body, **kw)
        if resp.status_code < 200 or resp.status_code > 204:
            raise FetchError(response=resp, method="PUT", url=url, params=params, headers=headers, body=body)
        return resp

    def delete(self, url: str, headers: Optional[Any] = None, params: Optional[Any] = None, **kw):
        """Utility method to perform a DELETE"""
        resp = self.session.delete(url, params=params, headers=headers, **kw)
        if resp.status_code == 404:
            return None
        if resp.status_code < 200 or resp.status_code > 204:
            raise FetchError(response=resp, method="DELETE", url=url, params=params, headers=headers)
        return resp


@attr.s(auto_attribs=True)
class sessionManager:

    """Manages session lifetime"""

    keystoneURL: str
    username: str
    password: str
    headers: Dict[str, str]

    def auth(self, session: Session):
        """Get new token"""
        domain = self.headers['Fiware-Service']
        login_url = f"{self.keystoneURL}/v3/auth/tokens"
        body = {
            "auth": {
                "identity": {
                    "methods": ["password"],
                    "password": {
                        "user": {
                            "domain": {
                                "name": domain
                            },
                            "name": self.username,
                            "password": self.password
                        }
                    }
                },
                "scope": {
                    "domain": {
                        "name": domain
                    }
                }
            }
        }
        resp = session.post(url=login_url, body=body)
        token = resp.headers['X-Subject-Token']
        self.headers["X-Auth-Token"] = token

    # pylint: disable=too-many-arguments
    def __call__(self, session: Session, method: fetchMethod, url: str, params=None, body=None):
        """Executes method retrying auth if needed"""
        call = getattr(session, method.value)
        try:
            return call(url, headers=self.headers, params=params, body=body)
        except FetchError as err:
            # If error is unauthorized, try login again
            if err.response.status_code != 401:
                raise
            self.auth(session)
            return call(url, params=params, headers=self.headers, body=body)


@attr.s(auto_attribs=True)
class ContextBroker:
    """
    ContextBroker provides some utility errors to interact with an Orion Context Broker
    """

    keystoneURL: str
    orionURL: str
    service: str
    subservice: str
    _manager: Optional[Callable[..., requests.Response]]

    # pylint: disable=unused-argument,too-many-arguments
    def auth(self, session: Session, username: str, password: str, calls: Optional[int]=None, period: Optional[int]=None):
        """Create session manager and optionally use rate limit"""
        self._manager = sessionManager(
            keystoneURL=self.keystoneURL,
            username=username,
            password=password,
            headers={
                "Fiware-Service": self.service,
                "Fiware-ServicePath": self.subservice,
            }
        )
        if calls is not None and period is not None:
            self._manager = sleep_and_retry(limits(calls=calls, period=period)(self._manager))

    def get(self, session: Session, entityID: str, entityType: str) -> Optional[Any]:
        """Get a particular entity"""
        if self._manager is None:
            raise ValueError("ContextBroker must be initialized calling to auth(...)")
        url = f"{self.orionURL}/v2/entities/{entityID}"
        params = {"type": entityType}
        resp = self._manager(session, fetchMethod.GET, url, params=params)
        if resp is None:
            return None
        return resp.json()

    def post(self, session: Session, entityId: str, entityType: str, entity: Any):
        """Create a particular entity"""
        if self._manager is None:
            raise ValueError("ContextBroker must be initialized calling to auth(...)")
        url = f"{self.orionURL}/v2/entities"
        body = {'id': entityId, 'type': entityType}
        body.update(entity)
        self._manager(session, fetchMethod.POST,  url, body=body)

    @staticmethod
    def splitBatches(entities: Iterable[Any]) -> Generator[List[Any], None, None]:
        """Split a batch in sub-batches with no repeating IDs"""
        newBatch: List[Any] = list()
        hits: Set[str] = set()
        for item in entities:
            itemID = item['id']
            # Avoid repeating item IDs in a single batch
            if itemID in hits:
                yield newBatch
                newBatch = list()
                hits.clear()
            newBatch.append(item)
            hits.add(itemID)
        # If there is something in the batch, yield it
        if len(newBatch) > 0:
            yield newBatch

    def batch(self, session: Session, entities: List[Any]):
        """Perform batch entity update"""
        if self._manager is None:
            raise ValueError("ContextBroker must be initialized calling to auth(...)")
        url = f"{self.orionURL}/v2/op/update"
        for batch in ContextBroker.splitBatches(entities):
            body = {
                "actionType": "APPEND",
                "entities": batch,
            }
            self._manager(session, fetchMethod.POST,  url, body=body)

    def postAttribs(self, session: Session, entityId: str, entityType: str, entity: Any):
        """Add attributes to an entity"""
        if self._manager is None:
            raise ValueError("ContextBroker must be initialized calling to auth(...)")
        url = f"{self.orionURL}/v2/entities/{entityId}/attrs"
        params = {'type': entityType}
        self._manager(session, fetchMethod.POST, url, params=params, body=entity)

    def putAttribs(self, session: Session, entityId: str, entityType: str, entity: Any):
        """Add attributes to an entity"""
        if self._manager is None:
            raise ValueError("ContextBroker must be initialized calling to auth(...)")
        url = f"{self.orionURL}/v2/entities/{entityId}/attrs"
        params = {'type': entityType}
        self._manager(session, fetchMethod.PUT, url, params=params, body=entity)

    def delAttrib(self, session: Session, entityId: str, entityType: str, attrib: Any):
        """Delete attributes from an entity"""
        if self._manager is None:
            raise ValueError("ContextBroker must be initialized calling to auth(...)")
        url = f"{self.orionURL}/v2/entities/{entityId}/attrs/{attrib}"
        params = {'type': entityType}
        self._manager(session, fetchMethod.DELETE, url, params=params)
