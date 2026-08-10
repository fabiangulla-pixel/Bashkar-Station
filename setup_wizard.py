"""
setup_wizard.py — Asistente de instalación de Bashkar Station.

Lo que existía antes era `instalar.py`, un script de consola. Para quien no
programa, una terminal que escupe texto y puede fallar a mitad no es un
instalador: es un obstáculo. Esto es la ventana que se espera de un programa
—qué falta, para qué sirve cada cosa, un botón que lo resuelve— y funciona
igual en Windows y en macOS.

Se usa Tkinter y no Qt a propósito: viene con Python en ambos sistemas, así que
el asistente puede arrancar ANTES de que se haya instalado ninguna dependencia,
que es justo cuando hace falta.

Toda la lógica de "qué falta y cómo se arregla" vive en `core/requisitos.py`.
Aquí solo está la interfaz. Esa separación es la que permite que la consola y
la ventana no se contradigan.

Ejecutar:  python setup_wizard.py
"""

from __future__ import annotations

import queue
import sys
import threading
import tkinter as tk
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core import requisitos  # noqa: E402

# Paleta tomada de app.py para que el asistente y la aplicación se vean como
# una sola cosa. Los widgets nativos sin estilizar quedan descartados.
FONDO = "#0A1628"
FONDO_TARJETA = "#12203A"
FONDO_LOG = "#0D1117"
TEXTO = "#E6EDF3"
TEXTO_TENUE = "#7FB3D3"
AZUL = "#0078D4"
AZUL_VIVO = "#4FC1FF"
VERDE = "#70AD47"
AMBAR = "#D7A03C"
ROJO = "#D9534F"
GRIS = "#3A4A63"

FUENTE = "Segoe UI" if sys.platform == "win32" else "Helvetica"
MONO = "Consolas" if sys.platform == "win32" else "Menlo"


class BotonPlano(tk.Canvas):
    """Botón dibujado a mano.

    Un `tk.Button` nativo se ve como Windows 95 en Windows y desentona con el
    resto de la aplicación en macOS. Dibujarlo en un Canvas cuesta poco y da el
    mismo aspecto en los dos sistemas, que es lo que se quiere de un asistente
    que la misma persona puede abrir en su portátil y en el del trabajo.
    """

    def __init__(self, master, texto, comando, color=AZUL, ancho=210, alto=38, **kw):
        super().__init__(master, width=ancho, height=alto, bg=kw.pop("bg", FONDO),
                         highlightthickness=0, cursor="hand2", **kw)
        self._comando = comando
        self._color = color
        self._habilitado = True
        self._ancho, self._alto = ancho, alto
        self._cuerpo = self.create_rectangle(0, 0, ancho, alto, fill=color, outline="")
        self._texto = self.create_text(ancho // 2, alto // 2, text=texto,
                                       fill="#FFFFFF", font=(FUENTE, 10, "bold"))
        self.bind("<Button-1>", self._al_pulsar)
        self.bind("<Enter>", lambda _e: self._pintar(aclarar=True))
        self.bind("<Leave>", lambda _e: self._pintar())

    def _pintar(self, aclarar=False):
        if not self._habilitado:
            self.itemconfig(self._cuerpo, fill=GRIS)
            self.itemconfig(self._texto, fill="#8899AA")
            return
        self.itemconfig(self._cuerpo, fill=AZUL_VIVO if aclarar else self._color)
        self.itemconfig(self._texto, fill="#FFFFFF" if not aclarar else "#0A1628")

    def _al_pulsar(self, _evento):
        if self._habilitado and self._comando:
            self._comando()

    def habilitar(self, valor: bool):
        self._habilitado = valor
        self.configure(cursor="hand2" if valor else "arrow")
        self._pintar()

    def texto(self, valor: str):
        self.itemconfig(self._texto, text=valor)


class BarraProgreso(tk.Canvas):
    """Barra de progreso en Canvas, por la misma razón que el botón."""

    def __init__(self, master, ancho=560, alto=8):
        super().__init__(master, width=ancho, height=alto, bg=FONDO,
                         highlightthickness=0)
        self._ancho = ancho
        self.create_rectangle(0, 0, ancho, alto, fill="#1B2A44", outline="")
        self._relleno = self.create_rectangle(0, 0, 0, alto, fill=AZUL, outline="")

    def fijar(self, fraccion: float):
        ancho = max(0, min(1.0, fraccion)) * self._ancho
        self.coords(self._relleno, 0, 0, ancho, self.winfo_reqheight())


