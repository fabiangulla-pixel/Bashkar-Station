/* Bashkar Station Web — frontend vanilla.
   Espejo de _PAGINAS de app.py: mismos ids, emojis, nombres y grupos.
   Los paneles del primer tramo son funcionales; el resto muestra su guía HD
   (de core/guia_modulos.py vía /api/guias) y el aviso de "pendiente de portar". */
"use strict";

// ── Registro de páginas (espejo exacto de app.py::_PAGINAS) ──────────────────
const PAGINAS = [
  ["cfg",    "⚙",   "Configuración",  "Configuración del corpus",                       "flujo"],
  ["etz",    "✏️",  "Etiquetar",      "Etiquetar zonas de página (opcional)",           "flujo"],
  ["ocr",    "📄",  "Extracción OCR", "Extracción de texto por OCR",                    "flujo"],
  ["conv",   "⚡",  "Conversor PDF",  "Conversión masiva PDF→TXT (texto embebido)",     "flujo"],
  ["mmx",    "🧠",  "Extracción IA",  "Extracción multimodal estructurada (IA visión)", "flujo"],
  ["norm",   "📝",  "Normalizar",     "Revisión y normalización del texto",             "flujo"],
  ["seg",    "📋",  "Segmentar",      "Segmentación en artículos",                      "flujo"],
  ["anal",   "🔬",  "Analizar",       "Análisis textual y semántico",                   "flujo"],
  ["res",    "📈",  "Resultados",     "Resultados y exportación",                       "flujo"],
  ["ner",    "🏷",  "Entidades",      "Índice de entidades nombradas",                  "analisis"],
  ["anot",   "✍️",  "Anotar",         "Anotación semántica revisable",                  "analisis"],
  ["bsem",   "🔍",  "Búsqueda",       "Búsqueda semántica por similitud",               "analisis"],
  ["coloc",  "🔤",  "Collocates",     "Redes léxicas y concordancias",                  "analisis"],
  ["nov",    "🆕",  "Novedad",        "Detección de novedad y cambio discursivo",       "analisis"],
  ["red",    "🕸",  "Redes",          "Redes de co-ocurrencia",                         "analisis"],
  ["ling",   "🔭",  "Lingüística",    "Sintaxis, morfología, encuadre, polaridad",      "analisis"],
  ["sem",    "🧠",  "Semántico",      "Tono, léxico y estilo",                          "analisis"],
  ["top",    "🧩",  "Tópicos",        "Topic modeling del corpus",                      "analisis"],
  ["viz",    "🎨",  "Visualizar",     "Visualizaciones avanzadas",                      "analisis"],
  ["comp",   "📊",  "Comparativo",    "Análisis comparativo interno",                   "analisis"],
  ["comp2",  "🔀",  "Multi-corpus",   "Comparación entre proyectos",                    "analisis"],
  ["intxt",  "🔗",  "Intertexto",     "Análisis intertextual",                          "analisis"],
  ["meta",   "🌐",  "Metadatos URL",  "Metadatos desde URL externa",                    "analisis"],
  ["vis",    "🖼",  "Tipografía",     "Visual y tipografía",                            "analisis"],
  ["imgdesc","🎨",  "Desc. imágenes", "Descripción e iconografía de imágenes",          "analisis"],
  ["rep",    "📝",  "Reporte",        "Reporte narrativo (IA)",                         "salida"],
  ["dash",   "📊",  "Dashboard",      "Dashboard ejecutivo",                            "salida"],
  ["valid",  "✅",  "Validar",        "Validación humana y semáforo",                   "salida"],
  ["colab",  "👥",  "Colaborar",      "Colaboración y trazabilidad",                    "salida"],
];
const GRUPO_TITULOS = { flujo: "FLUJO DE TRABAJO", analisis: "ANÁLISIS OPCIONALES", salida: "SALIDA · COLABORACIÓN" };
// Paneles funcionales en este tramo web:
const IMPLEMENTADAS = new Set(["cfg", "conv", "norm", "seg", "anal", "res", "ner", "dash"]);

