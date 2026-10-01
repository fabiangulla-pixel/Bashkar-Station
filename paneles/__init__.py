"""paneles — Las pestañas de BashkarApp, fuera del monolito.

Cada módulo define una clase mixin con los métodos de una pestaña (paso 7 de
las recomendaciones: app.py como punto de composición). BashkarApp hereda de
todas.

Cada panel importa explícitamente lo que usa: lo compartido con app.py vive en
``gui_comun`` (ST, APP_VERSION, ayudas) y los colores del tema en
``gui_comun.TEMA``, que se lee en cada uso porque el tema cambia en caliente.
Así ruff (F821) comprueba los nombres de los paneles como los de cualquier
otro módulo.

Historia: en la primera tanda de la sesión 71 los nombres se inyectaban con
una función ``sincronizar(globals())``; se retiró al hacer los imports
explícitos.
"""