class AsistenteInstalacion(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Bashkar Station — Instalación")
        self.configure(bg=FONDO)
        self.geometry("820x680")
        self.minsize(760, 600)

        # El worker nunca toca Tk: deja mensajes aquí y el hilo de la interfaz
        # los recoge con after(). Saltarse esto cuelga Tkinter de formas que
        # solo aparecen en el equipo del usuario.
        self._cola: queue.Queue = queue.Queue()
        self._diag: requisitos.Diagnostico | None = None
        self._filas: dict[str, dict] = {}
        self._trabajando = False
        # Se guarda el id del `after` para poder cancelarlo al cerrar. Sin esto
        # queda una llamada pendiente que se ejecuta sobre widgets ya
        # destruidos, y Tk no lanza una excepción: se cae el proceso entero.
        self._tarea_cola: str | None = None

        self._construir()
        self._tarea_cola = self.after(80, self._bombear_cola)
        self._revisar()

    # ── Construcción de la interfaz ──────────────────────────────────────────

    def _construir(self):
        cab = tk.Frame(self, bg=FONDO)
        cab.pack(fill="x", padx=28, pady=(22, 6))
        tk.Label(cab, text="Instalación de Bashkar Station", bg=FONDO, fg=TEXTO,
                 font=(FUENTE, 18, "bold")).pack(anchor="w")
        self.lbl_sub = tk.Label(cab, text="Revisando el equipo…", bg=FONDO,
                                fg=TEXTO_TENUE, font=(FUENTE, 10))
        self.lbl_sub.pack(anchor="w", pady=(2, 0))

        self.barra = BarraProgreso(self, ancho=764)
        self.barra.pack(padx=28, pady=(14, 4), anchor="w")

        # Lista de requisitos, con scroll: son más de veinte.
        contenedor = tk.Frame(self, bg=FONDO)
        contenedor.pack(fill="both", expand=True, padx=28, pady=(8, 0))
        lienzo = tk.Canvas(contenedor, bg=FONDO, highlightthickness=0, height=280)
        scroll = tk.Scrollbar(contenedor, orient="vertical", command=lienzo.yview)
        self.lista = tk.Frame(lienzo, bg=FONDO)
        self.lista.bind("<Configure>",
                        lambda _e: lienzo.configure(scrollregion=lienzo.bbox("all")))
        lienzo.create_window((0, 0), window=self.lista, anchor="nw", width=740)
        lienzo.configure(yscrollcommand=scroll.set)
        lienzo.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        lienzo.bind_all("<MouseWheel>",
                        lambda e: lienzo.yview_scroll(int(-e.delta / 120), "units"))

        botones = tk.Frame(self, bg=FONDO)
        botones.pack(fill="x", padx=28, pady=(12, 6))
        self.btn_instalar = BotonPlano(botones, "Instalar lo que falta",
                                       self._instalar_todo, color=VERDE, ancho=200)
        self.btn_instalar.pack(side="left")
        self.btn_copiar = BotonPlano(botones, "Copiar comandos", self._copiar,
                                     color=AZUL, ancho=170)
        self.btn_copiar.pack(side="left", padx=(10, 0))
        self.btn_revisar = BotonPlano(botones, "Volver a revisar", self._revisar,
                                      color=AZUL, ancho=160)
        self.btn_revisar.pack(side="left", padx=(10, 0))

        tk.Label(self, text="Registro", bg=FONDO, fg=TEXTO_TENUE,
                 font=(FUENTE, 9, "bold")).pack(anchor="w", padx=28, pady=(8, 2))
        self.log = tk.Text(self, height=9, bg=FONDO_LOG, fg=TEXTO_TENUE,
                           font=(MONO, 9), relief="flat", wrap="word",
                           insertbackground=TEXTO, padx=10, pady=8)
        self.log.pack(fill="both", expand=False, padx=28, pady=(0, 20))
        self.log.configure(state="disabled")

    def _fila_requisito(self, req: requisitos.Requisito) -> dict:
        marco = tk.Frame(self.lista, bg=FONDO_TARJETA)
        marco.pack(fill="x", pady=2)

        punto = tk.Label(marco, text="●", bg=FONDO_TARJETA, font=(FUENTE, 12),
                         fg=VERDE if req.instalado else (AMBAR if not req.obligatorio else ROJO))
        punto.pack(side="left", padx=(12, 8), pady=8)

        centro = tk.Frame(marco, bg=FONDO_TARJETA)
        centro.pack(side="left", fill="x", expand=True, pady=6)
        tk.Label(centro, text=req.nombre, bg=FONDO_TARJETA, fg=TEXTO,
                 font=(FUENTE, 10, "bold"), anchor="w").pack(anchor="w")
        detalle = req.detalle or req.para_que
        tk.Label(centro, text=detalle, bg=FONDO_TARJETA, fg=TEXTO_TENUE,
                 font=(FUENTE, 8), anchor="w", wraplength=520,
                 justify="left").pack(anchor="w")

        etiqueta = {"listo": "listo", "falta": "falta", "opcional": "opcional"}[req.estado]
        tk.Label(marco, text=etiqueta, bg=FONDO_TARJETA,
                 fg=VERDE if req.instalado else (AMBAR if not req.obligatorio else ROJO),
                 font=(FUENTE, 9, "bold")).pack(side="right", padx=14)
        return {"marco": marco, "punto": punto}

    # ── Estado y mensajes ────────────────────────────────────────────────────

    def _escribir(self, texto: str):
        self.log.configure(state="normal")
        self.log.insert("end", texto + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _bombear_cola(self):
        """Único punto donde los mensajes del worker llegan a los widgets."""
        # La ventana pudo cerrarse entre dos vueltas del temporizador.
        # `winfo_exists` sobre una raíz ya destruida no devuelve False: lanza
        # TclError, porque no queda intérprete Tcl al que preguntar.
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
        try:
            while True:
                tipo, dato = self._cola.get_nowait()
                if tipo == "log":
                    self._escribir(dato)
                elif tipo == "progreso":
                    self.barra.fijar(dato)
                elif tipo == "fin":
                    self._trabajando = False
                    self._revisar()
        except queue.Empty:
            pass
        self._tarea_cola = self.after(80, self._bombear_cola)

    def destroy(self):
        """Cancela el temporizador antes de desmontar los widgets.

        Si se destruye la ventana con un `after` pendiente, Tk ejecuta el
        callback contra widgets que ya no existen. No lanza una excepción que
        se pueda capturar: aborta el proceso.
        """
        if self._tarea_cola is not None:
            try:
                self.after_cancel(self._tarea_cola)
            except Exception:
                pass
            self._tarea_cola = None
        super().destroy()

    def _revisar(self):
        if self._trabajando:
            return
        for hijo in self.lista.winfo_children():
            hijo.destroy()
        self._filas.clear()

        diag = requisitos.diagnosticar()
        self._diag = diag
        for req in diag.requisitos:
            self._filas[req.clave] = self._fila_requisito(req)

        total = len(diag.requisitos)
        listos = sum(1 for r in diag.requisitos if r.instalado)
        self.barra.fijar(listos / total if total else 1.0)

        if diag.listo:
            self.lbl_sub.configure(
                text=f"{diag.sistema} · Todo listo. Ya puedes usar Bashkar Station.",
                fg=VERDE)
            self.btn_instalar.habilitar(False)
        else:
            n = len(diag.faltantes)
            # Concordancia de verbo y sustantivo: "Falta 1 componente" /
            # "Faltan 3 componentes". Lo va a leer un editor.
            frase = (f"Falta {n} componente" if n == 1
                     else f"Faltan {n} componentes")
            self.lbl_sub.configure(text=f"{diag.sistema} · {frase} de {total}.",
                                   fg=AMBAR)
            self.btn_instalar.habilitar(not diag.congelado)

        if diag.congelado:
            self._escribir(
                "Estás usando la versión empaquetada (.exe). Desde aquí no se "
                "pueden instalar paquetes de Python: usa «Copiar comandos» y "
                "pégalos en una terminal.")

    # ── Acciones ─────────────────────────────────────────────────────────────

    def _copiar(self):
        if not self._diag:
            return
        comandos = requisitos.comando_terminal_completo(self._diag)
        if not comandos:
            self._escribir("No falta nada que copiar.")
            return
        self.clipboard_clear()
        self.clipboard_append(comandos)
        self._escribir("Comandos copiados al portapapeles:")
        for linea in comandos.splitlines():
            self._escribir(f"    {linea}")

    def _instalar_todo(self):
        if self._trabajando or not self._diag:
            return
        pendientes = [r for r in self._diag.faltantes if r.puede_instalarse]
        manuales = [r for r in self._diag.faltantes if not r.puede_instalarse]

        if manuales:
            self._escribir("Estos hay que instalarlos a mano (son programas del "
                           "sistema, no paquetes de Python):")
            for r in manuales:
                self._escribir(f"    {r.nombre}:  {r.instruccion_manual}")

        if not pendientes:
            self._escribir("No hay nada que este asistente pueda instalar solo.")
            return

        self._trabajando = True
        self.btn_instalar.habilitar(False)
        self.btn_revisar.habilitar(False)
        hilo = threading.Thread(target=self._worker_instalar, args=(pendientes,),
                                daemon=True)
        hilo.start()

    def _worker_instalar(self, pendientes):
        """Corre FUERA del hilo de la interfaz. No toca ni un widget."""
        registrar = lambda m: self._cola.put(("log", m))  # noqa: E731
        total = len(pendientes)
        instalados = 0
        for i, req in enumerate(pendientes, start=1):
            self._cola.put(("progreso", i / total))
            if requisitos.instalar_requisito(req, registrar):
                instalados += 1
        registrar(f"Terminado: {instalados} de {total} quedaron instalados.")
        if instalados < total:
            registrar("Los que fallaron suelen resolverse ejecutando el comando "
                      "en una terminal, donde se ve el error completo.")
        self._cola.put(("fin", None))


def main():
    app = AsistenteInstalacion()
    app.mainloop()


if __name__ == "__main__":
    main()
