// Demo de solo lectura de Bashkar Station. Sin dependencias ni compilación:
// lee los JSON de datos/ que genera scripts/generar_demo.py.
"use strict";

const CAT = { personas: "Persona", lugares: "Lugar", organizaciones: "Organización",
  fechas: "Fecha", obras_publicaciones: "Obra", eventos_historicos: "Evento" };
const cache = {};
const main = document.getElementById("contenido");

const fmt = (n) => Number(n).toLocaleString("es-CO");
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const enc = encodeURIComponent;

async function json(ruta) {
  if (!cache[ruta]) {
    cache[ruta] = fetch(ruta).then((r) => {
      if (!r.ok) throw new Error(`${ruta}: ${r.status}`);
      return r.json();
    });
  }
  return cache[ruta];
}
const corpus = () => json("datos/corpus.json");
const numero = (id) => json(`datos/numeros/${id}.json`);
const entidades = () => json("datos/entidades.json");

function pintar(html, titulo) {
  main.innerHTML = html;
  document.title = (titulo ? titulo + " · " : "") + "Estampa 1939 · Bashkar Station";
  main.focus({ preventScroll: true });
  window.scrollTo(0, 0);
}

function etiqueta(cat, texto) {
  const c = CAT[cat] ? cat : "otras";
  return `<a class="etiqueta ${c}" href="#/entidad/${enc(cat)}/${enc(texto)}" title="${esc(CAT[cat] || cat)}">${esc(texto)}</a>`;
}

function etiquetasDe(ents) {
  return Object.entries(ents || {}).flatMap(([c, l]) => l.map((t) => etiqueta(c, t))).join(" ") ||
    '<span class="vacio">Sin entidades detectadas.</span>';
}

function numeroDeUnidad(id) { return id.replace(/-a\d{4}$/, ""); }

// ── Vistas ──────────────────────────────────────────────────────────────────

async function vistaInicio() {
  const c = await corpus();
  const k = c.cifras;
  const nums = c.numeros.map((n) => `
    <li><a href="#/numero/${enc(n.id)}">
      <img src="img/${enc(n.id)}/${enc(n.portada || "p0001")}_mini.webp" alt="Portada de Estampa, ${esc(n.etiqueta)}" loading="lazy">
      <div><b>${esc(n.etiqueta)}</b><br><small>${fmt(n.paginas)} páginas · ${fmt(n.unidades)} unidades</small></div>
    </a></li>`).join("");
  pintar(`
    <h1><em>${esc(c.publicacion || "Estampa")}</em>, ${esc(c.periodo)}</h1>
    <p class="sub">Revista semanal ilustrada de ${esc(c.lugar || "Bogotá")}. Cinco números leídos
      de punta a punta con <a href="https://github.com/fabiangulla-pixel/Bashkar-Station">Bashkar Station</a>:
      transcripción, unidades editoriales, entidades nombradas y sus relaciones.</p>
    <ul class="cifras">
      <li><b>${fmt(k.numeros)}</b><span>números</span></li>
      <li><b>${fmt(k.paginas)}</b><span>páginas</span></li>
      <li><b>${fmt(k.unidades)}</b><span>unidades editoriales</span></li>
      <li><b>${fmt(k.entidades_indice || k.entidades_unicas)}</b><span>entidades nombradas</span></li>
      <li><b>${fmt(k.menciones)}</b><span>menciones en unidades</span></li>
    </ul>
    <h2>Números</h2>
    <ul class="numeros">${nums}</ul>
    <h2>Explorar</h2>
    <p><a href="#/entidades">Índice de entidades</a> (personas, lugares, organizaciones y fechas) ·
       <a href="#/grafo">Grafo de co-ocurrencias</a> ·
       <a href="#/descargas">Descargar el corpus en TEI P5, CSV y BibTeX</a></p>`);
}

