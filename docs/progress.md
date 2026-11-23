# Avance

## 2026-11-05 — Conexión directa, versión 0.1.9

- Eliminada la confirmación previa del botón Conectar. Verificado inicio del backend con dobles de prueba, sin conexión real.

## 2026-11-05 — Alternar ventana desde bandeja, versión 0.1.8

- Clic simple oculta la ventana visible o muestra/restaura la oculta o minimizada, conservando el programa y las VPN.
- Un diálogo pendiente se muestra en lugar de ocultarse. El menú Mostrar y el segundo lanzamiento mantienen la acción de mostrar.
- Verificado ocultar/mostrar/restaurar mediante activaciones Qt simuladas, sin operaciones VPN.

## 2026-11-05 — Columnas redimensionables, versión 0.1.7

- Eliminados modos Stretch, ResizeToContents y Fixed que bloqueaban columnas. Las seis visibles usan Interactive.
- Verificado arrastre con eventos de ratón Qt en cada separador y conservación del ancho tras refrescar; backend ficticio, sin operaciones de red.

## 2026-11-05 — Ventana redimensionable y filtro IPv4, versión 0.1.6

- Retirado mínimo fijo de 700 × 360; contenido desplazable para tamaños pequeños.
- Preferencia persistente Mostrar sólo IPv4, aplicada a columna y tooltip sin alterar las direcciones del backend.
- Pruebas de tamaño 360 × 220 en todos los apartados, ampliación, persistencia y sesión con sólo IPv6.

## 2026-11-04 — Salida segura desde la bandeja, versión 0.1.4

- Usuario confirma funcionamiento de 0.1.3 en Mint.
- Salir observa estados actuales, confirma si hay conexiones, cancela intentos en curso, desconecta en serie y verifica antes de terminar. No mantiene la aplicación abierta tras una salida correcta.
- Cancela la salida sin modificar conexiones cuando el usuario responde No; conserva la aplicación abierta. La X sigue ocultando con bandeja.
- Fallos, tiempos de espera y estados desconocidos impiden terminar sin confirmación de desconexión.
- 66 pruebas aprobadas, incluida terminación real de un proceso Qt en modo bandeja y liberación del bloqueo. Trabajadores VPN ficticios; sin conexiones reales ni cambios administrativos durante desarrollo.

## 2026-11-04 — Compatibilidad del .deb con Mint 22.3

- Confirmado equipo Linux Mint 22.3/noble, Python 3.12.3: falta el paquete PySide6 de Ubuntu 26.04 requerido por el .deb anterior.
- Versión 0.1.3 amd64: runtime Qt/PySide6 Essentials + shiboken6 privado, sin pip ni repositorios externos durante instalación. Conservada variante --qt system para Ubuntu 26.04.
- Resolución apt simulada correcta y ventana Qt desde el paquete extraído usando Python del sistema en modo aislado, sin abrir túneles ni instalar permisos.
- Compatibilidad con Mint 21 / Ubuntu 22.04 no incluida; instalación real de esta variante pendiente del usuario.

## 2026-10-30 — Instancia única y bandeja, versión 0.1.2

- Usuario confirma funcionamiento del .deb 0.1.1 en una nueva VM limpia.
- Bloqueo privado por usuario y socket local para activar la ventana existente; recuperación tras terminación inesperada.
- Icono de bandeja con Mostrar y Salir, X oculta sólo si hay bandeja disponible; salir conserva conexiones.
- 58 pruebas aprobadas, incluidas comunicación local y caída de proceso, sin VPN ni cambios administrativos.
- Paquete 0.1.2 construido e inspeccionado; presentación del icono pendiente de comprobación en el escritorio de la VM.

## 2026-10-29 — AppArmor automático y paquete .deb experimental

- Habilitación revisión 4: bloque local de AppArmor idempotente, conserva ajustes ajenos, compila sin carga antes de recargar y restaura archivos/perfil ante fallos.
- .deb para Ubuntu 26.04 con dependencias de distribución y acceso en el menú; sin pip durante instalación.
- Distingue instalación del paquete y autorización inicial por cuenta; no concede permisos a todos los usuarios.
- Desinstalación revoca sólo las políticas propias y conserva claves/perfiles.
- 53 pruebas aprobadas; compilación AppArmor sin carga y .deb inspeccionado/extraído sin instalación. Falta prueba real de instalación/desinstalación en VM.

## Biblioteca automática de /etc/wireguard

