from fastapi import APIRouter, HTTPException

from backend.app.models.schemas import NewsSubscriptionCreate, NewsSubscriptionResponse, NewsSubscriptionUpdate
from backend.app.news.service import news_service

router = APIRouter(prefix="/news", tags=["News & Briefings"])


def _clean(item):
    if item and "enabled" in item: item["enabled"] = bool(item["enabled"])
    return item


@router.post("/subscriptions", response_model=NewsSubscriptionResponse, status_code=201)
async def create_subscription(request: NewsSubscriptionCreate):
    try: return _clean(news_service.create_subscription(**request.model_dump()))
    except ValueError as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/subscriptions", response_model=list[NewsSubscriptionResponse])
async def list_subscriptions(): return [_clean(x) for x in news_service.subscriptions()]


@router.patch("/subscriptions/{subscription_id}", response_model=NewsSubscriptionResponse)
async def update_subscription(subscription_id: int, request: NewsSubscriptionUpdate):
    try: item = news_service.update_subscription(subscription_id, **request.model_dump(exclude_unset=True))
    except ValueError as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not item: raise HTTPException(status_code=404, detail="Subscription not found")
    return _clean(item)


@router.delete("/subscriptions/{subscription_id}", status_code=204)
async def delete_subscription(subscription_id: int):
    if not news_service.delete_subscription(subscription_id): raise HTTPException(status_code=404, detail="Subscription not found")


@router.post("/subscriptions/{subscription_id}/enable", response_model=NewsSubscriptionResponse)
async def enable_subscription(subscription_id: int):
    item = news_service.update_subscription(subscription_id, enabled=1)
    if not item: raise HTTPException(status_code=404, detail="Subscription not found")
    return _clean(item)


@router.post("/subscriptions/{subscription_id}/disable", response_model=NewsSubscriptionResponse)
async def disable_subscription(subscription_id: int):
    item = news_service.update_subscription(subscription_id, enabled=0)
    if not item: raise HTTPException(status_code=404, detail="Subscription not found")
    return _clean(item)


@router.post("/run")
async def run_briefing(): return await news_service.run("scheduled")


@router.get("/briefings")
async def list_briefings(): return news_service.history()


@router.get("/briefings/{briefing_id}")
async def get_briefing(briefing_id: int):
    briefing = news_service.get_briefing(briefing_id)
    if not briefing: raise HTTPException(status_code=404, detail="Briefing not found")
    return briefing


@router.get("/events")
async def list_events():
    return news_service.events()


@router.get("/events/{event_id}")
async def get_event(event_id: int):
    event = news_service.get_event(event_id)
    if not event: raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.post("/events/{event_id}/dismiss")
async def dismiss_event(event_id: int):
    event = news_service.dismiss_event(event_id)
    if not event: raise HTTPException(status_code=404, detail="Event not found")
    return event