// ── Estado del frontend ──────────────────────────────────────────────────────
const S = {
  sesion: null, capacidades: {}, guias: {}, estado: {},
  grupo: "flujo", pagina: "cfg",
};

// ── Utilidades ───────────────────────────────────────────────────────────────
const $ = (sel) => document.querySelector(sel);
const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function api(ruta, opciones) {
  const r = await fetch(ruta, opciones);
  let datos = null;
  try { datos = await r.json(); } catch { /* descargas u otros */ }
  if (!r.ok) throw new Error((datos && datos.error) || `HTTP ${r.status}`);
  return datos;
}
const apiPost = (ruta, cuerpo) => api(ruta, {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify(cuerpo || {}),
});

function toast(msg, tipo = "ok", ms = 3800) {
  const div = document.createElement("div");
  div.className = `toast toast-${tipo}`;
  div.textContent = msg;
  $("#toasts").appendChild(div);
  setTimeout(() => div.remove(), ms);
}

async function refrescarEstado() {
  S.estado = await api("/api/estado");
  const p = S.estado.proyecto;
  $("#proyecto-activo").textContent = p ? `📁 ${p} — ${S.estado.publicacion}` : "— sin proyecto —";
}

// Polling de un trabajo con barra de progreso en `cont`
function seguirTrabajo(idTrabajo, cont, alTerminar) {
  cont.innerHTML = `<div class="prog-caja">
      <div class="prog-barra"><div class="prog-fill" id="pf"></div></div>
      <div class="prog-msg" id="pm">Iniciando…</div>
      <div class="prog-log" id="pl"></div></div>`;
  const fill = cont.querySelector("#pf"), msg = cont.querySelector("#pm"), log = cont.querySelector("#pl");
  const timer = setInterval(async () => {
    try {
      const t = await api(`/api/trabajo?id=${idTrabajo}`);
      fill.style.width = `${t.progreso}%`;
      msg.textContent = `${t.progreso}% — ${t.mensaje || t.estado}`;
      log.textContent = (t.log || []).join("\n");
      log.scrollTop = log.scrollHeight;
      if (t.estado !== "corriendo") {
        clearInterval(timer);
        if (t.estado === "ok") {
          toast("Proceso completado ✓");
          await refrescarEstado();
          if (alTerminar) alTerminar(t);
        } else {
          toast(t.error || "El proceso falló", "error", 6000);
          msg.textContent = `ERROR: ${t.error}`;
        }
      }
    } catch (e) { clearInterval(timer); toast(e.message, "error"); }
  }, 800);
}

// ── Shell: login, navegación ─────────────────────────────────────────────────
async function iniciar() {
  S.sesion = await api("/api/sesion");
  $("#version-tag").textContent = `web v${S.sesion.version}`;
  if (S.sesion.modo_publico && !S.sesion.autenticado) {
    $("#login-overlay").classList.remove("oculto");
    $("#login-btn").onclick = login;
    $("#login-pass").onkeydown = (e) => { if (e.key === "Enter") login(); };
    return;
  }
  await arrancarApp();
}

async function login() {
  try {
    await apiPost("/api/login", { password: $("#login-pass").value });
    $("#login-overlay").classList.add("oculto");
    await arrancarApp();
  } catch (e) {
    const el = $("#login-error");
    el.textContent = e.message; el.classList.remove("oculto");
  }
}

async function arrancarApp() {
  $("#app").classList.remove("oculto");
  [S.capacidades, S.guias] = await Promise.all([api("/api/capacidades"), api("/api/guias")]);
  await refrescarEstado();
  document.querySelectorAll(".ab-btn").forEach((b) => {
    b.onclick = () => {
      document.querySelectorAll(".ab-btn").forEach((x) => x.classList.remove("ab-activo"));
      b.classList.add("ab-activo");
      S.grupo = b.dataset.grupo;
      pintarSidebar();
      const primera = PAGINAS.find((p) => p[4] === S.grupo);
      navegar(primera[0]);
    };
  });
  $("#btn-guardar").onclick = async () => {
    try { await apiPost("/api/proyecto/guardar"); toast("Proyecto guardado 💾"); }
    catch (e) { toast(e.message, "error"); }
  };
  pintarSidebar();
  navegar("cfg");
}

