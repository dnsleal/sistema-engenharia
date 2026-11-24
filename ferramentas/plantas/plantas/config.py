"""Configuração: nomes de camadas, tolerâncias, pé-direito padrão.

O padrão fica em config_padrao.json (ao lado da pasta do pacote). Um arquivo do
usuário só precisa trazer as chaves que quer trocar.
"""
from __future__ import annotations

import copy
import fnmatch
import json
from pathlib import Path

ARQ_PADRAO = Path(__file__).resolve().parent.parent / "config_padrao.json"


def _mesclar(base: dict, extra: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _mesclar(out[k], v)
        else:
            out[k] = v
    return out


def carregar(caminho: str | Path | None = None) -> dict:
    cfg = json.loads(ARQ_PADRAO.read_text(encoding="utf-8"))
    if caminho:
        cfg = _mesclar(cfg, json.loads(Path(caminho).read_text(encoding="utf-8")))
    return cfg


def casa_camada(camada: str, padroes: list[str]) -> bool:
    """Compara nome de camada com padrões tipo 'AMBIENTE*' (sem diferenciar maiúsculas)."""
    c = (camada or "").upper()
    return any(fnmatch.fnmatchcase(c, p.upper()) for p in padroes)


def categoria_da_camada(camada: str, cfg: dict) -> str | None:
    for cat in ("ambientes", "terreno", "construida", "permeavel"):
        if casa_camada(camada, cfg["camadas"].get(cat, [])):
            return cat
    return None


def camadas_de_area(cfg: dict) -> list[str]:
    c = cfg["camadas"]
    return c.get("ambientes", []) + c.get("terreno", []) + c.get("construida", []) + c.get("permeavel", [])