- Detección asíncrona al iniciar y después de habilitar permisos, sin duplicados ni pérdida de comentarios/favoritos.
- Importación automática a /etc/wireguard con validación, permisos privados y publicación sin sobrescribir destinos.
- Retirada la opción de copia gestionada del diálogo; revisión 3 del componente autorizado.
- 46 pruebas aprobadas, con publicación en carpetas temporales y descubrimiento Qt simulado. No se modificó /etc/wireguard ni se abrieron VPN reales.

## Diagnóstico WireGuard en VM

- Mensajes clasificados sin exponer stderr, claves, endpoints ni rutas del perfil.
- Revisión 2 del componente autorizado para poder actualizar desde Configuración.
- 41 pruebas aprobadas; no se realizaron cambios administrativos ni conexiones reales.

## 2026-10-23 — Habilitación administrativa una sola vez

- Asistente de primer inicio y Configuración → Habilitar WireGuard, con comprobación efectiva del permiso y opción de posponer.
- Instalación explícita mediante diálogo administrativo del sistema; GUI y trabajadores sin root y sin recibir contraseñas.
- Política por cuenta que autoriza sólo el broker fijo sin argumentos; sin acceso general a wg-quick/Python/shell ni modificación de reglas previas.
- Validación con visudo, publicación atómica, prueba como usuario y rollback de archivos/permisos anteriores ante fallos.
- Broker con protocolo cerrado, UID desde sudo, perfiles aislados UID/UUID, validación root de cada configuración, originales intactos y límites de almacenamiento.
- Registro de perfiles posteriores y uso de conexiones sin contraseña administrativa por operación; identidad y propiedad verificadas.
- 40 pruebas aprobadas, incluidos rollback, regla real parseada en /tmp, aislamiento y habilitación Qt simulada que no se repite.
- Comprobación real de sólo lectura: habilitación aún pendiente. No se instalaron archivos, cambiaron sudoers ni abrieron VPN durante esta entrega.


## Ejecución estrictamente con permisos de usuario

- Eliminadas llamadas de elevación del código y retirado el uso de autorizaciones NOPASSWD.
- Listado/lectura/copia opcional de perfiles mediante Python, sin cambios automáticos de permisos o propietario.
- Importación WireGuard local por defecto sin copiar al sistema; comprobada con Qt sin lanzar procesos administrativos.
- No se invoca wg-quick up/down porque el programa instalado intenta elevar permisos por su cuenta. Se muestra la limitación; observación de interfaz/IP sigue disponible.
- OpenVPN 3 conserva cliente D-Bus como usuario; los privilegios de sus servicios externos son independientes.
- 28 pruebas aprobadas, sin cambios del sistema ni VPN reales. Las entradas anteriores describen versiones históricas ya sustituidas.


## Versión personal: WireGuard con sudo existente

- Retirada la dependencia del auxiliar propio, instalador y política polkit; no se modificó el sistema ni sudoers.
- WireGuard ejecuta sudo -n wg-quick up/down con rutas de /etc/wireguard, incluyendo perfiles ya iniciados desde terminal.
- Listado y copia administrativa con herramientas nativas y argumentos estructurados; sin sobrescritura, originales intactos, sin secretos en SQLite/logs.
- Adaptación a los permisos reales de la carpeta privada 0700 y a las secciones en minúsculas existentes en los perfiles.
- Lectura real comprobada: aigis.conf y zintex.conf reconocidos con cero rechazos. No se iniciaron ni detuvieron VPN, ni se copiaron archivos reales.
- 30 pruebas aprobadas con operaciones VPN/sudo sustituidas; validación general documentada como fase posterior.


## Perfiles WireGuard en /etc/wireguard

- Dos orígenes en el diálogo: copiar un archivo importado o seleccionar un .conf protegido existente, con operaciones administrativas asíncronas.
- Auxiliar con acciones limitadas para listar metadatos, inspeccionar y copiar configuraciones normalizadas; root:root 0600, sin enlaces ni sobrescrituras y con huellas verificadas.
- Interfaz basada en el nombre del .conf del sistema; snapshot privado en /run para desconexión y compatibilidad con perfiles antiguos.
- Menú para copiar perfiles existentes externos y actualizar su referencia conservando UUID, comentario y favorito, sólo estando desconectados.
- Detectado que el auxiliar no está instalado. No se han escrito archivos en /etc ni instalado componentes del sistema; pendiente de autorización.
- 28 pruebas aprobadas y flujo Qt verificado con trabajador ficticio; copias, colisiones, permisos, huellas y snapshots probados sólo en directorios temporales. Sin VPN reales.

## Detener un intento de conexión

