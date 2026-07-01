from fastapi import APIRouter

from app.api.v1.categories import router as categories_router
from app.api.v1.leaderboard import router as leaderboard_router
from app.api.v1.markets import router as markets_router
from app.api.v1.wallets import router as wallets_router
from app.api.v1.alerts import router as alerts_router
from app.api.v1.follow import router as follow_router
from app.api.v1.portfolio import router as portfolio_router

api_router = APIRouter()

api_router.include_router(leaderboard_router, prefix="/leaderboard", tags=["leaderboard"])
api_router.include_router(wallets_router, prefix="/wallets", tags=["wallets"])
api_router.include_router(markets_router, prefix="/markets", tags=["markets"])
api_router.include_router(categories_router, prefix="", tags=["categories"])
api_router.include_router(alerts_router, prefix="/alerts", tags=["alerts"])
api_router.include_router(follow_router, prefix="/follow", tags=["follow"])
api_router.include_router(portfolio_router, prefix="/portfolio", tags=["portfolio"])
