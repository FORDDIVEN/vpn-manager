# VPN Manager

Aplicación de escritorio para Linux, desarrollada incrementalmente con Python y PySide6.

**Modo actual: habilitación inicial y uso habitual sin contraseña administrativa.** La GUI sigue como usuario normal. En el primer inicio ofrece **Autorizar una vez** para instalar un componente limitado y el permiso persistente de tu cuenta. Después WireGuard puede registrar perfiles validados, conectar, detener y desconectar sin otra contraseña de root por operación.

No se concede acceso general a comandos de root ni se modifica tu regla existente. La configuración usa un archivo propio en sudoers.d, validado con visudo y restaurado si falla. La contraseña inicial la recibe el diálogo del sistema, nunca la aplicación. También se puede habilitar desde **Configuración → Habilitar WireGuard**.

OpenVPN 3 mantiene sus servicios D-Bus. Las credenciales del servidor VPN son distintas de la autorización administrativa y pueden seguir solicitándose. Ver [backend y límites actuales](docs/backend.md). Las pruebas aún no han realizado una habilitación real ni abierto túneles.

## Ejecutar

Python 3.12 o superior y una sesión gráfica Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/vpn-manager
```

Ejecutar como usuario normal, sin `sudo`. PySide6 requiere las bibliotecas gráficas de Qt y del sistema; si falta alguna, revisar el mensaje del cargador antes de instalar paquetes de la distribución.

La ventana (820 × 400 inicialmente, redimensionable con contenido desplazable) abre en Conexiones. El menú lateral permanece fijo y permite navegar por el resumen, conexiones, favoritos, registros y configuración. El menú de cada perfil se abre con el botón «…». Conexiones reúne el listado y detalle de todos los perfiles; Favoritos muestra únicamente los marcados con estrella. En Conexiones y Favoritos, las VPN se separan en pestañas OpenVPN y WireGuard. La búsqueda y los filtros se aplican al protocolo seleccionado y se conservan al cambiar de pestaña. Al iniciar se muestra **Conectando** y el botón **Detener**; al confirmar la conexión pasa a **Desconectar**. Detener solicita la cancelación y comprueba la desconexión antes de volver a **Conectar**. Los estados e IP se actualizan periódicamente. Configuración permite actualizar los estados manualmente. Cerrar la ventana conserva las conexiones activas. La búsqueda incluye nombres, comentarios y etiquetas; los filtros se combinan.

## Verificar

Las pruebas usan dobles de las herramientas VPN y no modifican la red:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Para comprobar Qt sin una sesión gráfica, después de instalar las dependencias:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -c 'from PySide6.QtWidgets import QApplication; from vpn_manager.gui.main_window import MainWindow; app = QApplication([]); window = MainWindow(); window.show(); app.processEvents(); window.close()'
```

Consultar [arquitectura](docs/architecture.md) y [avance](docs/progress.md).

## Importar y editar

1. Pulsar **+** y elegir **OpenVPN** o **WireGuard** en su menú, sin cambiar de pestaña previamente. Al importar se muestra automáticamente la pestaña del protocolo elegido.
2. En OpenVPN, elegir un `.ovpn`. En WireGuard, elegir un `.conf` local: se copia automáticamente a `/etc/wireguard/`. Los perfiles válidos de esa carpeta aparecen al iniciar, tras habilitar WireGuard. También se puede seleccionar uno desde el diálogo o elegir **Usar archivo local (sin copiar)** para guardar sólo la referencia al archivo original. Indicar nombre y comentario y, opcionalmente, marcar Favorito. Tras la habilitación inicial, WireGuard valida y copia los perfiles sin pedir otra contraseña administrativa. Los archivos existentes nunca se sobrescriben.
3. Usar **…** para cambiar favorito, editar nombre/comentario, ver la ubicación o quitar el perfil del gestor.