function pintarSidebar() {
  $("#sidebar-titulo").textContent = GRUPO_TITULOS[S.grupo];
  const lista = $("#sidebar-lista");
  lista.innerHTML = "";
  PAGINAS.filter((p) => p[4] === S.grupo).forEach(([pid, emoji, nombre]) => {
    const b = document.createElement("button");
    b.className = "sb-item" + (pid === S.pagina ? " sb-activo" : "");
    b.dataset.pid = pid;
    b.innerHTML = `<span>${emoji}</span> ${esc(nombre)}` +
      (IMPLEMENTADAS.has(pid) ? "" : `<span class="sb-badge" title="Pendiente de portar">🖥</span>`);
    b.onclick = () => navegar(pid);
    lista.appendChild(b);
  });
}

function navegar(pid) {
  S.pagina = pid;
  document.querySelectorAll(".sb-item").forEach((x) =>
    x.classList.toggle("sb-activo", x.dataset.pid === pid));
  const [, emoji, nombre, desc] = PAGINAS.find((p) => p[0] === pid);
  const cont = $("#contenido");
  cont.innerHTML = `<div class="page-titulo">${emoji} ${esc(nombre)}</div>
    <div class="page-sub">${esc(desc)}</div><div class="page-linea"></div>
    <div id="page-body"></div>`;
  const body = $("#page-body");
  const render = RENDERS[pid] || renderStub;
  Promise.resolve(render(body, pid)).catch((e) => {
    body.innerHTML = `<div class="cap-off">Error cargando el panel: ${esc(e.message)}</div>`;
  });
}

function cardGuia(pid) {
  const g = S.guias[pid];
  if (!g) return "";
  return `<div class="card"><h3>📖 Guía del módulo</h3><div class="guia">
    <p><strong>Qué es:</strong> ${esc(g.que_es)}</p>
    <p style="margin-top:6px"><strong>Para qué:</strong> ${esc(g.para_que)}</p>
    <p style="margin-top:6px"><strong>Resultado:</strong> ${esc(g.resultado)}</p>
    <p style="margin-top:6px"><strong>Cómo interpretar:</strong> ${esc(g.interpretar)}</p>
  </div></div>`;
}

function renderStub(body, pid) {
  body.innerHTML = `
    <div class="stub-aviso">🖥 Este panel aún vive solo en la app de escritorio.
    Se porta a la web en el siguiente tramo — la lógica ya es compartida
    (core/), solo falta esta vista.</div>` + cardGuia(pid);
}

// ── Renders funcionales ──────────────────────────────────────────────────────
const RENDERS = {};

