# Política de seguridad

## Cómo reportar una vulnerabilidad

**No abras un issue público.** Escribe a **fabian.gulla@gmail.com** con el
asunto `[SEGURIDAD] Bashkar Station`, o usa el aviso privado de GitHub en
*Security → Report a vulnerability*.

Incluye, si puedes: qué versión usas (aparece en la barra inferior de la
aplicación), qué hiciste para provocarlo, qué esperabas y qué pasó. Respondo en
un plazo razonable —esto es un proyecto de investigación, no un producto con
turnos de guardia— y te aviso cuando esté corregido.

## Versiones que reciben correcciones

Solo la última versión publicada. Hoy: **v11.8**.

## Qué es relevante en este proyecto

Bashkar Station es una aplicación **de escritorio y offline** que procesa
archivos locales. Su superficie de ataque es pequeña, pero hay tres zonas donde
un fallo sí importa:

**1. Claves de API.** La aplicación puede usar servicios de IA (Anthropic,
OpenAI, Google, o modelos locales vía Ollama y LM Studio). Las claves se guardan
en el archivo `.bashkar` del proyecto, **en texto plano y en el disco del
usuario**. Esto es una limitación conocida, no un descuido silencioso: el
archivo nunca sale de tu máquina y nunca entra al repositorio (`.gitignore`
excluye los proyectos), pero cualquiera con acceso a tu carpeta de usuario puede
leerlo. Si compartes un `.bashkar` con un colega, **borra las claves antes**.

En el **modo público** del servidor web (`servidor_web.py` con
`BASHKAR_PASSWORD`) las claves nunca se escriben a disco: se vacían antes de
guardar el proyecto y se restauran solo en memoria.

**2. El servidor web.** `servidor_web.py` está pensado para uso local. Si lo
expones a internet, hazlo **siempre** con `BASHKAR_PASSWORD` y detrás de HTTPS.
En modo público cada visitante tiene su sesión aislada (cookie `sid` httpOnly,
`Secure` cuando hay `X-Forwarded-Proto: https`), y las rutas `/api/pagina` y
`/api/descargar` bloquean *path traversal*. Si encuentras una forma de leer
archivos fuera de la carpeta de trabajo o de ver la sesión de otro usuario, eso
es exactamente lo que quiero saber.

**3. Archivos de entrada no confiables.** La aplicación abre PDFs e imágenes de
terceros con PyMuPDF, Pillow y OpenCV. Un fallo de memoria en esas librerías al
procesar un archivo malicioso sería relevante; repórtalo también aguas arriba.

## Fuera de alcance

- Que las claves estén en texto plano en el `.bashkar` local: documentado arriba.
- Ejecutar el servidor web sin contraseña y exponerlo a internet: eso es una
  decisión de despliegue, no un fallo del programa.
- Las llamadas a las APIs de IA envían el texto de tu corpus al proveedor que
  elijas. Es el funcionamiento esperado y por eso existen las rutas locales
  (Tesseract, Kraken, Ollama, LM Studio) para trabajar 100 % sin red.

## Para quien clone este repositorio

El historial completo se ha escaneado en busca de credenciales (`sk-`, `sk-ant-`,
`sk-proj-`, `AIza`, `ghp_`, `github_pat_`, `hf_`, `AKIA`): los 349 objetos del
historial están limpios. Las cadenas tipo `sk-ant-xxx` que verás en `tests/` y en
los textos de ayuda son marcadores de ejemplo.
