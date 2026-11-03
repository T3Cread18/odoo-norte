import logging
import math
import re
from urllib.parse import unquote

import requests

_logger = logging.getLogger(__name__)

_NUM = r"(-?\d{1,3}\.\d+)"
# De más a menos preciso: el pin exacto de un lugar (!3d..!4d..), un
# parámetro q=/query=/ll=/destination=, el centro del mapa (@lat,lng) y por
# último unas coordenadas sueltas "10.0661, -69.3207".
_PATRONES = (
    r"!3d%s!4d%s" % (_NUM, _NUM),
    r"[?&](?:q|query|ll|destination|center)=(?:loc:)?%s\s*,\s*%s" % (_NUM, _NUM),
    r"@%s,%s" % (_NUM, _NUM),
    r"%s\s*,\s*%s" % (_NUM, _NUM),
)
_ENLACE_CORTO = re.compile(
    r"https?://(?:maps\.app\.goo\.gl|goo\.gl/maps|g\.co/kgs)/\S+")


def _buscar_coordenadas(texto):
    # En las URL el espacio llega como "+" (p. ej. Google Maps resuelve un
    # pin a ".../maps/search/9.58,+-69.23"); sin esto no se reconoce el par
    # y se acababa tomando otra coordenada del HTML de la página.
    texto = unquote(unquote(texto)).replace("+", " ")
    for patron in _PATRONES:
        m = re.search(patron, texto)
        if m:
            lat, lng = float(m.group(1)), float(m.group(2))
            if -90 <= lat <= 90 and -180 <= lng <= 180 \
                    and (lat, lng) != (0.0, 0.0):
                return lat, lng
    return None


def leer_ubicacion(texto):
    """Coordenadas (lat, lng) a partir de lo que pegue el contratista:
    coordenadas, enlace de Google Maps o enlace corto maps.app.goo.gl
    (se sigue la redirección). None si viene vacío; ValueError si no se
    entienden."""
    texto = (texto or "").strip()
    if not texto:
        return None
    coords = _buscar_coordenadas(texto)
    if coords:
        return coords
    corto = _ENLACE_CORTO.search(texto)
    if corto:
        try:
            resp = requests.get(corto.group(0), allow_redirects=True,
                                timeout=8)
            coords = _buscar_coordenadas(resp.url) \
                or _buscar_coordenadas(resp.text[:200000])
        except requests.RequestException:
            _logger.warning("No se pudo abrir el enlace %s", corto.group(0))
        if coords:
            return coords
    raise ValueError(texto)


def url_mapa(lat, lng):
    if not (lat or lng):
        return False
    return "https://www.google.com/maps?q=%.7f,%.7f" % (lat, lng)


def distancia_m(lat1, lng1, lat2, lng2):
    """Distancia en metros entre dos puntos (haversine)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) \
        * math.sin(math.radians(lng2 - lng1) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))