// ⚙ Configuración / Proyecto
RENDERS.cfg = async (body) => {
  const proyectos = await api("/api/proyectos");
  const filas = proyectos.map((p) =>
    `<tr class="click" data-ruta="${esc(p.ruta)}"><td>${esc(p.nombre)}</td>
     <td>${esc(p.modificado || "")}</td></tr>`).join("");
  const etapas = Object.entries(S.estado.estado_etapas || {}).map(([k, v]) =>
    `<span class="etapa etapa-${v}">${k}: ${v}</span>`).join("");
  body.innerHTML = `
    <div class="card"><h3>Estado del proyecto</h3>
      <div class="etapas">${etapas || "—"}</div>
      <p class="guia" style="margin-top:10px">
        Números en corpus: <strong>${(S.estado.numeros || []).length}</strong> ·
        Artículos segmentados: <strong>${S.estado.n_articulos}</strong> ·
        Entidades NER: <strong>${S.estado.n_entidades}</strong></p>
    </div>
    <div class="card"><h3>Nuevo proyecto</h3>
      <div class="fila">
        <div><label>Nombre</label><input type="text" id="np-nombre" placeholder="Estampa 1939"></div>
        <div><label>Publicación</label><input type="text" id="np-pub" placeholder="Revista Estampa"></div>
        <div><label>Período</label><input type="text" id="np-per" placeholder="1938-1940"></div>
        <div style="flex:0"><button class="btn btn-primario" id="np-crear">➕ Crear</button></div>
      </div>
    </div>
    <div class="card"><h3>Abrir proyecto existente</h3>
      ${proyectos.length ? `<table><thead><tr><th>Nombre</th><th>Modificado</th></tr></thead>
        <tbody>${filas}</tbody></table>` : `<p class="guia">No hay proyectos todavía.</p>`}
    </div>` + cardGuia("cfg");
  $("#np-crear").onclick = async () => {
    try {
      await apiPost("/api/proyecto/nuevo", {
        nombre: $("#np-nombre").value, publicacion: $("#np-pub").value, periodo: $("#np-per").value,
      });
      toast("Proyecto creado ✓"); await refrescarEstado(); navegar("cfg");
    } catch (e) { toast(e.message, "error"); }
  };
  body.querySelectorAll("tr.click").forEach((tr) => {
    tr.onclick = async () => {
      try {
        await apiPost("/api/proyecto/cargar", { ruta: tr.dataset.ruta });
        toast("Proyecto cargado ✓"); await refrescarEstado(); navegar("cfg");
      } catch (e) { toast(e.message, "error"); }
    };
  });
};

// ⚡ Conversor PDF (texto embebido — funciona sin Tesseract)
RENDERS.conv = async (body) => {
  const capPdf = S.capacidades.pymupdf || {};
  body.innerHTML = `
    ${capPdf.disponible ? "" : `<div class="cap-off">PyMuPDF no está disponible en este servidor: ${esc(capPdf.detalle)}</div>`}
    <div class="card"><h3>1 · Subir PDFs</h3>
      <p class="guia">PDFs con capa de texto embebida (BNC / Paper Capture). La conversión
      extrae el texto sin re-OCR y alimenta directamente el módulo Normalizar.</p>
      <p style="margin-top:10px"><input type="file" id="conv-archivos" multiple accept=".pdf"></p>
      <div id="conv-subida" class="guia"></div>
    </div>
    <div class="card"><h3>2 · Convertir</h3>
      <button class="btn btn-primario" id="conv-ir" ${capPdf.disponible ? "" : "disabled"}>⚡ Convertir a texto</button>
      <div id="conv-prog"></div>
    </div>` + cardGuia("conv");
  $("#conv-archivos").onchange = async (ev) => {
    const div = $("#conv-subida");
    for (const archivo of ev.target.files) {
      div.innerHTML += `<p>Subiendo ${esc(archivo.name)}…</p>`;
      try {
        const r = await fetch("/api/subir", {
          method: "POST", body: archivo,
          headers: { "X-Filename": encodeURIComponent(archivo.name) },
        });
        const j = await r.json();
        if (!r.ok) throw new Error(j.error || "error");
        div.innerHTML += `<p style="color:var(--ok)">✓ ${esc(j.nombre)} (${Math.round(j.bytes / 1024)} KB)</p>`;
      } catch (e) { div.innerHTML += `<p style="color:var(--error)">✗ ${esc(e.message)}</p>`; }
    }
  };
  $("#conv-ir").onclick = async () => {
    try {
      const { trabajo } = await apiPost("/api/conv/iniciar", {});
      seguirTrabajo(trabajo, $("#conv-prog"), () => navegar("norm"));
    } catch (e) { toast(e.message, "error"); }
  };
};

