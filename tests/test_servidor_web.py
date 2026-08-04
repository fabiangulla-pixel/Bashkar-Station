"""
Tests del servidor web (servidor_web.py) — patrón NativoWeb.

Levantan un ThreadingHTTPServer REAL en puerto efímero (127.0.0.1:0) dentro
de un fixture y lo golpean con requests: es loopback puro (sin red externa)
y la única forma honesta de verificar cookies, 401 y aislamiento de sesiones.
"""

import importlib
import json
import sys
import threading
import time
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))


# ══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════════════
def _levantar(sw):
    servidor = sw.ThreadingHTTPServer(("127.0.0.1", 0), sw.ManejadorAPI)
    servidor.daemon_threads = True
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    return servidor, f"http://127.0.0.1:{servidor.server_address[1]}"


@pytest.fixture
def servidor_local(tmp_path, monkeypatch):
    """Servidor en modo LOCAL (sin contraseña), con la carpeta de proyectos
    desviada a tmp_path para no tocar Documents del usuario."""
    monkeypatch.delenv("BASHKAR_PASSWORD", raising=False)
    import servidor_web as sw

    sw = importlib.reload(sw)
    from core import project_manager as pm

    dir_proys = tmp_path / "proyectos"
    dir_proys.mkdir()
    monkeypatch.setattr(pm, "_dir_proyectos", lambda: dir_proys)
    servidor, base = _levantar(sw)
    yield sw, base
    servidor.shutdown()
    sw.ESTADO_LOCAL.limpiar()


@pytest.fixture
def servidor_publico(monkeypatch):
    """Servidor en modo PÚBLICO (multi-sesión con contraseña)."""
    monkeypatch.setenv("BASHKAR_PASSWORD", "clave-de-prueba")
    import servidor_web as sw

    sw = importlib.reload(sw)
    servidor, base = _levantar(sw)
    yield sw, base
    servidor.shutdown()
    for ses in list(sw.SESIONES.values()):
        ses.limpiar()


def _esperar_trabajo(base, sesion, trabajo_id, timeout=60):
    fin = time.time() + timeout
    while time.time() < fin:
        t = sesion.get(f"{base}/api/trabajo?id={trabajo_id}", timeout=10).json()
        if t["estado"] != "corriendo":
            return t
        time.sleep(0.2)
    raise TimeoutError("El trabajo no terminó a tiempo")


def _pdf_de_prueba() -> bytes:
    """PDF de 2 páginas con texto embebido, estilo artículo de prensa."""
    import fitz

    doc = fitz.open()
    cuerpo = (
        "LA POLITICA EUROPEA Y AMERICA\n\n"
        "Por J. Garcia\n\n" + "El presidente Alfonso Lopez visito Bogota para hablar de la guerra "
        "en Espana y de la situacion europea. La revista registra el ambiente "
        "cultural de la capital y los debates del momento politico. " * 8
    )
    for _ in range(2):
        pagina = doc.new_page()
        pagina.insert_textbox(fitz.Rect(50, 50, 545, 780), cuerpo, fontsize=10)
    datos = doc.tobytes()
    doc.close()
    return datos


# ══════════════════════════════════════════════════════════════════════════════
# Higiene del handler
# ══════════════════════════════════════════════════════════════════════════════
def test_do_post_lee_el_body_una_sola_vez():
    """En HTTP/1.1 keep-alive el body debe leerse EXACTAMENTE una vez, en un
    punto compartido, antes de despachar. Una segunda lectura desincroniza la
    siguiente petición de la conexión (bug real del proyecto de referencia)."""
    fuente = (Path(__file__).parent.parent / "servidor_web.py").read_text(encoding="utf-8")
    assert fuente.count("self.rfile.read") == 1


def test_modulos_core_sin_gui():
    """La lógica compartida no importa tkinter ni del lado del servidor."""
    fuente = (Path(__file__).parent.parent / "servidor_web.py").read_text(encoding="utf-8")
    assert "import tkinter" not in fuente
    fuente_estado = (Path(__file__).parent.parent / "core" / "estado.py").read_text(
        encoding="utf-8"
    )
    assert "import tkinter" not in fuente_estado


