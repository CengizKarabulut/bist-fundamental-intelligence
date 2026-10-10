"""Opt-in MKK/KAP authenticated financial-statement adapter.

The public MKK API Portal requires account approval, an API key, and a
subscribed API product. The product's endpoint and JSON schema are NOT
publicly confirmed in this repository. Therefore the adapter is OFF by
default and never pretends it has downloaded a KAP report.

Once an authorized KAP financial-statement product returns its published
schema, a verified explicit mapper converts that schema to the canonical
row/period layout below. A mismatch fails closed instead of silently
miscalculating BIST valuations. Credentials are environment-only.
"""
from __future__ import annotations

import json
import os
import re
import ssl
from functools import lru_cache
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import pandas as pd

MAX_BYTES=12_000_000
SUPPORTED_GROUPS={"UFRS","XI_29"}
STATEMENTS={"balance_sheet","income_stmt","cashflow"}


class KapConfigurationError(ValueError):
    pass


class KapSchemaError(ValueError):
    pass


def _trusted_mkk_url(url):
    url=urlparse(url)
    host=(url.hostname or "").lower()
    # No arbitrary HTTP or user-chosen server allowed for the API key.
    if url.scheme != "https" or not (host == "mkk.com.tr" or host.endswith(".mkk.com.tr")
                                   or host == "kap.org.tr" or host.endswith(".kap.org.tr")):
        raise KapConfigurationError("Only official HTTPS MKK/KAP hosts permitted")
    if url.username or url.password or url.fragment or url.port not in (None,443):
        raise KapConfigurationError("Credentials, fragments and non-HTTPS ports forbidden")
    return True


def _canonical_json_to_frames(payload, *, symbol, group):
    """Parse ONLY canonical contract; unknown official schemas must be mapped.

    Required format:
      { "symbol": "ASELS", "financial_group": "XI_29",
        "currency": "TRY", "unit_multiplier_try": 1,
        "statements": { "balance_sheet": [
           {"label":"Özkaynaklar","period":"2026Q2","amount":123}, ...] }
      }
    Annual data may be represented separately in "annual_statements".
    All monetary statement inputs must already be expressed in nominal TRY,
    or declare unit_multiplier_try (e.g. 1000 for figures in thousand TRY).
    """
    if not isinstance(payload,dict) or str(payload.get("symbol","")).upper()!=symbol:
        raise KapSchemaError("KAP symbol missing/mismatch")
    if payload.get("financial_group")!=group or payload.get("currency") not in ("TRY","TL"):
        raise KapSchemaError("KAP group/currency mismatch")
    mult=payload.get("unit_multiplier_try")
    if mult is None or not isinstance(mult,(int,float)) or mult<=0:
        raise KapSchemaError("Money unit multiplier must be explicit")
    frames={}
    for mode,sections in (("quarterly",payload.get("statements")),("annual",payload.get("annual_statements"))):
        if not isinstance(sections,dict):
            if mode=="annual": continue
            raise KapSchemaError("Quarterly statement data missing")
        for statement, facts in sections.items():
            if statement not in STATEMENTS: continue
            if not isinstance(facts,list):
                raise KapSchemaError("Statement facts must be arrays")
            items={}
            for record in facts:
                if not isinstance(record,dict):
                    raise KapSchemaError("Malformed financial fact")
                label=str(record.get("label") or "").strip()
                period=str(record.get("period") or "").strip()
                if mode=="quarterly":
                    if not re.fullmatch(r"20\d{2}Q[1-4]",period):
                        raise KapSchemaError("Invalid quarterly period")
                elif not re.fullmatch(r"20\d{2}",period):
                    raise KapSchemaError("Invalid annual period")
                if not label or re.search(r"[^\S ]",label):
                    raise KapSchemaError("Invalid fact label")
                try:
                    amt=float(record["amount"])*mult
                except (ValueError,TypeError,KeyError):
                    raise KapSchemaError("Invalid fact amount")
                if not pd.notna(amt) or amt in (float("inf"),float("-inf")):
                    raise KapSchemaError("Non-finite financial amount")
                row=items.setdefault(label,{})
                if period in row and row[period]!=amt:
                    raise KapSchemaError("Conflicting duplicate financial fact")
                row[period]=amt
            df=pd.DataFrame.from_dict(items,orient="index",dtype=float)
            if not df.empty:
                df=df.reindex(columns=sorted(df.columns))
            frames[(mode,statement)]=df
    return frames