async function vistaNumero(id) {
  const [c, n] = await Promise.all([corpus(), numero(id)]);
  const meta = c.numeros.find((x) => x.id === id) || { etiqueta: id };
  const mini = n.paginas.map((p) => `
    <li><a href="#/pagina/${enc(id)}/${p.p}">
      <img src="img/${enc(id)}/${p.p}_mini.webp" alt="Página ${parseInt(p.p.slice(1), 10)}" loading="lazy">
      ${parseInt(p.p.slice(1), 10)}</a></li>`).join("");
  const filas = n.unidades.map((u) => `
    <tr><td><a href="#/unidad/${enc(u.id)}">${esc(u.titulo)}</a></td>
      <td>${esc(u.seccion)}</td><td>${u.paginas.map((p) => parseInt(p.slice(1), 10)).join(", ")}</td>
      <td>${fmt(u.palabras)}</td></tr>`).join("");
  pintar(`
    <p><a href="#/">← Todos los números</a></p>
    <h1><em>Estampa</em>, ${esc(meta.etiqueta)}</h1>
    <p class="sub">${fmt(n.paginas.length)} páginas · ${fmt(n.unidades.length)} unidades editoriales</p>
    <h2>Páginas</h2><ul class="miniaturas">${mini}</ul>
    <h2>Unidades editoriales</h2>
    <table><thead><tr><th>Título</th><th>Sección</th><th>Páginas</th><th>Palabras</th></tr></thead>
    <tbody>${filas}</tbody></table>`, meta.etiqueta);
}

async function vistaPagina(id, p) {
  const [c, n] = await Promise.all([corpus(), numero(id)]);
  const meta = c.numeros.find((x) => x.id === id) || { etiqueta: id };
  const i = n.paginas.findIndex((x) => x.p === p);
  if (i < 0) return pintar('<p class="vacio">Página no encontrada.</p>');
  const pag = n.paginas[i];
  const num = parseInt(p.slice(1), 10);
  const ant = i > 0 ? `<a href="#/pagina/${enc(id)}/${n.paginas[i - 1].p}">← Página anterior</a>` : "<span></span>";
  const sig = i < n.paginas.length - 1 ? `<a href="#/pagina/${enc(id)}/${n.paginas[i + 1].p}">Página siguiente →</a>` : "<span></span>";
  const unidades = n.unidades.filter((u) => pag.unidades.includes(u.id));
  const lista = unidades.map((u) => `<li><a href="#/unidad/${enc(u.id)}">${esc(u.titulo)}</a>
    <div>${etiquetasDe(u.entidades)}</div></li>`).join("");
  pintar(`
    <p><a href="#/numero/${enc(id)}">← ${esc(meta.etiqueta)}</a></p>
    <h1>Página ${num} <small class="sub">de ${n.paginas.length}</small></h1>
    <div class="pasos">${ant}${sig}</div>
    <div class="visor">
      <a href="img/${enc(id)}/${p}.webp"><img src="img/${enc(id)}/${p}.webp"
        alt="Facsímil de la página ${num} de Estampa, ${esc(meta.etiqueta)}"></a>
      <div><div class="transcripcion" aria-label="Transcripción">${pag.sin_texto
        ? '<span class="vacio">Esta página no tiene texto para transcribir.</span>' : esc(pag.texto)}</div>
        <p class="leyenda">Transcripción automática (Claude Vision), sin revisión humana: puede contener errores.</p></div>
    </div>
    <h2>Unidades editoriales en esta página</h2>
    ${lista ? `<ul class="lista-unidades">${lista}</ul>` : '<p class="vacio">Ninguna unidad empieza o continúa aquí.</p>'}`,
    `${meta.etiqueta}, página ${num}`);
}