// 📝 Normalizar
RENDERS.norm = async (body) => {
  const numeros = S.estado.numeros || [];
  const ops = numeros.map((n) => `<option value="${esc(n.nombre)}">${esc(n.nombre)} (${n.paginas} págs)</option>`).join("");
  body.innerHTML = `
    ${numeros.length ? "" : `<div class="stub-aviso">No hay textos en el corpus todavía — usa el Conversor PDF o la Extracción OCR primero.</div>`}
    <div class="card"><h3>Normalizar textos</h3>
      <p class="guia">Corrige errores de digitalización preservando arcaísmos legítimos
      del español de los años 30 («habia», «fué», «Luégo») — son datos históricos, no errores.</p>
      <div class="fila" style="margin-top:10px">
        <div><label>Número</label><select id="norm-numero"><option value="">— todos —</option>${ops}</select></div>
        <div style="flex:0"><button class="btn btn-primario" id="norm-ir" ${numeros.length ? "" : "disabled"}>📝 Normalizar</button></div>
      </div>
      <div id="norm-prog"></div>
    </div>
    <div class="card"><h3>Ver páginas</h3>
      <div class="fila">
        <div><label>Número</label><select id="ver-numero">${ops}</select></div>
        <div><label>Página</label><select id="ver-pagina"></select></div>
      </div>
      <div id="ver-texto" class="texto-visor" style="margin-top:12px">…</div>
    </div>` + cardGuia("norm");
  $("#norm-ir").onclick = async () => {
    try {
      const { trabajo } = await apiPost("/api/norm/iniciar", { numero: $("#norm-numero").value });
      seguirTrabajo(trabajo, $("#norm-prog"));
    } catch (e) { toast(e.message, "error"); }
  };
  const cargarPaginas = async () => {
    const numero = $("#ver-numero").value;
    const info = numeros.find((n) => n.nombre === numero);
    const sel = $("#ver-pagina");
    sel.innerHTML = "";
    if (!info) return;
    for (let i = 1; i <= info.paginas; i++) {
      const nombre = `p${String(i).padStart(4, "0")}.txt`;
      sel.innerHTML += `<option value="${nombre}">${nombre}</option>`;
    }
    await cargarTexto();
  };
  const cargarTexto = async () => {
    const numero = $("#ver-numero").value, pagina = $("#ver-pagina").value;
    if (!numero || !pagina) return;
    try {
      const d = await api(`/api/pagina?numero=${encodeURIComponent(numero)}&pagina=${encodeURIComponent(pagina)}`);
      $("#ver-texto").textContent = d.texto || "(página vacía)";
    } catch (e) { $("#ver-texto").textContent = e.message; }
  };
  $("#ver-numero").onchange = cargarPaginas;
  $("#ver-pagina").onchange = cargarTexto;
  if (numeros.length) await cargarPaginas();
};

// 📋 Segmentar
RENDERS.seg = async (body) => {
  body.innerHTML = `
    <div class="card"><h3>Segmentar en artículos</h3>
      <p class="guia">Convierte cada página en una unidad de contenido y consolida las
      continuaciones («Pasa a la pág. N»). Detecta título, autor, sección y tipo de página.</p>
      <p style="margin-top:10px"><button class="btn btn-primario" id="seg-ir">📋 Segmentar corpus</button></p>
      <div id="seg-prog"></div>
    </div>
    <div class="card"><h3>Artículos (${S.estado.n_articulos})</h3><div id="seg-tabla">…</div></div>
    ` + cardGuia("seg");
  $("#seg-ir").onclick = async () => {
    try {
      const { trabajo } = await apiPost("/api/seg/iniciar", {});
      seguirTrabajo(trabajo, $("#seg-prog"), () => pintarTabla());
    } catch (e) { toast(e.message, "error"); }
  };
  const pintarTabla = async () => {
    const arts = await api("/api/articulos");
    if (!arts.length) { $("#seg-tabla").innerHTML = `<p class="guia">Sin artículos todavía.</p>`; return; }
    const filas = arts.map((a) =>
      `<tr class="click" data-i="${a.i}"><td>${esc(a.id)}</td><td>${esc(a.numero)}</td>
       <td>${esc(a.titulo)}</td><td>${esc(a.autor)}</td><td>${esc(a.seccion)}</td><td>${a.palabras}</td></tr>`).join("");
    $("#seg-tabla").innerHTML = `<table><thead><tr><th>ID</th><th>Número</th><th>Título</th>
      <th>Autor</th><th>Sección</th><th>Palabras</th></tr></thead><tbody>${filas}</tbody></table>
      <div id="seg-visor" class="texto-visor oculto" style="margin-top:12px"></div>`;
    $("#seg-tabla").querySelectorAll("tr.click").forEach((tr) => {
      tr.onclick = async () => {
        const art = await api(`/api/articulo?i=${tr.dataset.i}`);
        const visor = $("#seg-visor");
        visor.classList.remove("oculto");
        visor.textContent = art.texto || "(sin texto)";
      };
    });
  };
  await pintarTabla();
};

