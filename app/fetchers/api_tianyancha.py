"""
Fetches company intelligence from 天眼查 (Tianyancha) official API.
Requires TIANYANCHA_TOKEN environment variable or source.extra.token.
Returns empty list silently when no token is configured.
"""
import logging
import os
import asyncio
import httpx
from app.fetchers.base import BaseFetcher, RawItem

logger = logging.getLogger(__name__)

_BASE = "https://api.tianyancha.com/services/v4/open"


class TianyanchaFetcher(BaseFetcher):
    """Fetches company events from 天眼查 developer API."""

    def _headers(self, token: str) -> dict:
        return {
            "Authorization": token,
            "Content-Type": "application/json",
            "User-Agent": "news-platform/1.0",
        }

    async def fetch(self) -> list[RawItem]:
        token = self.source.extra.get("token") or os.environ.get("TIANYANCHA_TOKEN", "")
        company_name = self.source.extra.get("company_name", "")

        if not token:
            logger.debug("TianyanchaFetcher: no token configured, skipping")
            return []
        if not company_name:
            logger.error("TianyanchaFetcher: company_name missing in source.extra")
            return []

        headers = self._headers(token)
        async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
            company_id = await self._find_company(client, headers, company_name)
            if not company_id:
                logger.warning("TianyanchaFetcher: company not found: %s", company_name)
                return []

            results = await asyncio.gather(
                self._fetch_dynamics(client, headers, company_id, company_name),
                self._fetch_investments(client, headers, company_id, company_name),
                self._fetch_lawsuits(client, headers, company_id, company_name),
                return_exceptions=True,
            )

        items: list[RawItem] = []
        for r in results:
            if isinstance(r, list):
                items.extend(r)
        return items

    async def _find_company(self, client, headers, name: str) -> str | None:
        try:
            resp = await client.get(
                f"{_BASE}/search",
                params={"word": name, "pageNum": 1, "pageSize": 5},
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            rows = (data.get("data") or {}).get("data") or []
            if rows:
                return str(rows[0].get("id", ""))
        except Exception as exc:
            logger.error("Tianyancha search error: %s", exc)
        return None

    async def _fetch_dynamics(self, client, headers, cid: str, company: str) -> list[RawItem]:
        try:
            resp = await client.get(
                f"{_BASE}/dynamicSearch",
                params={"id": cid, "pageNum": 1, "pageSize": 20},
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            items = []
            for d in ((data.get("data") or {}).get("data") or []):
                title = d.get("title") or d.get("content", "")
                if not title:
                    continue
                items.append(RawItem(
                    title=f"[企业动态] {title}",
                    url=f"https://www.tianyancha.com/company/{cid}",
                    raw_text=d.get("description", ""),
                    extra={"event_type": "企业动态", "company": company},
                ))
            return items
        except Exception as exc:
            logger.error("Tianyancha dynamics error: %s", exc)
            return []

    async def _fetch_investments(self, client, headers, cid: str, company: str) -> list[RawItem]:
        try:
            resp = await client.get(
                f"{_BASE}/investmentList",
                params={"id": cid, "pageNum": 1, "pageSize": 20},
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            items = []
            for d in ((data.get("data") or {}).get("data") or []):
                name = d.get("companyName") or d.get("name", "")
                amount = d.get("regAmount") or d.get("amount", "")
                if not name:
                    continue
                title = f"[对外投资] {name}"
                if amount:
                    title += f"（{amount}）"
                items.append(RawItem(
                    title=title,
                    url=f"https://www.tianyancha.com/company/{cid}",
                    raw_text=str(d),
                    extra={"event_type": "对外投资", "company": company},
                ))
            return items
        except Exception as exc:
            logger.error("Tianyancha investments error: %s", exc)
            return []

    async def _fetch_lawsuits(self, client, headers, cid: str, company: str) -> list[RawItem]:
        try:
            resp = await client.get(
                f"{_BASE}/lawSuit",
                params={"id": cid, "pageNum": 1, "pageSize": 20},
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            items = []
            for d in ((data.get("data") or {}).get("data") or []):
                case_name = d.get("caseName") or d.get("title", "")
                if not case_name:
                    continue
                items.append(RawItem(
                    title=f"[司法案件] {case_name}",
                    url=f"https://www.tianyancha.com/company/{cid}",
                    raw_text=str(d),
                    extra={"event_type": "司法案件", "company": company},
                ))
            return items
        except Exception as exc:
            logger.error("Tianyancha lawsuits error: %s", exc)
            return []
