"The main class for a client to connect to the Relay service API"
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional, Union

import requests

from .client import new_session
from .events import Events
from .outputs import Outputs
from .util import json_object_hook


class UnresolvableException(Exception):
    pass


class DynamicMetaclass(type):

    def __getattr__(self, name: str) -> Dynamic:
        return Dynamic(name)


class Dynamic(metaclass=DynamicMetaclass):
    """A query interface for inspecting a spec.

    This class allows arbitrary traversal that can be converted to a query to
    the metadata API.
    """

    def __init__(self, name: str, parent: Optional[Dynamic] = None) -> None:
        self._name = name
        self._parent = parent

    def __getattr__(self, name: str) -> Dynamic:
        return Dynamic(name, parent=self)

    def __str__(self) -> str:
        if self._parent is None:
            return self._name

        return '{0}[{1}]'.format(self._parent, json.dumps(self._name))


class Interface:
    """An Interface object connects client code to the metadata service."""

    def __init__(self, api_url: Optional[str] = None,
                 configure_logging: Optional[bool] = None):
        self._client = new_session(api_url=api_url)

        if configure_logging is None:
            configure_logging = os.environ.get('RELAY') == 'true'

        if configure_logging:
            logging.basicConfig(
                format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                level=logging.INFO,
            )

    def get(self, q: Optional[Union[Dynamic, str]] = None) -> Any:
        """Retrieve values from the metadata service

        Args:
            q: A particular parameter to query the value of.

        Returns:
            The value of the queried parameter as a string.
            If no query was provided, all available parameters will be
            returned in a json map

        Raises:
            requests.exceptions.HTTPError with status_code 422 if the requested
            parameter is missing.
        """

        params = {}
        if q is not None:
            params['q'] = str(q)

        r = self._client.get('http+api://api/spec', params=params)
        r.raise_for_status()

        data = json.loads(r.text, object_hook=json_object_hook)
        if not data['complete']:
            raise UnresolvableException()

        return data['value']

    def get_or_default(self,
            q: Optional[Union[Dynamic, str]],
            default: Optional[Any] = None,
            ) -> Any:
        """Retrieve optional values from the metadata service, or supplies a
        default when absent.

        Args:
            q: A particular parameter to query the value of.
            default: A default value to return when the parameter is absent
            from the spec

        Returns:
            The value of the queried parameter as a string, or the supplied
            default value. If no query was provided, all available parameters
            will be returned in a json map
        """

        try:
            return self.get(q)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 422:
                return default
            raise

    @property
    def events(self) -> Events:
        """Accessor for Events methods"""
        return Events(self._client)

    @property
    def outputs(self) -> Outputs:
        """Accessor for Outputs methods"""
        return Outputs(self._client)