// 🔬 Analizar (léxico básico — primer tramo)
RENDERS.anal = async (body) => {
  body.innerHTML = `
    <div class="stub-aviso">Primer tramo web: frecuencias, secciones y volumen.
    LDA, campos semánticos y Word2Vec siguen en el escritorio (próximo tramo).</div>
    <div class="card"><h3>Análisis léxico del corpus</h3>
      <button class="btn btn-primario" id="anal-ir">🔬 Analizar</button>
      <div id="anal-prog"></div>
    </div>
    <div id="anal-res"></div>` + cardGuia("anal");
  const pintar = async () => {
    const a = await api("/api/analisis");
    if (!a || !a.top_terminos) return;
    const max = a.top_terminos.length ? a.top_terminos[0][1] : 1;
    const barras = a.top_terminos.slice(0, 30).map(([t, n]) =>
      `<div class="barra-h"><span class="bh-label">${esc(t)}</span>
       <div class="bh-fill" style="width:${Math.round(n / max * 55)}%"></div>
       <span class="bh-num">${n}</span></div>`).join("");
    const secciones = (a.secciones || []).map(([s, n]) => `<tr><td>${esc(s)}</td><td>${n}</td></tr>`).join("");
    $("#anal-res").innerHTML = `
      <div class="card"><h3>Resumen</h3><p class="guia">
        Artículos: <strong>${a.n_articulos}</strong> ·
        Palabras: <strong>${a.total_palabras.toLocaleString("es")}</strong> ·
        Vocabulario: <strong>${a.vocabulario.toLocaleString("es")}</strong> términos</p></div>
      <div class="card"><h3>Términos más frecuentes</h3>${barras}</div>
      <div class="card"><h3>Distribución por sección</h3>
        <table><thead><tr><th>Sección</th><th>Artículos</th></tr></thead><tbody>${secciones}</tbody></table></div>`;
  };
  $("#anal-ir").onclick = async () => {
    try {
      const { trabajo } = await apiPost("/api/anal/iniciar", {});
      seguirTrabajo(trabajo, $("#anal-prog"), pintar);
    } catch (e) { toast(e.message, "error"); }
  };
  await pintar();
};

// 🏷 Entidades (NER)
RENDERS.ner = async (body) => {
  const capSpacy = S.capacidades.spacy_es || {};
  body.innerHTML = `
    ${capSpacy.disponible ? "" : `<div class="cap-off">spaCy español no está instalado en este servidor — el NER no puede correr aquí.</div>`}
    <div class="card"><h3>Reconocimiento de entidades</h3>
      <p class="guia">Pipeline offline con spaCy (personas, lugares, organizaciones).
      La validación con IA (Claude/Ollama) se porta en el siguiente tramo.</p>
      <p style="margin-top:10px"><button class="btn btn-primario" id="ner-ir" ${capSpacy.disponible ? "" : "disabled"}>🏷 Extraer entidades</button></p>
      <div id="ner-prog"></div>
    </div>
    <div id="ner-res"></div>` + cardGuia("ner");
  const pintar = async () => {
    const indice = await api("/api/ner");
    const cats = Object.entries(indice || {}).filter(([, v]) => v && Object.keys(v).length);
    if (!cats.length) { $("#ner-res").innerHTML = ""; return; }
    $("#ner-res").innerHTML = cats.map(([cat, ents]) => {
      const orden = Object.entries(ents).sort((x, y) => y[1].length - x[1].length);
      const chips = orden.slice(0, 80).map(([nombre, arts]) =>
        `<span class="chip">${esc(nombre)} <small>×${arts.length}</small></span>`).join("");
      return `<div class="card"><h3>${esc(cat)} (${orden.length})</h3>${chips}</div>`;
    }).join("");
  };
  $("#ner-ir").onclick = async () => {
    try {
      const { trabajo } = await apiPost("/api/ner/iniciar", {});
      seguirTrabajo(trabajo, $("#ner-prog"), pintar);
    } catch (e) { toast(e.message, "error"); }
  };
  await pintar();
};