async function vistaUnidad(uid) {
  const id = numeroDeUnidad(uid);
  const [c, n] = await Promise.all([corpus(), numero(id)]);
  const u = n.unidades.find((x) => x.id === uid);
  if (!u) return pintar('<p class="vacio">Unidad no encontrada.</p>');
  const meta = c.numeros.find((x) => x.id === id) || { etiqueta: id };
  const pags = u.paginas.map((p) => `<a href="#/pagina/${enc(id)}/${p}">página ${parseInt(p.slice(1), 10)}</a>`).join(", ");
  pintar(`
    <p><a href="#/numero/${enc(id)}">← ${esc(meta.etiqueta)}</a></p>
    <h1>${esc(u.titulo)}</h1>
    <p class="sub">${esc(u.seccion)} · ${fmt(u.palabras)} palabras · ${pags}</p>
    <h2>Entidades nombradas</h2><p>${etiquetasDe(u.entidades)}</p>
    <p class="leyenda">Identificador estable: <code>${esc(u.id)}</code> (el mismo que en el TEI).</p>`, u.titulo);
}

async function vistaEntidades(params) {
  const [lista, c] = await Promise.all([entidades(), corpus()]);
  const q = (params.get("q") || "").trim();
  const cat = params.get("c") || "";
  const opciones = Object.entries(c.cifras.por_categoria).map(([k, v]) =>
    `<option value="${esc(k)}" ${k === cat ? "selected" : ""}>${esc(CAT[k] || k)} (${fmt(v)})</option>`).join("");
  pintar(`
    <h1>Entidades nombradas</h1>
    <p class="sub">${fmt(lista.length)} entidades detectadas automáticamente (${fmt(c.cifras.entidades_unicas)} formas escritas:
      «Bogotá» y «BOGOTA» cuentan como una), ordenadas por número de unidades en que aparecen.</p>
    <form class="filtros" role="search" onsubmit="return false">
      <label>Buscar <input id="q" type="search" value="${esc(q)}" placeholder="p. ej. Arciniegas"></label>
      <label>Categoría <select id="c"><option value="">Todas</option>${opciones}</select></label>
    </form>
    <div id="resultados"></div>`, "Entidades");
  const pintarLista = () => {
    const qq = document.getElementById("q").value.trim().toLowerCase();
    const cc = document.getElementById("c").value;
    const norm = (s) => s.toLowerCase().normalize("NFD").replace(/\p{Diacritic}/gu, "");
    const nq = norm(qq);
    const filtradas = lista.filter((e) => (!cc || e.c === cc) &&
      (!nq || norm(e.t).includes(nq) || (e.f || []).some((f) => norm(f).includes(nq))));
    const filas = filtradas.slice(0, 300).map((e) => `<tr><td>${etiqueta(e.c, e.t)}</td>
      <td>${esc(CAT[e.c] || e.c)}</td><td>${fmt(e.u.length)}</td></tr>`).join("");
    document.getElementById("resultados").innerHTML = filtradas.length
      ? `<p class="leyenda">${fmt(filtradas.length)} resultados${filtradas.length > 300 ? " (se muestran los 300 más frecuentes)" : ""}.</p>
         <table><thead><tr><th>Entidad</th><th>Categoría</th><th>Unidades</th></tr></thead><tbody>${filas}</tbody></table>`
      : '<p class="vacio">Sin resultados.</p>';
    history.replaceState(null, "", `#/entidades?q=${enc(qq)}&c=${enc(cc)}`);
  };
  document.getElementById("q").addEventListener("input", pintarLista);
  document.getElementById("c").addEventListener("change", pintarLista);
  pintarLista();
}

