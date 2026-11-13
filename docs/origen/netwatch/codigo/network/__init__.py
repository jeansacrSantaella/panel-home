"""Acceso a la red y a los comandos del sistema (ping, arp, route)."""
import platform

IS_MAC = platform.system() == "Darwin"
