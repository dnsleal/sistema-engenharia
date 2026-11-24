"""Estruturas de dados comuns aos leitores (DXF/PDF) e às saídas (Excel/Word/SVG).

Toda geometria já chega aqui em METROS, qualquer que seja a unidade do arquivo.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from shapely.geometry import Polygon


@dataclass
class Alerta:
    nivel: str            # 'erro' | 'atencao' | 'info'
    mensagem: str
    x: float | None = None  # posição (m) para marcar no desenho de conferência
    y: float | None = None

    def __str__(self) -> str:
        return f"[{self.nivel.upper()}] {self.mensagem}"


@dataclass
class Poligono:
    geom: Polygon
    camada: str
    origem: str           # 'polilinha', 'linhas', 'hachura', 'circulo', 'pdf-caminho', 'pdf-linhas'
    ref: str = ""         # handle do DXF ou nº do caminho no PDF, para achar a entidade


@dataclass
class Texto:
    texto: str
    x: float
    y: float
    altura: float
    camada: str


@dataclass
class Desenho:
    """O que um leitor extrai do arquivo, antes de qualquer interpretação."""
    arquivo: str
    formato: str                       # 'dxf' | 'dwg' | 'pdf'
    unidade: str                       # descrição da unidade/escala usada
    fator_m: float                     # metros por unidade do arquivo
    poligonos: list[Poligono] = field(default_factory=list)
    textos: list[Texto] = field(default_factory=list)
    blocos: Counter = field(default_factory=Counter)        # (nome, camada) -> quantidade
    camadas: dict = field(default_factory=dict)             # camada -> {'fechados': n, 'abertos': n, 'textos': n}
    alertas: list[Alerta] = field(default_factory=list)
    tem_camadas: bool = True           # PDF sem camadas (OCG) = False
    paredes: list = field(default_factory=list)      # polígonos (paredes desenhadas fechadas), em m
    linhas_paredes: list = field(default_factory=list)       # LineString de paredes desenhadas com linhas
    linhas_esquadrias: list = field(default_factory=list)    # LineString de portas/janelas


@dataclass
class Area:
    """Um polígono já classificado (ambiente, terreno, construída, permeável...)."""
    categoria: str
    nome: str
    camada: str
    geom: Polygon
    pe_direito: float | None = None
    area_declarada: float | None = None   # área escrita no desenho (ex.: "12,50 m²"), para conferir
    origem: str = ""
    numero: int = 0

    @property
    def area(self) -> float:
        return self.geom.area

    @property
    def perimetro(self) -> float:
        return self.geom.exterior.length + sum(i.length for i in self.geom.interiors)

    @property
    def area_parede(self) -> float | None:
        """Área bruta de paredes (perímetro × pé-direito), sem descontar vãos."""
        return None if self.pe_direito is None else self.perimetro * self.pe_direito


@dataclass
class Resultado:
    desenho: Desenho
    ambientes: list[Area]
    outras: dict[str, list[Area]]       # 'terreno', 'construida', 'permeavel' -> áreas
    resumo: dict
    alertas: list[Alerta]
    modo: str                           # 'camadas' ou 'textos' (como os ambientes foram achados)
