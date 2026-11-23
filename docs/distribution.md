# Instalación de escritorio (.deb experimental)

Desde 0.1.3 hay un paquete amd64 con Qt/PySide6 incluidos en una ruta privada para Linux Mint 22.x / Ubuntu 24.04 o posterior, con Python >= 3.12 y glibc >= 2.39. No requiere `python3-pyside6.qtwidgets` de los repositorios. No es compatible con Mint 21 / Ubuntu 22.04 tal como vienen de fábrica.

El paquete anterior `0.1.2_all.deb` utilizaba PySide6 del sistema, disponible en la VM Ubuntu 26.04 pero no en Mint 22.3. El mensaje de apt sobre dependencias o posibles paquetes retenidos no prueba por sí solo que existan paquetes rotos: aquí falta una dependencia concreta. No mezclar repositorios de Ubuntu 26.04 para instalarla en Mint.

## Usuario final

1. Descargar vpn-manager_0.1.9_amd64.deb y abrirlo con el instalador de software de Ubuntu. También se puede instalar desde terminal con `sudo apt install ./vpn-manager_0.1.9_amd64.deb`; apt resuelve las dependencias declaradas.
2. Abrir **VPN Manager** desde el menú de aplicaciones.
3. Pulsar **Autorizar una vez** y autenticarse en el diálogo administrativo. Se concede permiso persistente sólo a esa cuenta y al componente limitado. Si ya usabas otra versión, entra en **Configuración → Habilitar WireGuard** para actualizar la habilitación.
4. Importar perfiles y usar las conexiones. La GUI siempre se ejecuta como usuario normal.

La instalación del .deb y la habilitación por cuenta son dos acciones administrativas distintas; no se promete una única solicitud de contraseña para ambas. No hay que editar sudoers ni AppArmor a mano. La aplicación no inicia VPN durante la habilitación. El permiso no se concede automáticamente a todos los usuarios del equipo.

El paquete incluye PySide6 Essentials y shiboken6 y declara Python, las bibliotecas nativas de X11/Wayland/OpenGL, python3-dbus, wireguard-tools, iproute2, sudo, pkexec y AppArmor. Necesita una sesión gráfica con agente de autenticación. OpenVPN 3 es opcional para quien use sólo WireGuard: para OpenVPN debe instalarse previamente con sus bindings del sistema, siguiendo la guía oficial de OpenVPN. No se añaden repositorios externos automáticamente. El soporte DNS que requiera el perfil debe estar disponible; en la VM usada, resolvconf lo proporciona resolvectl/systemd-resolved.

## Ajuste AppArmor automático

La habilitación de revisión 4 detecta `/etc/apparmor.d/wg-quick`. Si existe, comprueba propietario/permisos y la inclusión de `local/wg-quick`. Añade un bloque delimitado en ese archivo local, conservando el resto. Autoriza sólo lectura de copias operativas de VPN Manager, /etc/nsswitch.conf y /etc/passwd. No desactiva AppArmor ni cambia perfiles a modo permisivo.

Primero compila con `apparmor_parser -Q -K`, después recarga sólo wg-quick. Las reglas se probaron con el compilador sin cargar política. Cualquier fallo del proceso de habilitación restaura los archivos originales; si se intentó recargar, vuelve a cargar el perfil restaurado. Un formato de perfil desconocido se rechaza con un mensaje en el asistente en lugar de modificarlo a ciegas.

Si no existe ese perfil de AppArmor, la habilitación continúa sin crearlo. Otras políticas de seguridad o reglas particulares pueden requerir diagnóstico propio. Las excepciones que ya se añadieron manualmente no se eliminan: sólo se administra el bloque de VPN Manager.

## Actualizar y desinstalar

Actualizar instalando el nuevo .deb. Si el componente o permiso anterior requiere actualizarse, usar Configuración → Habilitar WireGuard. Al desinstalar, dpkg retira la GUI y los componentes del paquete; el script postrm revoca las reglas sudoers marcadas como propias y elimina únicamente el bloque AppArmor de VPN Manager. Conserva reglas ajenas, archivos VPN, copias privadas y biblioteca del usuario. Usar Salir y confirmar la desconexión antes de desinstalar: el script de desinstalación no ejecuta down automáticamente.

## Construir y validar

Desde la raíz del proyecto, `.venv/bin/python scripts/build-deb.py` produce el .deb amd64 y su SHA-256 en dist/. Requiere Python 3.12, dpkg-deb y PySide6 Essentials/shiboken6 instalados con versiones coincidentes en el entorno de construcción. Copia únicamente archivos de esos dos wheels según sus manifiestos RECORD, sin bytecode ni otros paquetes del entorno. El runtime actual es 6.12.0 y se registra en el paquete. Se incluyen textos GPL/LGPL y referencias a los fuentes de Qt/PySide6; se mantiene enlace dinámico.