# ══════════════════════════════════════════════════════════════════════════════
# Modo local
# ══════════════════════════════════════════════════════════════════════════════
def test_local_sesion_y_capacidades(servidor_local):
    _, base = servidor_local
    s = requests.Session()
    ses = s.get(f"{base}/api/sesion", timeout=10).json()
    assert ses == {"modo_publico": False, "autenticado": True, "version": ses["version"]}
    caps = s.get(f"{base}/api/capacidades", timeout=10).json()
    for clave in ("tesseract", "poppler", "pymupdf", "spacy_es", "proveedores_locales"):
        assert clave in caps
    assert caps["proveedores_locales"]["disponible"] is True  # modo local


def test_local_estaticos_y_traversal(servidor_local):
    _, base = servidor_local
    s = requests.Session()
    r = s.get(f"{base}/", timeout=10)
    assert r.status_code == 200 and "Bashkar" in r.text
    assert s.get(f"{base}/styles.css", timeout=10).status_code == 200
    # path traversal bloqueado
    r = s.get(f"{base}/../servidor_web.py", timeout=10)
    assert r.status_code == 404
    r = s.get(f"{base}/..%2Fservidor_web.py", timeout=10)
    assert r.status_code == 404


def test_local_guias_cubren_los_paneles_registrados(servidor_local):
    """Cada panel de la Activity Bar debe tener su guía HD.

    Antes esto fijaba el número exacto (29) y se rompía al añadir un panel, sin
    decir cuál faltaba. Lo que importa no es el conteo sino el invariante: que
    no haya paneles huérfanos de guía. Si en el futuro se decide que algún panel
    no la lleva, se añade aquí como excepción explícita y documentada.
    """
    _, base = servidor_local
    guias = requests.get(f"{base}/api/guias", timeout=10).json()

    import app as appmod
    registrados = {p[0] for p in appmod.BashkarApp._PAGINAS}

    sin_guia = registrados - set(guias)
    assert not sin_guia, f"Paneles sin guía HD: {sorted(sin_guia)}"
    assert len(guias) >= len(registrados)
    assert "que_es" in guias["cfg"]