// 📈 Resultados / exportación
RENDERS.res = async (body) => {
  body.innerHTML = `
    <div class="card"><h3>Exportar corpus</h3>
      <p class="guia">Los exportes se generan en el servidor y se descargan al navegador.</p>
      <p style="margin-top:12px">
        <button class="btn" data-fmt="tei">📜 XML-TEI P5</button>
        <button class="btn" data-fmt="bibtex">📚 BibTeX</button>
        <button class="btn" data-fmt="csv_articulos">📋 CSV artículos</button>
        <button class="btn" data-fmt="csv_ner">🏷 CSV entidades</button>
      </p>
      <div id="res-msg" class="guia" style="margin-top:8px"></div>
    </div>` + cardGuia("res");
  body.querySelectorAll("[data-fmt]").forEach((b) => {
    b.onclick = async () => {
      const msg = $("#res-msg");
      msg.textContent = "Generando…";
      try {
        const { archivo } = await apiPost("/api/exportar", { formato: b.dataset.fmt });
        msg.innerHTML = `✓ Listo: <a href="/api/descargar?nombre=${encodeURIComponent(archivo)}"
          style="color:var(--azul-claro)">${esc(archivo)}</a>`;
        toast("Exporte generado ✓");
      } catch (e) { msg.textContent = ""; toast(e.message, "error"); }
    };
  });
};

// 📊 Dashboard
RENDERS.dash = async (body) => {
  await refrescarEstado();
  const e = S.estado;
  const numeros = (e.numeros || []).map((n) =>
    `<tr><td>${esc(n.nombre)}</td><td>${n.paginas}</td></tr>`).join("");
  const etapas = Object.entries(e.estado_etapas || {}).map(([k, v]) =>
    `<span class="etapa etapa-${v}">${k}: ${v}</span>`).join("");
  body.innerHTML = `
    <div class="card"><h3>Proyecto</h3><p class="guia">
      <strong>${esc(e.publicacion)}</strong> · ${esc(e.periodo || "sin período")}<br>
      Artículos: <strong>${e.n_articulos}</strong> · Entidades: <strong>${e.n_entidades}</strong></p>
      <div class="etapas" style="margin-top:10px">${etapas}</div></div>
    <div class="card"><h3>Números del corpus</h3>
      ${numeros ? `<table><thead><tr><th>Número</th><th>Páginas</th></tr></thead><tbody>${numeros}</tbody></table>`
                : `<p class="guia">Corpus vacío.</p>`}</div>` + cardGuia("dash");
};

// OCR / etiquetador / mmx: paneles con dependencia de host — aviso de capacidad
RENDERS.ocr = async (body) => {
  const t = S.capacidades.tesseract || {}, p = S.capacidades.poppler || {};
  body.innerHTML = `
    ${t.disponible ? "" : `<div class="cap-off">Tesseract no está disponible en este servidor (${esc(t.detalle)}).
      En el despliegue web usa el Conversor PDF (texto embebido) o la Extracción IA.</div>`}
    ${p.disponible ? "" : `<div class="cap-off">Poppler no está disponible (${esc(p.detalle)}).</div>`}
    <div class="stub-aviso">🖥 Las 7 rutas de OCR (Tesseract, Claude Vision, BNC, Kraken…)
      siguen en la app de escritorio. Este tramo web cubre el Conversor PDF; el panel OCR
      completo se porta después.</div>` + cardGuia("ocr");
};

iniciar().catch((e) => {
  document.body.innerHTML = `<div style="padding:40px;font-family:sans-serif;color:#F48771">
    Error arrancando Bashkar Web: ${esc(e.message)}</div>`;
});
