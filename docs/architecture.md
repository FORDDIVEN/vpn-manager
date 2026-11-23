# Arquitectura vigente: habilitación inicial limitada

- gui/: Qt Widgets, biblioteca y asistente de permisos. Usuario normal.
- core/: modelos, importación y ConnectionManager asíncrono con QProcess.
- database/: SQLite para metadatos, rutas y huellas, sin secretos.
- system/worker.py: cliente OpenVPN 3/D-Bus y coordinación del cliente WireGuard.
- system/permissions_client.py: llamadas a un broker fijo sin argumentos y comprobación de autorización efectiva.
- system/permissions_installer.py: instalador inicial explícito, invocado mediante pkexec tras la confirmación del usuario.
- system/privileged_wireguard.py: broker instalado propiedad de root; protocolo cerrado e identidad desde sudo, aislamiento UID/UUID.
- system/wireguard_config.py: normalizador que se instala también con propietario root y se ejecuta en la frontera privilegiada.

La única autorización administrativa inicial crea un permiso persistente para el broker sin argumentos. No se autoriza ejecución libre de wg-quick ni se amplían permisos a Python/shell. El broker gestiona sólo configuraciones normalizadas privadas, con lista de opciones permitidas y rechazo de hooks.

Importar perfiles futuros no modifica sudoers: la cuenta habilitada registra datos validados y puede operar sus propias sesiones. Los registros y copias quedan aislados por UID/UUID, y las interfaces llevan identidad comprobada. Los originales permanecen intactos.

La GUI continúa sin privilegios. La preferencia local de bienvenida no equivale a autorización: cada operación verifica el componente instalado y sudo comprueba el permiso real. OpenVPN 3 utiliza sus propios servicios D-Bus existentes y mantiene independiente la autenticación del servidor VPN.

El instalador usa validación de candidato/global con visudo, publicación atómica, verificación como usuario y rollback. No instala servicios residentes ni inicia VPN durante la habilitación. Los cambios reales de sistema requieren la confirmación administrativa de ese asistente.

Ver backend.md para archivos instalados, dependencias, límites, cancelación, retención de copias y pruebas.