La ruta privada es `/usr/lib/vpn-manager/vendor/`; el lanzador aislado de Python la añade sólo para esta aplicación. No se instala pip ni se descargan wheels durante la instalación del .deb. Los trabajadores OpenVPN siguen usando `/usr/bin/python3` y los bindings de la distribución. Al incluir bibliotecas nativas, el paquete deja de ser Architecture: all y aumenta de tamaño (aprox. 69 MiB comprimidos).

Se conserva `python3 scripts/build-deb.py --qt system` para construir la variante ligera con Qt de los repositorios de Ubuntu 26.04. Esa variante sigue sin servir para Mint 22.

Construye con propietarios root sin ejecutar instalación ni scripts administrativos. No incluye .venv completo, perfiles, claves, bases SQLite ni repositorio git. Inspeccionar con `dpkg-deb --info` y `dpkg-deb --contents`.

Las pruebas automatizadas usan archivos temporales y comandos simulados; incluyen preservación de ajustes, idempotencia, compilación real sin carga y rollback tras fallo. La instalación/desinstalación real de este .deb y el flujo AppArmor integrado aún deben comprobarse en una instantánea de la VM. El ajuste manual equivalente ya funcionó en la VM del usuario.

## Versión 0.1.2: instancia única y bandeja

Cerrar por completo la versión anterior antes de actualizar. Esta actualización no cambia el protocolo de permisos ni requiere volver a habilitar WireGuard si ya estaba en revisión 4. Un segundo lanzamiento activa la primera ventana mediante un socket local privado, sin crear otra biblioteca ni otros trabajadores. El bloqueo se libera al finalizar incluso tras una terminación inesperada.

Desde 0.1.4, el icono de bandeja permite mostrar la ventana y salir después de comprobar las conexiones. Si existen conexiones activas o en curso, Sí solicita cancelación/desconexión y verifica el resultado antes de salir; No conserva el programa abierto. Un error o estado desconocido impide cerrar. Con bandeja disponible, la X sólo oculta; sin bandeja, la X cierra como antes. La disponibilidad y ubicación del icono dependen del escritorio: en GNOME se necesita soporte de indicadores en la sesión. La aplicación comprueba la disponibilidad y no se oculta al cerrar si no la detecta. No instala extensiones del escritorio.

La versión 0.1.1 fue instalada y utilizada correctamente por el usuario en una segunda VM limpia. La versión 0.1.2 añade pruebas de exclusión, activación, recuperación tras cierre inesperado y comportamiento con/sin bandeja. La presentación real del icono de esta actualización debe comprobarse en el escritorio de la VM.

## Verificación de 0.1.3 en Mint 22.3

Se resolvió el paquete con `apt-get -s install` sin errores, sin instalarlo. Se extrajo y abrió una ventana Qt con `/usr/bin/python3 -I`, sin entorno virtual ni PYTHONPATH externo, comprobando que PySide6 y shiboken6 procedían del runtime incluido. Esa prueba utiliza un backend inyectado sin operaciones de red. La instalación real y conexiones de esta variante siguen pendientes de prueba por el usuario; no se modificó el sistema del equipo de desarrollo.

## Versión 0.1.4: Salir con desconexión confirmada

Se observan estados reales antes de salir, evitando confiar en un Desconectado antiguo. Tras confirmar, las desconexiones se hacen en serie para evitar conflictos entre operaciones WireGuard. Se vuelve a consultar todos los perfiles antes de cerrar la GUI y terminar el proceso. No se matan trabajadores de conexión como atajo para salir. El sondeo normal se pausa durante la salida y se restaura al cancelar o fallar. La X sigue ocultando cuando hay bandeja; los perfiles externos que la aplicación no gestiona no se adoptan ni se desconectan.

El usuario confirmó que el paquete con runtime privado 0.1.3 funciona en Mint 22.3. Para actualizar a 0.1.4, salir de la versión anterior y luego instalar el paquete nuevo. No cambia la revisión 4 de permisos.

## Versión 0.1.6: tamaño de ventana y visualización de IPv4

Se elimina el mínimo fijo de 700 × 360. La ventana puede reducirse y ampliarse; cuando el contenido no cabe, el área central ofrece desplazamiento. Configuración permite mostrar únicamente IPv4 en la columna IP VPN y en su texto emergente. La preferencia se guarda por usuario. No desactiva IPv6 ni modifica túneles o rutas. La versión y el tamaño instalado se mantienen en los metadatos del .deb.