- Botón Conectar → Detener durante Conectando → Desconectar al confirmar conexión.
- Detener solicita cancelación cooperativa; muestra Deteniendo hasta la comprobación final, sin aceptar clics repetidos.
- OpenVPN 3 limpia la sesión/configuración y verifica el resultado; se cubre la carrera con una conexión tardía.
- Auxiliar WireGuard preparado para cancelar antes de up o revertir con down después de completar la operación de red, sin matar wg-quick a medias.
- 22 pruebas aprobadas, incluidas pruebas Qt de etiquetas/estados/clics y rollback WireGuard con comandos sustituidos. No se iniciaron VPN reales ni se instaló el auxiliar.


## 2026-10-17 — Primer backend OpenVPN 3 y WireGuard

- OpenVPN 3 Linux v25, binding Python/dbus y herramientas WireGuard detectados localmente.
- GUI migrada de simulación a ConnectionManager con QProcess, observación periódica limitada a cuatro trabajadores y errores seguros.
- OpenVPN 3: parser oficial, snapshot memfd, certificados relativos, importación de un solo uso, sesiones propias, estados D-Bus, IP y solicitud de credenciales sin persistencia.
- WireGuard: auxiliar independiente de acciones cerradas, normalización con lista permitida, rechazo de hooks/SaveConfig, directorios privados por UID, interfaz/alias propios y observación IP sin privilegios.
- Preparados instalador y política polkit; NO instalados. No se cambiaron rutas, DNS ni servicios ni se abrieron túneles.
- 18 pruebas automáticas aprobadas; verificación Qt con trabajador ficticio y parser oficial con certificado externo de prueba, sin acceso D-Bus a sesiones.
- Pendiente de autorización: instalación del auxiliar en el sistema. Pruebas reales requieren autorización independiente y selección del perfil.
- Limitaciones: autenticación web/PKCS#11 no implementada, sin cancelación general durante conexión, sin handshake/métricas de WireGuard ni diagnóstico completo del daemon. Ver backend.md.

## 2026-10-17 — Más espacio para las columnas

- Ancho inicial aumentado a 820 px y mínimo a 700 px; altura inicial conservada en 400 px.
- Mayor ancho para Comentario (110 px) e IP VPN (120 px), manteniendo ambas columnas ajustables.
- Verificado con Qt sin pantalla: menú fijo y tabla sin desplazamiento horizontal en tamaño inicial y mínimo.

## Columna IP VPN

- Añadida columna ajustable IP VPN y direcciones opcionales por sesión (no por perfil ni en SQLite).
- Sólo se muestran con sesión conectada, observación disponible y no simulada; en el resto de casos aparece —.
- Tooltip para direcciones completas IPv4/IPv6. No se infiere la IP desde la configuración.
- Verificación Qt con datos controlados: direcciones múltiples, sesión simulada, desconexión, acciones y ausencia de scroll horizontal en ambos tamaños compactos.
- Obtención de direcciones reales pendiente de integrar los backends y la monitorización.

## Comentario visible en el listado

- Columna Comentario junto al nombre en Conexiones y Favoritos, con ancho ajustable y tooltip del texto completo.
- Verificado con Qt sin pantalla: comentario corto visible, actualización tras editar y tabla sin desplazamiento horizontal en 600 × 400 y 560 × 360.

## Selección de protocolo desde +

- + abre un menú OpenVPN/WireGuard independiente de la pestaña activa.
- Después de importar, se muestra el perfil en la pestaña correspondiente.
- Verificado con Qt sin pantalla: ambas opciones desde la pestaña opuesta, importación, selección automática y cancelación sin cambios.

## Importación y biblioteca local

- Botón + junto a las pestañas, con tooltip y diálogo que indican OpenVPN o WireGuard.
- Importación de referencias, reconocimiento básico por contenido, UUID y duplicados por ruta o SHA-256.
- Nombre, comentario y favorito persistentes en SQLite con permisos 0600.
- Menú … para favorito, edición, ubicación y eliminación confirmada sólo del registro.
- Inicio con biblioteca vacía; retirados los ejemplos de la GUI. Las sesiones siguen simuladas y se restablecen sin borrar perfiles.
- Siete pruebas automáticas aprobadas: transiciones, filtros, persistencia, duplicados, entradas inválidas, exclusión del contenido sensible y originales intactos.
- Qt sin pantalla: botón contextual por protocolo, importación, reapertura, menú de edición/favorito/eliminación con diálogos automatizados y tamaños compactos.
- Pendiente: revisión visual, validación completa de configuraciones y dependencias externas, servicio privilegiado y VPN reales.

## Menú fijo y ventana más estrecha