El comentario aparece en su propia columna junto al nombre, tanto en Conexiones como en Favoritos, y se puede buscar. La columna se puede ensanchar arrastrando su borde; el texto completo también aparece al pasar el puntero. La columna **IP VPN** está preparada para mostrar las direcciones IPv4/IPv6 asignadas al túnel en una sesión real; muestra **—** si no hay una dirección observada. OpenVPN 3 muestra el estado de su sesión; WireGuard muestra la interfaz propia activa, sin confirmar conectividad del peer. Los cambios persisten al reiniciar. Quitar un perfil requiere confirmación y conserva el archivo original.

La biblioteca se guarda en `$XDG_DATA_HOME/vpn-manager/profiles.sqlite3` (normalmente `~/.local/share/vpn-manager/profiles.sqlite3`) con permisos 0600. SQLite sólo almacena metadatos, ruta y huella SHA-256, sin claves ni credenciales. Las copias WireGuard se guardan por separado en `/var/lib/vpn-manager/wireguard/<uid>/<uuid>/`, privadas y gestionadas por el componente autorizado, sin sobrescribir originales. No escribir secretos en nombres o comentarios.

La importación detecta formato y duplicados; la validación privilegiada se realiza nuevamente al registrar/conectar. Los perfiles WireGuard con hooks, SaveConfig u opciones no admitidas se rechazan. Las fuentes originales se conservan. Consulta docs/backend.md para dependencias, revisiones, límites y retención de copias.

## Probar en otro equipo o VM

Consulta la [guía de instalación y prueba manual](docs/testing-vm.md). El paquete de fuentes se instala en un entorno virtual nuevo en el equipo destino.

Los perfiles WireGuard de `/etc/wireguard/` se detectan automáticamente al abrir y después de habilitar los permisos. Se conservan comentarios y favoritos y se omiten duplicados. Quitar del gestor no elimina el archivo: volverá a detectarse en el siguiente inicio. Los perfiles con formato u opciones no admitidas se omiten y se informa en Logs.

## Instalador .deb experimental

La versión 0.1.9 amd64 incluye Qt/PySide6 para Mint 22.x y Ubuntu 24.04 o posterior; instala desde el gestor de software y abre VPN Manager desde el menú. La primera habilitación gestiona también el ajuste local de AppArmor, con validación y restauración ante fallos. No requiere editar permisos manualmente. Ver [distribución, actualización y límites](docs/distribution.md). Construir con `.venv/bin/python scripts/build-deb.py`.

## Instancia única y bandeja

Sólo se abre una instancia por usuario. Un segundo lanzamiento muestra la ventana existente, también si estaba oculta. Si el escritorio ofrece bandeja del sistema, cerrar con la X oculta la ventana y mantiene la aplicación abierta. El menú del icono permite mostrarla o **Salir**. Si hay VPN activas o conectándose, pide confirmación: Sí cancela/desconecta y sólo sale tras verificar; No conserva el programa abierto. Un fallo o estado desconocido impide salir. Sin bandeja disponible, cerrar la ventana termina la aplicación como antes.

En **Configuración → Mostrar sólo IPv4 en la columna IP VPN** se puede ocultar IPv6 de la tabla y su texto emergente. La preferencia se conserva al reiniciar y no modifica la configuración de red. Sin IPv4 observada se muestra —.

Todas las columnas visibles se pueden redimensionar arrastrando los separadores de sus encabezados, incluidas Perfil, Estado, Acción y ⋯. La actualización de estados conserva los anchos durante la sesión.

Un clic en el icono de bandeja alterna entre ocultar la ventana visible y mostrarla si estaba oculta o minimizada. Si hay un diálogo abierto, se muestra para que puedas responder. El menú Mostrar VPN Manager siempre muestra la ventana.

El botón Conectar inicia el intento directamente, sin confirmación adicional de rutas/DNS. Las credenciales que solicite la VPN y la autorización inicial de WireGuard siguen su flujo habitual.
