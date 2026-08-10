"""
core/recursos.py — Reparto de CPU entre los modelos y la interfaz.

El problema que resuelve: en un portátil sin GPU, PyTorch y las bibliotecas de
álgebra (OpenMP, MKL, OpenBLAS) toman por defecto **todos los hilos lógicos**
que ve el sistema. Bashkar además lanza sus lotes con `ThreadPoolExecutor`, y
cada worker abre su propio grupo de hilos de BLAS: con 4 workers en una máquina
de 12 hilos se piden 48. Eso es sobresuscripción — los hilos se pelean el mismo
núcleo, el planificador pasa más tiempo cambiando de contexto que calculando, y
el hilo de Tkinter no alcanza a repintar. Para la investigadora la app "se
congeló", aunque por dentro esté trabajando a toda máquina.

La cura es reservar núcleos en lugar de repartirlos todos. Dejar uno o dos
libres cuesta poco en tiempo de cómputo —los hilos lógicos de más aportan poco
en operaciones limitadas por memoria, que es lo que son las matrices grandes— y
devuelve una interfaz que responde.

Reglas de la casa:
  · SOLO biblioteca estándar en el nivel de módulo. Esto se llama en el arranque,
    antes de que exista torch; importarlo aquí lo cargaría siempre, incluso en
    sesiones que no tocan un solo modelo (y son la mayoría).
  · Las variables de entorno se fijan **antes** del primer import de torch/numpy:
    OpenMP lee su configuración al inicializarse y luego ya no la relee.
  · Nunca lanza. Un fallo repartiendo CPU no puede impedir abrir la aplicación.
"""

from __future__ import annotations

import os

__all__ = [
    "hilos_recomendados",
    "aplicar_limites_cpu",
    "limitar_hilos_torch",
    "VARIABLE_OVERRIDE",
]

# Permite fijar el número a mano cuando la heurística no encaja: una máquina de
# 32 núcleos dedicada a un lote nocturno quiere lo contrario que un portátil con
# el navegador abierto.
VARIABLE_OVERRIDE = "BASHKAR_HILOS"

# Núcleos que se dejan libres para la interfaz y el sistema operativo.
NUCLEOS_RESERVADOS = 1


def hilos_recomendados() -> int:
    """Cuántos hilos debería usar el cálculo numérico en esta máquina.

    Parte de los hilos *lógicos* y los divide entre dos para estimar los núcleos
    físicos: en cargas de álgebra densa el segundo hilo de cada núcleo compite
    por la misma unidad de coma flotante y suele empeorar el rendimiento en vez
    de mejorarlo. De ahí se reserva uno para la interfaz.

    Devuelve siempre 1 como mínimo.
    """
    override = os.environ.get(VARIABLE_OVERRIDE, "").strip()
    if override:
        try:
            valor = int(override)
            if valor > 0:
                return valor
        except ValueError:
            pass          # valor inservible: se sigue con la heurística

    logicos = os.cpu_count() or 1
    fisicos_estimados = max(1, logicos // 2)
    return max(1, fisicos_estimados - NUCLEOS_RESERVADOS)


def aplicar_limites_cpu(hilos: int | None = None) -> int:
    """Fija las variables de entorno de OpenMP/MKL/BLAS. Llamar en el arranque.

    Debe ejecutarse **antes** del primer `import torch` o `import numpy`, porque
    esas bibliotecas leen la configuración al inicializar su pool y después la
    ignoran. Por eso vive en un módulo sin dependencias: se puede llamar en la
    primera línea de `app.py`.

    Usa `setdefault`: si la investigadora ya fijó OMP_NUM_THREADS en su sistema,
    manda su decisión.

    Devuelve el número de hilos aplicado.
    """
    n = hilos if (hilos and hilos > 0) else hilos_recomendados()
    for variable in (
        "OMP_NUM_THREADS",
        "MKL_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
    ):
        os.environ.setdefault(variable, str(n))
    return n


def limitar_hilos_torch(hilos: int | None = None) -> int | None:
    """Aplica el límite dentro de PyTorch, si ya está cargado.

    Complementa a `aplicar_limites_cpu`: las variables de entorno cubren el
    arranque, y esto cubre el caso de que torch se importe por un camino que no
    pasó por ahí. Es idempotente y barata.

    Devuelve los hilos aplicados, o None si torch no está disponible (que es lo
    normal en el .exe compilado, donde PyTorch se excluye a propósito).
    """
    try:
        import torch
    except Exception:
        return None

    n = hilos if (hilos and hilos > 0) else hilos_recomendados()
    try:
        torch.set_num_threads(n)
        # El pool interoperador coordina operaciones paralelas entre sí; con un
        # solo modelo a la vez no aporta nada y compite con el de dentro.
        torch.set_num_interop_threads(1)
    except Exception:
        # set_num_interop_threads lanza si ya se lanzó trabajo paralelo. No es
        # motivo para tumbar un OCR que por lo demás iba a funcionar.
        pass
    return n
