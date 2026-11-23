# Habilitación inicial y backend VPN

## Experiencia de uso

La primera apertura muestra el asistente **Habilitar WireGuard**. Se comprueba primero el permiso real de la cuenta; no se confía en una preferencia local para decidir que esté habilitado.

Si falta, el usuario pulsa **Autorizar una vez** y se autentica en el diálogo administrativo del sistema (pkexec/polkit). La aplicación no recibe ni guarda la contraseña. El instalador no inicia túneles ni modifica rutas o DNS.

Después de habilitar, importar perfiles, conectar, detener y desconectar WireGuard no solicita contraseña administrativa por operación ni por reinicio de la GUI. El permiso persiste entre reinicios de Linux. Revocaciones, actualizaciones de protocolo, otra cuenta o cambios del sistema pueden requerir autorización nuevamente. Las credenciales de la propia VPN (usuario, contraseña, MFA de OpenVPN) son independientes y pueden seguir siendo necesarias.

Se puede posponer el asistente y habilitar más tarde en **Configuración → Habilitar WireGuard**. La preferencia de bienvenida sólo evita repetir el aviso; las operaciones siguen comprobando la autorización efectiva.

## Qué se instala, con una autorización

- `/usr/libexec/vpn-manager/wireguard-helper`: broker Python aislado, root:root 0755.
- `/usr/libexec/vpn-manager/wireguard_config.py`: validador, root:root 0644.
- `/etc/sudoers.d/vpn-manager-<uid>`: permiso de la cuenta, root:root 0440.

La regla autoriza únicamente el broker **sin argumentos**. No concede NOPASSWD: ALL, ni acceso directo a wg-quick, Python, shells, cp o comandos arbitrarios. No se edita `/etc/sudoers`, no se elimina ninguna regla previa y no se añade un servicio residente.

El instalador valida un candidato con `visudo -c -f`, publica archivos de forma atómica, valida la configuración global y prueba el permiso como la cuenta destino. Si falla, restaura los contenidos/permisos anteriores. Rechaza enlaces, destinos inseguros o una política existente que no esté marcada como administrada por VPN Manager. La instalación entre usuarios se serializa.

Requisitos de esta primera versión: Linux de escritorio con sudo, visudo, pkexec, agente de autenticación gráfico, Python 3, ip y wg-quick. El asistente informa componentes faltantes. OpenVPN 3 Linux debe aportar sus bindings Python/dbus del sistema. El empaquetado por distribución que declare estas dependencias queda para la fase de distribución.

## Operaciones posteriores y seguridad

La GUI y los trabajadores permanecen como usuario normal. El trabajador ejecuta `sudo -n -- /usr/libexec/vpn-manager/wireguard-helper`, sin argumentos. Envía solicitudes JSON de un protocolo cerrado por stdin; stderr de componentes externos nunca se incorpora al diagnóstico.

El broker obtiene la identidad de `SUDO_UID`, establecido por sudo, y admite exclusivamente probe, list, publish-system, register, register-system, inspect, connect, disconnect, cancel y status. No acepta comandos, ejecutables, unidades, PID ni rutas arbitrarias para ejecutar como root.

Cada UID/UUID tiene su propia copia normalizada en `/var/lib/vpn-manager/wireguard/<uid>/<uuid>/`, con directorios root 0700 y configuración 0600. El nombre de interfaz es derivado del UID/UUID. La propiedad se verifica mediante tipo WireGuard y alias de interfaz; no se toma control de túneles externos. Los registros de usuarios distintos están separados, aunque compartan UUID.

Registrar y conectar vuelven a validar el contenido con una lista permitida. Sólo se admiten claves base64 de 32 bytes, direcciones/redes, DNS/dominios limitados, endpoint y parámetros numéricos admitidos. Se rechazan hooks PreUp/PostUp/PreDown/PostDown, SaveConfig, inclusiones, opciones desconocidas y valores no válidos. Los archivos del sistema tampoco se consideran ejecutables confiables sin validación. Nuevos perfiles admitidos pueden registrarse tras la habilitación inicial sin otra contraseña administrativa.