def test_local_pipeline_completo(servidor_local):
    """Flujo entero por HTTP: proyecto → subir PDF → convertir → normalizar →
    segmentar → analizar → exportar → descargar. La misma lógica core/ que
    usa el escritorio, ejercitada desde el segundo frontend."""
    pytest.importorskip("fitz")
    _, base = servidor_local
    s = requests.Session()

    # Proyecto nuevo
    r = s.post(
        f"{base}/api/proyecto/nuevo",
        json={"nombre": "Prueba Web", "publicacion": "Estampa", "periodo": "1939"},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    assert r.json()["publicacion"] == "Estampa"

    # Subir PDF con texto embebido
    r = s.post(
        f"{base}/api/subir",
        data=_pdf_de_prueba(),
        headers={"X-Filename": "numero_prueba.pdf"},
        timeout=10,
    )
    assert r.status_code == 200 and r.json()["nombre"] == "numero_prueba.pdf"

    # Convertir (texto embebido → 03_ocr)
    r = s.post(f"{base}/api/conv/iniciar", json={}, timeout=10)
    assert r.status_code == 200, r.text
    t = _esperar_trabajo(base, s, r.json()["trabajo"])
    assert t["estado"] == "ok", t

    estado = s.get(f"{base}/api/estado", timeout=10).json()
    assert estado["numeros"], estado
    assert estado["numeros"][0]["paginas"] == 2

    # Ver una página
    numero = estado["numeros"][0]["nombre"]
    r = s.get(f"{base}/api/pagina?numero={numero}&pagina=p0001.txt", timeout=10)
    assert r.status_code == 200
    assert "presidente" in r.json()["texto"].lower()

    # Normalizar
    r = s.post(f"{base}/api/norm/iniciar", json={}, timeout=10)
    t = _esperar_trabajo(base, s, r.json()["trabajo"])
    assert t["estado"] == "ok", t

    # Segmentar
    r = s.post(f"{base}/api/seg/iniciar", json={}, timeout=10)
    t = _esperar_trabajo(base, s, r.json()["trabajo"])
    assert t["estado"] == "ok", t
    arts = s.get(f"{base}/api/articulos", timeout=10).json()
    # Debe segmentar de verdad, no solo devolver una lista (bug real cazado
    # con CDP: pasar la carpeta del número en vez de la carpeta 03_ocr padre
    # hacía que segmentar_numero buscara una ruta duplicada inexistente y
    # siempre devolviera 0 artículos sin lanzar ningún error).
    assert isinstance(arts, list) and len(arts) >= 1, arts

    # Detalle de artículo + análisis + exportes
    art = s.get(f"{base}/api/articulo?i=0", timeout=10).json()
    assert "texto" in art and art["texto"]

    r = s.post(f"{base}/api/anal/iniciar", json={}, timeout=10)
    t = _esperar_trabajo(base, s, r.json()["trabajo"])
    assert t["estado"] == "ok", t
    analisis = s.get(f"{base}/api/analisis", timeout=10).json()
    assert analisis["top_terminos"]

    r = s.post(f"{base}/api/exportar", json={"formato": "csv_articulos"}, timeout=30)
    assert r.status_code == 200, r.text
    nombre = r.json()["archivo"]
    r = s.get(f"{base}/api/descargar?nombre={nombre}", timeout=10)
    assert r.status_code == 200 and len(r.content) > 20

    # Guardar el proyecto no revienta
    assert s.post(f"{base}/api/proyecto/guardar", json={}, timeout=10).status_code == 200


def test_local_pagina_traversal_bloqueado(servidor_local):
    _, base = servidor_local
    s = requests.Session()
    s.post(f"{base}/api/proyecto/nuevo", json={"nombre": "Seguridad"}, timeout=10)
    r = s.get(f"{base}/api/pagina?numero=..&pagina=..%2Fservidor_web.py", timeout=10)
    assert r.status_code in (400, 404)
    r = s.get(f"{base}/api/descargar?nombre=..%2F..%2Fsecreto.txt", timeout=10)
    assert r.status_code == 404


def test_local_errores_utiles(servidor_local):
    _, base = servidor_local
    s = requests.Session()
    # segmentar sin corpus → error claro, no 500
    r = s.post(f"{base}/api/seg/iniciar", json={}, timeout=10)
    assert r.status_code == 400 and "03_ocr" in r.json()["error"]
    # trabajo inexistente
    assert s.get(f"{base}/api/trabajo?id=nope", timeout=10).status_code == 404
    # exportar formato desconocido
    r = s.post(f"{base}/api/exportar", json={"formato": "xyz"}, timeout=10)
    assert r.status_code == 400


# ══════════════════════════════════════════════════════════════════════════════
# Modo público
# ══════════════════════════════════════════════════════════════════════════════
def test_publico_requiere_sesion(servidor_publico):
    _, base = servidor_publico
    s = requests.Session()
    ses = s.get(f"{base}/api/sesion", timeout=10).json()
    assert ses["modo_publico"] is True and ses["autenticado"] is False
    # Sin login: 401 en API protegida
    assert s.get(f"{base}/api/estado", timeout=10).status_code == 401
    assert s.post(f"{base}/api/proyecto/nuevo", json={"nombre": "x"}, timeout=10).status_code == 401
    # Los estáticos sí se sirven (pantalla de login)
    assert s.get(f"{base}/", timeout=10).status_code == 200


def test_publico_login(servidor_publico):
    _, base = servidor_publico
    s = requests.Session()
    r = s.post(f"{base}/api/login", json={"password": "incorrecta"}, timeout=10)
    assert r.status_code == 401
    r = s.post(f"{base}/api/login", json={"password": "clave-de-prueba"}, timeout=10)
    assert r.status_code == 200
    cookie = r.headers.get("Set-Cookie", "")
    assert "sid=" in cookie and "HttpOnly" in cookie
    # Sin X-Forwarded-Proto=https NO debe llevar Secure (HTTP plano local)
    assert "Secure" not in cookie
    # Con la cookie, la API responde
    assert s.get(f"{base}/api/estado", timeout=10).status_code == 200


def test_publico_sesiones_aisladas(servidor_publico):
    """Dos visitantes con sesiones distintas jamás ven los datos del otro."""
    _, base = servidor_publico
    a, b = requests.Session(), requests.Session()
    for s in (a, b):
        assert (
            s.post(
                f"{base}/api/login", json={"password": "clave-de-prueba"}, timeout=10
            ).status_code
            == 200
        )
    a.post(f"{base}/api/proyecto/nuevo", json={"nombre": "Proyecto de A"}, timeout=10)
    proys_a = a.get(f"{base}/api/proyectos", timeout=10).json()
    proys_b = b.get(f"{base}/api/proyectos", timeout=10).json()
    assert any("proyecto_de_a" in p["ruta"] for p in proys_a)
    assert proys_b == []
    # La config de A no contamina a B
    a.post(f"{base}/api/config", json={"publicacion": "Solo de A"}, timeout=10)
    estado_b = b.get(f"{base}/api/estado", timeout=10).json()
    assert estado_b["publicacion"] != "Solo de A"


def test_publico_no_persiste_api_keys(servidor_publico):
    """En modo público las claves viven solo en memoria de la sesión: el
    .bashkar guardado en disco JAMÁS contiene una clave."""
    sw, base = servidor_publico
    s = requests.Session()
    s.post(f"{base}/api/login", json={"password": "clave-de-prueba"}, timeout=10)
    s.post(f"{base}/api/proyecto/nuevo", json={"nombre": "Con claves"}, timeout=10)
    s.post(f"{base}/api/config", json={"api_keys": {"anthropic": "sk-ant-SECRETO"}}, timeout=10)
    s.post(f"{base}/api/proyecto/guardar", json={}, timeout=10)
    ses_srv = next(iter(sw.SESIONES.values()))
    # En memoria sí está (la sesión la necesita para llamar a la IA)…
    assert ses_srv.st.api_keys["anthropic"] == "sk-ant-SECRETO"
    # …pero en disco no.
    contenido = ses_srv.ruta_proyecto.read_text(encoding="utf-8")
    assert "SECRETO" not in contenido


def test_publico_no_acepta_rutas_del_servidor(servidor_publico):
    """Un visitante no puede cargar archivos arbitrarios del servidor ni
    fijar out_dir a una ruta del host."""
    sw, base = servidor_publico
    s = requests.Session()
    s.post(f"{base}/api/login", json={"password": "clave-de-prueba"}, timeout=10)
    r = s.post(f"{base}/api/proyecto/cargar", json={"ruta": "C:/Windows/system.ini"}, timeout=10)
    assert r.status_code == 400
    s.post(f"{base}/api/proyecto/nuevo", json={"nombre": "P"}, timeout=10)
    s.post(f"{base}/api/config", json={"out_dir": "C:/Windows"}, timeout=10)
    ses_srv = next(iter(sw.SESIONES.values()))
    assert "Windows" not in str(ses_srv.st.out_dir)


def test_publico_capacidades_ocultan_proveedores_locales(servidor_publico):
    _, base = servidor_publico
    caps = requests.get(f"{base}/api/capacidades", timeout=10).json()
    assert caps["proveedores_locales"]["disponible"] is False


def test_json_invalido_no_revienta(servidor_local):
    _, base = servidor_local
    r = requests.post(
        f"{base}/api/proyecto/nuevo",
        data=b"esto no es json {",
        headers={"Content-Type": "application/json"},
        timeout=10,
    )
    assert r.status_code == 400
    assert "JSON" in r.json()["error"]
