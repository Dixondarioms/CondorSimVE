"""El modelo real que corresponde a una unidad por su nombre («A-29 Super Tucano 1 (Hotel)» → a29).

Lo usan la migración 0045 (para las unidades de los ejercicios ya creados) y tools/modelos_en_plantillas.py (para las
plantillas). Solo cambia el modelo si la unidad no tiene uno o si el que tiene no corresponde a su nombre (por ejemplo,
un Super Tucano que figuraba como el avión de ataque K-8W).
"""

import re

# (clase, patron sobre el nombre, modelo); el primero que coincide gana
REGLAS = [
    ("ataque", r"super\s*tucano|\ba-29\b|emb-314", "a29"),
    ("ataque", r"\ba-37\b|dragonfly", "a37"),
    ("ataque", r"\bov-10\b|bronco", "ov10"),
    ("ataque", r"\bat-27\b|tucano|emb-312", "at27"),
    ("ataque", r"\bk-8", "ataque_ligero"),
    ("ataque", r"\bl-39\b|albatros", "l39"),
    ("ataque", r"yak-130", "yak130"),
    ("ataque", r"su-25", "su25"),
    ("ataque", r"\bp-3\b|orion", "p3c"),
    ("caza", r"kfir", "kfir"),
    ("caza", r"block\s*70|f-16v", "f16_b70"),
    ("caza", r"mirage\s*2000", "mirage2000"),
    ("caza", r"gripen|f-39", "gripen"),
    ("caza", r"mig-29", "mig29"),
    ("caza", r"su-35", "su35"),
    ("caza", r"\bf-5", "f5e"),
    ("helicoptero", r"mi-35|mi-24", "helo_ataque"),
    ("helicoptero", r"apache|ah-64", "ah64e"),
    ("helicoptero", r"mi-28", "mi28ne"),
    ("helicoptero", r"ka-52", "ka52"),
    ("helicoptero_artillado", r"bell\s*212|uh-1n", "bell212"),
    ("helicoptero_artillado", r"bell\s*412", "bell412"),
    ("helicoptero_artillado", r"cougar|as\s*532|super\s*puma", "as532"),
    ("helicoptero_artillado", r"caracal|h225", "h225m"),
    ("helicoptero_artillado", r"\bch-47", "ch47f"),
    ("helicoptero_artillado", r"\buh-60", "uh60l"),
    ("helicoptero_artillado", r"mi-26", "mi26"),
    ("helicoptero_artillado", r"mi-17|mi-8", "helo_transporte"),
    ("dron_ataque", r"\bmq-1\b|predator", "mq1"),
    ("dron_ataque", r"tb2|bayraktar", "tb2"),
    ("dron_ataque", r"mohajer|ansu", "uav_armado"),
    ("dron_ataque", r"wing\s*loong", "wingloong2"),
    ("dron_reconocimiento", r"scaneagle", "uav_reco"),
    ("dron_reconocimiento", r"heron", "heron"),
    ("dron_reconocimiento", r"hermes", "hermes450"),
    ("municion_merodeadora", r"shahed|geran", "shahed136"),
    ("municion_merodeadora", r"harop", "merodeadora"),
    ("municion_merodeadora", r"switchblade", "switchblade600"),
    ("municion_merodeadora", r"lancet", "lancet3"),
    ("avion_ge", r"\bp-3\b|orion|ep-3", "ep3e"),
    ("avion_ge", r"metro|merlin", "sa227_elint"),
    ("alerta_temprana", r"y-8w|kj-200", "y8w"),
    ("alerta_temprana", r"erieye|e-99|emb-145", "e99"),
    ("alerta_temprana", r"a-50", "a50u"),
    ("cisterna", r"kc-130", "kc130j"),
    ("cisterna", r"kc-767|j[uú]piter", "kc767"),
    ("antiaerea", r"buk-m3", "buk_m3"),
    ("antiaerea", r"buk-m2", "buk_m2e"),
    ("antiaerea", r"hawk", "mim23"),
    ("antiaerea", r"nasams", "nasams"),
    ("antiaerea", r"pantsir", "pantsir_s1"),
    ("antiaerea", r"\btor\b|tor-m", "tor_m2e"),
    ("antiaerea", r"patriot", "patriot"),
    ("antiaerea", r"s-400", "s400"),
    ("antiaerea", r"pechora|s-125", "pechora_2m"),
    ("antiaerea", r"s-300", "s300vm"),
    ("antiaerea_portatil", r"m-shorad", "m_shorad"),
    ("antiaerea_portatil", r"igla", "igla_s"),
    ("antiaerea_portatil", r"stinger", "stinger"),
    ("antiaerea_portatil", r"mistral", "mistral"),
    ("radar", r"jy-27", "jy27a"),
    ("radar", r"\bp-18\b", "p18"),
    ("radar", r"giraffe", "giraffe_amb"),
    ("blindado", r"t-72", "t72b1"),
    ("blindado", r"t-90", "t90a"),
    ("blindado", r"amx-30", "amx30"),
    ("blindado", r"scorpion", "scorpion90"),
    ("blindado", r"abrams|m1a2", "m1a2"),
    ("blindado", r"leopard", "leopard2a6"),
    ("infanteria", r"bmp-3", "bmp3"),
    ("infanteria", r"bmp-2", "bmp2"),
    ("infanteria", r"btr-80", "btr80a"),
    ("infanteria", r"vn-4", "vn4"),
    ("artilleria", r"smerch|bm-30", "bm30"),
    ("artilleria", r"grad|bm-21", "bm21"),
    ("artilleria", r"msta", "msta_s"),
    ("artilleria", r"nona", "nona_svk"),
    ("artilleria", r"himars", "himars"),
    ("artilleria", r"m109|paladin", "m109a7"),
    ("reconocimiento", r"brdm", "brdm2"),
    ("reconocimiento", r"tiuna", "tiuna"),
    ("fragata", r"mariscal\s*sucre|lupo", "lupo"),
    ("submarino", r"s[aá]balo|tipo\s*209|u-209", "u209"),
    ("patrullero", r"guaiquer", "guaiqueri"),
    ("patrullero", r"guaicamacuto", "guaicamacuto"),
    ("buque_desembarco", r"capana|goajira", "capana"),
]
_COMPILADAS = [(c, re.compile(p, re.IGNORECASE), m) for c, p, m in REGLAS]


def modelo_para(clase: str, nombre: str, actual: str | None, nombre_actual: str | None = None) -> str | None:
    """Modelo que corresponde a la unidad, o None si ya está bien (o no hay regla).

    `nombre_actual`: nombre del modelo que tiene ahora; si su nombre ya coincide con la regla, no se cambia."""
    for c, patron, modelo in _COMPILADAS:
        if c != clase or not patron.search(nombre or ""):
            continue
        if actual == modelo or (actual and nombre_actual and patron.search(nombre_actual)):
            return None
        return modelo
    return None