En **+ → WireGuard**, la opción predeterminada **Importar archivo a /etc/wireguard** valida y copia el archivo automáticamente a `/etc/wireguard/<nombre>.conf`, root:root 0600. La publicación se hace con archivo temporal privado y enlace atómico sin reemplazar destinos; se rechazan enlaces y colisiones con distinto contenido. Un nombre inválido o demasiado largo se sustituye por uno derivado del UUID. No se copian hooks ni se ejecuta el perfil al importar. La carpeta debe estar controlada por root y no ser escribible por otros. El límite es 1024 perfiles / 64 MiB en esa carpeta.

Al abrir la GUI y tras habilitar permisos, un trabajador consulta los archivos `.conf` válidos de `/etc/wireguard/` y añade sus metadatos a SQLite. Se mantienen UUID, nombres, comentarios y favoritos existentes, evitando duplicados por ruta o huella. No se leen claves en la GUI. Los archivos no admitidos se cuentan en Logs. La sincronización no borra entradas ni sustituye revisiones modificadas externamente: en ese caso hay que volver a importar la revisión. Quitar del gestor conserva el archivo del sistema y reaparecerá al iniciar.

Las conexiones mantienen las copias operativas privadas y comprobaciones de propiedad descritas arriba; la biblioteca referencia `/etc/wireguard/`. No se adoptan conexiones iniciadas manualmente con wg-quick. El componente de revisión 3 debe actualizarse desde Configuración → Habilitar WireGuard; esa actualización requiere una autorización administrativa.

Las copias gestionadas permanecen aunque se quite un registro de la biblioteca; su limpieza administrativa queda pendiente. Para acotar almacenamiento, hay un límite por cuenta de 1024 copias y 64 MiB. Una revisión registrada no se reemplaza bajo el mismo UUID: se importa como un perfil nuevo. SQLite sólo guarda metadatos, ruta y huella, nunca claves o contraseñas.

## Estado y cancelación

OpenVPN 3 usa la API D-Bus oficial con configuraciones transitorias de un solo uso, parser oficial para certificados relativos, estados observados y credenciales por canal privado. Autenticación web/SSO y PKCS#11 siguen pendientes.

WireGuard ejecuta wg-quick exclusivamente sobre la copia privada validada. Su estado/IP se observa en la interfaz propia; UP no demuestra handshake reciente ni accesibilidad del peer. DNS depende del soporte resolvconf de la distribución. No hay análisis automático completo de conflictos de rutas.

Conectando muestra Detener; una cancelación se comprueba antes de up y después de la operación de red. No se mata wg-quick a mitad de rutas/DNS: se ejecuta down al terminar. Una conexión que finalice justo al detener también se verifica y desconecta. Un fallo de limpieza/consulta no se convierte artificialmente en Desconectado.

La GUI conserva capacidad de respuesta mediante QProcess, limita consultas simultáneas y espera operaciones mutantes antes de cerrar. Cerrar la aplicación mantiene las conexiones establecidas. Los logs actuales contienen eventos y errores seguros, no el registro completo de los daemons.

## Validación y estado del sistema

40 pruebas aprobadas con carpetas temporales, trabajadores ficticios y comandos de red sustituidos. Incluyen aislamiento por UID, rechazo de hooks/rutas/argumentos, permisos de archivos, cancelación, parser real de sudoers sobre un archivo temporal, rollback de archivos nuevos y existentes, política ajena intacta y asistente Qt que habilita una sola vez.

La activación real en este equipo está pendiente: se comprobó que aún no existe un componente habilitado, sin instalarlo ni cambiar sudoers. No se han conectado VPN ni modificado rutas/DNS durante esta entrega. La primera activación real se realizará cuando el usuario pulse Autorizar una vez y confirme en el diálogo del sistema.

También está disponible **Usar archivo local (sin copiar)**: al importar se guarda sólo la referencia, sin publicación en `/etc/wireguard/` ni llamada al componente privilegiado. Al conectar, el backend crea su copia operativa privada validada como antes.

## Integración AppArmor y distribución

La habilitación de revisión 4 administra un bloque local limitado en `/etc/apparmor.d/local/wg-quick` cuando el perfil de distribución lo permite. Se compila antes de recargar y se restaura ante fallo. El permiso no se extiende a comandos o rutas libres. Ver [paquete .deb y ciclo de instalación](distribution.md).
