from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models import Usuario
from app.schemas.importacao import ResultadoImportacao
from app.services import ImportacaoService

router = APIRouter(prefix="/equipamentos/importar", tags=["Importação de Equipamentos"])


@router.post(
    "",
    response_model=ResultadoImportacao,
    status_code=status.HTTP_200_OK,
    summary="Importa equipamentos via arquivo CSV com suporte a upsert e relatório de erros",
)
async def importar_planilha_csv(
    arquivo: UploadFile = File(..., description="Arquivo CSV com dados de equipamentos"),
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResultadoImportacao:
    conteudo = await arquivo.read()
    return ImportacaoService(db).importar_csv(conteudo, usuario=usuario)
