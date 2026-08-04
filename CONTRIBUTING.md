# Cómo contribuir a Bashkar Station

Gracias por el interés. Este proyecto nació de una investigación concreta —el
análisis de la revista *Estampa* (Colombia, 1930-1940) en el Instituto Caro y
Cuervo— y se publica con la esperanza de que sirva a otras investigaciones sobre
prensa histórica en español. Las contribuciones son bienvenidas, desde una
errata en la documentación hasta un motor de análisis nuevo.

## Antes de escribir código

**Abre un issue primero** si vas a cambiar algo grande. No por burocracia: este
programa toma decisiones metodológicas discutibles (qué se considera un
arcaísmo, cuándo una normalización deja de ser conservadora, qué umbral separa
una zona de texto de una fotografía) y conviene discutirlas antes de
implementarlas. Muchas están documentadas en `CHANGELOG.md`, que es más una
bitácora de investigación que una lista de cambios.

Para erratas, fallos evidentes o mejoras pequeñas, ve directo al Pull Request.

## Poner en marcha el entorno

```bash
git clone https://github.com/fabiangulla-pixel/Bashkar-Station.git
cd Bashkar-Station
python instalar.py          # dependencias + Tesseract + modelos de spaCy
python scripts/install_hooks.py   # instala el hook de pre-commit
python app.py
```

Se desarrolla sobre **Python 3.12+** (la máquina de referencia usa 3.14).
Ojo con Python 3.14: `gensim` no compila ahí, por eso `core/word_vectors.py`
tiene un segundo backend en PyTorch. No lo quites.

## La regla que no se negocia: `check.bat` en verde

```
check.bat
```

Corre tres cosas, en orden: `py_compile` de `app.py`, `ruff check .` y la suite
completa de `pytest` (**1076 tests**). El hook de pre-commit lo ejecuta solo, así
que un commit no entra si algo está en rojo. **No uses `--no-verify`.** Si el
hook te estorba, es que hay un problema real que arreglar.

La suite tarda unos 8 minutos. Es a propósito: incluye tests de GUI headless que
instancian la aplicación de verdad.

## Convenciones del código

- **Ruff** con `E, F, I, B, C4, UP, W`, línea de 100 columnas. La configuración
  está en `pyproject.toml`. Hay `per-file-ignores` para módulos heredados: son
  deuda consciente, no permiso para escribir código nuevo con ese estilo.
- **`core/` no conoce la interfaz.** Los módulos de `core/` son funciones puras
  o clases sin `tkinter`. Es lo que permite que el mismo motor alimente la app
  de escritorio y `servidor_web.py`. Si tu módulo nuevo importa `tkinter`, algo
  está mal.
- **Nada pesado en el hilo principal.** Tkinter se congela. Todo procesamiento
  va en un `threading.Thread(daemon=True)`.
- **Y al revés: nada de Tk desde un hilo.** Tcl no es thread-safe. Las variables
  de la interfaz se leen en el lanzador (hilo principal) y se pasan ya
  congeladas al worker; lo que vuelve a la interfaz pasa por `self.after(0, …)`.
  Esto lo vigila `tests/test_hilos_tk.py` analizando el AST: si añades un worker
  que toque un widget directamente, el test falla y te dice dónde.
- **Comentarios en español**, como el resto del código. Explica el *porqué*, no
  el *qué*.
- **Mensajes de commit** en imperativo y en español, describiendo el problema
  que resuelven. Mira `git log` para el tono.

## Tests

Todo lo que aporte comportamiento nuevo necesita test. Detalles que importan
aquí:

- Nada de red en los tests. Wikidata, las APIs de LLM y los servidores locales
  se mockean. Los pocos tests que sí tocan red están marcados para saltarse.
- Nada de claves de API reales, obviamente. Usa `sk-ant-xxx` y similares.
- Si arreglas un fallo, **añade primero el test que lo reproduce**. Y si escribes
  un script de análisis (un linter propio, un auditor), añade también una
  **prueba negativa** que confirme que detecta código malo de verdad: un
  detector que nunca falla no está detectando nada.

## Corpus y datos

**No subas material del corpus.** El `.gitignore` excluye `*.db`, `*.sqlite`,
`modelos/` y `*.traineddata`. Los PDFs y transcripciones de prensa histórica
suelen tener condiciones de uso de la biblioteca que los digitalizó —en el caso
de *Estampa*, la Biblioteca Nacional de Colombia—. Este repositorio publica el
software, no las fuentes.

Si necesitas datos para un test, genera un ejemplo mínimo sintético.

## Pull Requests

1. Haz un fork y una rama con nombre descriptivo.
2. `check.bat` en verde.
3. Describe **qué problema resuelve**, no solo qué cambiaste. Si tocaste una
   heurística, di con qué material real la validaste.
4. Un PR, un asunto.

Reviso los PR yo mismo; ten paciencia, esto convive con otras obligaciones
académicas.

## Licencia

Al contribuir aceptas que tu aporte se publique bajo **Apache 2.0**, igual que
el resto del proyecto.