async function vistaEntidad(cat, texto) {
  const [lista, c] = await Promise.all([entidades(), corpus()]);
  const e = lista.find((x) => x.c === cat && (x.t === texto || (x.f || []).includes(texto)));
  if (!e) return pintar('<p class="vacio">Entidad no encontrada.</p>');
  const porNumero = {};
  e.u.forEach((uid) => (porNumero[numeroDeUnidad(uid)] ||= []).push(uid));
  const bloques = await Promise.all(Object.entries(porNumero).map(async ([id, uids]) => {
    const n = await numero(id);
    const meta = c.numeros.find((x) => x.id === id) || { etiqueta: id };
    const items = n.unidades.filter((u) => uids.includes(u.id)).map((u) =>
      `<li><a href="#/unidad/${enc(u.id)}">${esc(u.titulo)}</a> <small>(pág. ${u.paginas.map((p) => parseInt(p.slice(1), 10)).join(", ")})</small></li>`).join("");
    return `<h2>${esc(meta.etiqueta)}</h2><ul class="lista-unidades">${items}</ul>`;
  }));
  pintar(`
    <p><a href="#/entidades">← Índice de entidades</a></p>
    <h1>${esc(e.t)}</h1>
    <p class="sub">${esc(CAT[e.c] || e.c)} · aparece en ${fmt(e.u.length)} unidades editoriales</p>
    ${e.f ? `<p class="leyenda">También escrita: ${e.f.map(esc).join(" · ")}</p>` : ""}
    ${bloques.join("")}`, e.t);
}

async function vistaGrafo() {
  const g = await json("datos/grafo.json");
  pintar(`
    <h1>Grafo de co-ocurrencias</h1>
    <p class="sub">Las ${fmt(g.nodos.length)} personas, lugares y organizaciones más frecuentes. Dos entidades se unen
      si aparecen juntas en al menos dos unidades editoriales; el grosor indica en cuántas. Pulse un nodo para ver dónde aparece.</p>
    <div id="red" role="img" aria-label="Grafo de co-ocurrencias de entidades"></div>
    <p class="leyenda"><span class="etiqueta personas">Persona</span> <span class="etiqueta lugares">Lugar</span>
      <span class="etiqueta organizaciones">Organización</span></p>`, "Grafo");
  if (!window.vis) {
    document.getElementById("red").innerHTML = '<p class="vacio">No se pudo cargar la biblioteca del grafo.</p>';
    return;
  }
  const css = getComputedStyle(document.documentElement);
  const color = (c) => css.getPropertyValue(`--${c}`).trim() || "#888";
  const nodos = new vis.DataSet(g.nodos.map((n) => ({ id: n.id, label: n.t, value: n.n,
    color: color(n.c), font: { color: css.getPropertyValue("--tinta").trim() },
    title: `${n.t} · ${n.n} unidades`, _c: n.c })));
  const aristas = new vis.DataSet(g.aristas.map((a) => ({ from: a.a, to: a.b, value: a.w,
    color: { color: css.getPropertyValue("--linea").trim() } })));
  const red = new vis.Network(document.getElementById("red"), { nodes: nodos, edges: aristas }, {
    // Las etiquetas de los nodos pequeños se ocultan hasta acercarse: sin esto
    // el centro del grafo es ilegible.
    nodes: { shape: "dot", scaling: { min: 6, max: 34,
      label: { enabled: true, min: 10, max: 22, drawThreshold: 11 } } },
    edges: { scaling: { min: 1, max: 8 }, smooth: false },
    physics: { stabilization: { iterations: 200 }, barnesHut: { gravitationalConstant: -9000 } },
    interaction: { hover: true, tooltipDelay: 120 },
  });
  red.once("stabilizationIterationsDone", () => red.setOptions({ physics: false }));
  red.on("click", (ev) => {
    if (!ev.nodes.length) return;
    const n = nodos.get(ev.nodes[0]);
    location.hash = `#/entidad/${enc(n._c)}/${enc(n.label)}`;
  });
}

