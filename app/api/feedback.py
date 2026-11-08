import asyncio

from fastapi import APIRouter, Request

from app.api.deps import CurrentUser
from app.api.schemas import FeedbackRequest, FeedbackResponse
from app.core.errors import NotFound
from app.core.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackResponse)
async def give_feedback(body: FeedbackRequest, user: CurrentUser, request: Request) -> FeedbackResponse:
    if request.app.state.run_owners.owner(body.run_id) != user.username:
        raise NotFound("No answer with this run id was found for you.")

    log.info("user_feedback", run_id=body.run_id, score=body.score)
    client = request.app.state.feedback_client
    if client is None:
        return FeedbackResponse(recorded=True, sent_to_langsmith=False)

    await asyncio.to_thread(client.create_feedback, run_id=body.run_id, key="user_rating",
                            score=body.score, comment=body.comment)
    return FeedbackResponse(recorded=True, sent_to_langsmith=True)