class OfficialKapStatements:
    """Read-only authorized API client with a verified interchange contract."""

    def __init__(self,symbol,api_url_template,api_key,api_key_header="X-API-Key"):
        self.symbol=str(symbol).upper()
        if not re.fullmatch(r"[A-Z0-9]{2,12}",self.symbol):
            raise KapConfigurationError("Invalid stock symbol")
        if not api_key or not api_url_template:
            raise KapConfigurationError("API enrollment and endpoint required")
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9-]{1,60}",api_key_header):
            raise KapConfigurationError("Invalid API key header")
        # A URL returned by the portal is mandatory. We never guess REST paths.
        self.api_url_template=api_url_template
        self.api_key=api_key
        self.api_key_header=api_key_header

    @lru_cache(maxsize=4)
    def _fetch(self,group):
        if group not in SUPPORTED_GROUPS:
            raise KapConfigurationError("Unsupported financial group")
        try:
            url=self.api_url_template.format(symbol=self.symbol,financial_group=group)
        except (KeyError,ValueError) as exc:
            raise KapConfigurationError("Invalid KAP endpoint template") from exc
        _trusted_mkk_url(url)
        request=Request(
            url,headers={self.api_key_header:self.api_key,"Accept":"application/json",
                         "User-Agent":"BIST-Fundamental-Intelligence/1.2"},
            method="GET",
        )
        # Automatic redirects are forbidden: auth keys cannot travel to third
        # party hosts; an explicit API product host must be configured.
        from urllib.request import build_opener, HTTPSHandler, HTTPRedirectHandler
        class NoRedirect(HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                raise KapConfigurationError("API redirect forbidden")
        opener=build_opener(HTTPSHandler(context=ssl.create_default_context()),NoRedirect())
        with opener.open(request,timeout=20) as response:
            raw=response.read(MAX_BYTES+1)
            if len(raw)>MAX_BYTES:
                raise KapSchemaError("Official response too large")
        try:
            payload=json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError,ValueError) as exc:
            raise KapSchemaError("KAP response is not canonical JSON") from exc
        return _canonical_json_to_frames(payload,symbol=self.symbol,group=group)

    def _statement(self,statement,quarterly=False,financial_group="XI_29",last_n=None):
        group=financial_group or "XI_29"
        frames=self._fetch(group)
        mode="quarterly" if quarterly else "annual"
        df=frames.get((mode,statement),pd.DataFrame())
        if not df.empty and isinstance(last_n,int):
            df=df.iloc[:,-last_n:]
        return df.copy()

    def get_balance_sheet(self,**kwargs):
        return self._statement("balance_sheet",**kwargs)

    def get_income_stmt(self,**kwargs):
        return self._statement("income_stmt",**kwargs)

    def get_cashflow(self,**kwargs):
        return self._statement("cashflow",**kwargs)


def configured_official_kap_ticker(symbol):
    """KAP mode never starts unless both product endpoint and API key exist."""
    endpoint=os.environ.get("KAP_API_FINANCIALS_URL_TEMPLATE","").strip()
    key=os.environ.get("KAP_API_KEY","").strip()
    if not endpoint and not key:
        return None
    if not endpoint or not key:
        raise KapConfigurationError("Both KAP_API_FINANCIALS_URL_TEMPLATE and KAP_API_KEY required")
    return OfficialKapStatements(
        symbol,endpoint,key,os.environ.get("KAP_API_KEY_HEADER","X-API-Key")
    )
