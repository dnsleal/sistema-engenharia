"""Números no padrão brasileiro."""


def num(v, casas: int = 2) -> str:
    if v is None:
        return "—"
    s = f"{v:,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def m2(v) -> str:
    return "—" if v is None else f"{num(v)} m²"


def m(v) -> str:
    return "—" if v is None else f"{num(v)} m"


def pct(v) -> str:
    return "—" if v is None else f"{num(v * 100)} %"
