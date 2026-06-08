import logging
import httpx
from app.fetchers.base import BaseFetcher, RawItem

logger = logging.getLogger(__name__)

HTTP_TIMEOUT = 15


class HuggingFaceFetcher(BaseFetcher):
    async def fetch(self) -> list:
        base = self.source.feed_url.rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, trust_env=False) as client:
                resp = await client.get(
                    f"{base}/models",
                    params={"sort": "trending", "limit": 20, "direction": -1},
                )
                resp.raise_for_status()
                models = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error("HuggingFace API returned %s: %s", exc.response.status_code, exc)
            return []
        except httpx.RequestError as exc:
            logger.error("HuggingFace network error: %s", exc)
            return []
        except Exception as exc:
            logger.error("HuggingFace unexpected error: %s", exc)
            return []

        items: list = []
        for model in models:
            model_id = model.get("modelId") or model.get("id", "")
            if not model_id:
                continue
            url = f"https://huggingface.co/{model_id}"
            desc = model.get("cardData", {}).get("description", "") or ""
            items.append(RawItem(
                title=model_id, url=url, raw_text=desc,
                extra={"downloads": model.get("downloads", 0),
                       "likes": model.get("likes", 0)},
            ))
        return items