- Menú lateral siempre visible, sin botón de despliegue ni cambios automáticos de ancho.
- Ventana inicial de 600 × 400, mínimo 560 × 360; barra lateral estrecha según el tamaño de fuente.
- Eliminado el encabezado de navegación duplicado y compactada la columna de información.
- Verificación Qt sin pantalla en ambos tamaños: cinco destinos, menú sin solapamientos, protocolos, favoritos y acciones; tabla sin desplazamiento horizontal.

## Gestión unificada en Conexiones

- Eliminada la entrada Perfiles del menú; listado y detalle centralizados en Conexiones.
- Favoritos mantiene únicamente los perfiles con estrella y oculta el filtro redundante «Solo favoritos».
- Verificados los cinco destinos, listas completas y favoritas en ambos protocolos y apertura/cierre del menú con Qt sin pantalla.

## Panel lateral separado

- El menú ocupa su propio espacio a la izquierda del contenido, sin superposición.
- Abrir amplía el ancho de la ventana; cerrar retira ese espacio. En modo maximizado se distribuye el espacio disponible.
- Verificado con Qt sin pantalla: contenido sin solapamientos, ancho preservado, seis destinos y ciclos repetidos de apertura/cierre, también desde el tamaño mínimo.

## Menú lateral plegable

- Selector de secciones reemplazado por botón ☰ fijo a la izquierda y panel lateral superpuesto.
- El mismo botón abre y oculta el menú; permanece abierto al elegir una sección.
- No cambia el tamaño de la ventana ni comprime la tabla.
- Verificación Qt sin pantalla: apertura y cierre, seis destinos, rótulo de sección, redimensionamiento y separación por protocolo.

## Comentarios de perfil

- Eliminados los selectores de estado y categoría de la interfaz.
- Categoría reemplazada por un comentario libre en el modelo y ejemplos.
- Comentario disponible en detalle, tooltip del nombre y búsqueda.
- Importación y edición siguen pendientes; no hay datos persistidos que migrar.

## Ventana compacta

- Tamaño inicial de 640 × 440, redimensionable desde 560 × 380.
- Navegación mediante selector superior en lugar de barra lateral; inicio en Conexiones.
- Búsqueda en su propia fila y tabla reducida a perfil, estado, acción y detalle.
- Protocolo en pestañas; categoría disponible en filtros y detalle.
- Aviso permanente de demostración y aclaración de acciones simuladas en tooltips.
- Verificación Qt sin pantalla: navegación sin crecimiento automático, protocolos separados, acciones y tabla sin desplazamiento horizontal en ambos tamaños. Pendiente revisión visual en el escritorio.

## Separación visual por protocolo

- Pestañas OpenVPN y WireGuard en Conexiones, Perfiles y Favoritos, en lugar del selector combinado de protocolos.
- Búsqueda y filtros conservados al cambiar de pestaña.
- Verificación Qt sin pantalla: separación en las tres vistas, favoritos, filtros combinados, lista vacía y acción simulada.

## 2026-10-16 — Primera entrega

Implementado:
- Proyecto Python instalable y entrada `vpn-manager`.
- Dominio independiente de Qt y backend de demostración en memoria.
- Ventana Qt Widgets, navegación, dashboard, búsqueda y filtros combinados.
- Favoritos de ejemplo, detalle, registros filtrables y copia de diagnóstico simulado.
- Estados transitorios con QTimer, protección contra solicitudes repetidas y restablecimiento.
- Rechazo del inicio normal como root.
- Pruebas de transiciones, aislamiento de sesiones, filtros y restablecimiento.

Limitaciones explícitas:
- Conexiones y Perfiles comparten listado; no hay importación ni edición.
- Sin SQLite, perfiles reales, métricas reales, D-Bus, polkit ni operaciones VPN.
- Favoritos y categorías son datos de ejemplo, no editables todavía.
- No se han probado conexiones reales ni modificado el sistema.

Siguiente entrega:
1. Revisar el script Bash cuando esté disponible, sin secretos.
2. Importación y validación no privilegiada con referencias externas y duplicados.
3. SQLite, edición de metadatos y eliminación de registros sin borrar originales.
4. Política de configuraciones admitidas y contrato D-Bus antes del auxiliar.
5. Backend OpenVPN y luego WireGuard, con pruebas controladas.

Se requerirá autorización explícita antes de pruebas con VPN reales o cambios de red/servicios.

Validación de esta entrega:
- Dependencias instaladas en `.venv`, PySide6 6.12.0.
- Tres pruebas de dominio aprobadas y compilación sintáctica correcta.
- Qt probado con plataforma `offscreen`: apertura/cierre, seis entradas de navegación, búsqueda, transición asíncrona y cancelación de temporizadores al restablecer.
- Pendiente revisión visual en la sesión de escritorio del usuario.
