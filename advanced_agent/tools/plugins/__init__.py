"""Carpeta de plugins de tools.

Cada módulo aquí define una o más subclases de `Tool`. El `ToolRegistry` las
descubre e instancia automáticamente al arrancar — agregar una tool nueva es
soltar un archivo en esta carpeta, sin tocar el núcleo del harness.
"""