async function vistaDescargas() {
  const c = await corpus();
  pintar(`
    <h1>Descargas</h1>
    <p class="sub">El corpus completo, generado con los mismos exportadores de la aplicación.</p>
    <ul class="descargas">
      <li><a href="datos/descargas/corpus_tei.xml" download>corpus_tei.xml</a> — XML-TEI P5:
        las ${fmt(c.cifras.unidades)} unidades editoriales con su texto y sus entidades en <code>standOff</code>.
        Con su <a href="datos/descargas/corpus_tei.xml.proveniencia.json">manifiesto de proveniencia</a>.</li>
      <li><a href="datos/descargas/entidades.csv" download>entidades.csv</a> — las ${fmt(c.cifras.entidades_unicas)}
        entidades con su categoría y las unidades donde aparecen.</li>
      <li><a href="datos/descargas/corpus.bib" download>corpus.bib</a> — referencias BibTeX de las unidades.</li>
    </ul>
    <p>Las imágenes y los textos de <em>Estampa</em> se publican con autorización de la Biblioteca Nacional
      de Colombia; la licencia del software no se aplica a ellos. Antes de reutilizarlos, consulte las
      <a href="https://github.com/fabiangulla-pixel/Bashkar-Station/blob/main/DERECHOS.md">condiciones</a>.</p>
    <h2>Procesar su propio corpus</h2>
    <p>Bashkar Station es software libre y funciona en su equipo, sin conexión y sin GPU.
      Instrucciones de instalación en el
      <a href="https://github.com/fabiangulla-pixel/Bashkar-Station#instalación">repositorio</a>.</p>`, "Descargas");
}

async function vistaAcerca() {
  const c = await corpus();
  const k = c.cifras;
  const creditos = (c.creditos || []).map((x) => `<li><b>${esc(x.rol)}:</b> ${esc(x.nombre)}</li>`).join("");
  pintar(`
    <h1>Acerca de esta demo</h1>
    <p>Esta es una demostración de solo lectura de <a href="https://github.com/fabiangulla-pixel/Bashkar-Station">Bashkar Station</a>,
      una aplicación de escritorio para el análisis computacional de publicaciones periódicas históricas.
      Todo lo que se ve aquí lo produjo la aplicación, sin edición manual.</p>
    <h2>Cómo se hizo</h2>
    <ul>
      <li><b>Transcripción:</b> ${esc((k.metodo_ocr || []).join(", ") || "desconocido")} sobre las ${fmt(k.paginas)} páginas.
        No se ha revisado a mano: puede contener errores.</li>
      <li><b>Unidades editoriales:</b> ${fmt(k.unidades)}, segmentadas automáticamente.</li>
      <li><b>Entidades nombradas:</b> ${esc(k.motor_ner || "desconocido")}. ${fmt(k.entidades_unicas)} entidades,
        ${fmt(k.menciones)} menciones. Las categorías de obras y eventos no las produce este modelo.</li>
      <li><b>Grafo:</b> ${fmt(k.entidades_canonicas)} entidades canónicas y ${fmt(k.relaciones)} relaciones en la base del proyecto.</li>
    </ul>
    <h2>Créditos</h2>
    <ul>${creditos}</ul>
    <p>${esc(c.disponibilidad)}</p>`, "Acerca de");
}

// ── Enrutador ───────────────────────────────────────────────────────────────

async function enrutar() {
  const [ruta, consulta] = location.hash.replace(/^#/, "").split("?");
  const partes = (ruta || "/").split("/").filter(Boolean).map(decodeURIComponent);
  const params = new URLSearchParams(consulta || "");
  try {
    if (!partes.length) await vistaInicio();
    else if (partes[0] === "numero") await vistaNumero(partes[1]);
    else if (partes[0] === "pagina") await vistaPagina(partes[1], partes[2]);
    else if (partes[0] === "unidad") await vistaUnidad(partes[1]);
    else if (partes[0] === "entidades") await vistaEntidades(params);
    else if (partes[0] === "entidad") await vistaEntidad(partes[1], partes.slice(2).join("/"));
    else if (partes[0] === "grafo") await vistaGrafo();
    else if (partes[0] === "descargas") await vistaDescargas();
    else if (partes[0] === "acerca") await vistaAcerca();
    else pintar('<p class="vacio">Página no encontrada. <a href="#/">Volver al inicio</a>.</p>');
  } catch (err) {
    pintar(`<p class="vacio">No se pudieron cargar los datos (${esc(err.message)}).</p>`);
  }
}

window.addEventListener("hashchange", enrutar);
enrutar();
