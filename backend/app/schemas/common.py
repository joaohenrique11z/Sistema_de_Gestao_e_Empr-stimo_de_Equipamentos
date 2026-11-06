from math import ceil
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Pagina(BaseModel, Generic[T]):
    items: list[T]
    total: int
    pagina: int
    tamanho_pagina: int
    total_paginas: int

    @classmethod
    def criar(cls, items: list[T], total: int, pagina: int, tamanho_pagina: int) -> "Pagina[T]":
        return cls(
            items=items,
            total=total,
            pagina=pagina,
            tamanho_pagina=tamanho_pagina,
            total_paginas=ceil(total / tamanho_pagina) if total else 0,
        )


class Mensagem(BaseModel):
    detail: str

