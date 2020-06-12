import os
from typing import Mapping, Optional, Union
from urllib.parse import urljoin, urlsplit, urlunsplit

from requests import PreparedRequest, Response, Session
from requests.adapters import HTTPAdapter

from .typing import HTTPClientCertificate, HTTPTimeout


class MetadataAPIAdapter(HTTPAdapter):

    def __init__(self, base_url: Optional[str] = None) -> None:
        if base_url is None:
            base_url = os.environ['METADATA_API_URL']

        self._base_url = base_url

        super(MetadataAPIAdapter, self).__init__()

    def send(self, request: PreparedRequest, stream: bool = False,
             timeout: Optional[HTTPTimeout] = None,
             verify: Union[bool, str] = True,
             cert: Optional[HTTPClientCertificate] = None,
             proxies: Optional[Mapping[str, str]] = None) -> Response:
        (_, _, path, query, fragment) = urlsplit(request.url or '')
        request.prepare_url(
            urljoin(
                self._base_url,
                urlunsplit(('', '', path, query, fragment)),
            ),
            {},
        )

        return super(MetadataAPIAdapter, self).send(
            request,
            stream=stream,
            timeout=timeout,
            verify=verify,
            cert=cert,
            proxies=proxies,
        )


def new_session(api_url: Optional[str] = None) -> Session:
    sess = Session()
    sess.mount('http+api://', MetadataAPIAdapter(base_url=api_url))
    return sess
