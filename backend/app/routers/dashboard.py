from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models import Usuario
from app.schemas.dashboard import DashboardOut
from app.services import DashboardService

router = APIRouter(prefix="/dashboard", tags=["Dashboard / Painel"])


@router.get(
    "",
    response_model=DashboardOut,
    summary="Retorna contadores operacionais, pendências de empréstimo e últimas movimentações",
)
def obter_dashboard(
    _usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardOut:
    return DashboardService(db).obter_dados()
