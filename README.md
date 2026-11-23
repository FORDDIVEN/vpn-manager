# VPN Manager

Gestor gráfico para **OpenVPN 3 y WireGuard** en Linux, desarrollado por **Luthi** con Python y PySide6. Permite organizar perfiles y gestionar sus conexiones desde una sola aplicación.

**Versión actual:** 0.1.9 · **Estado:** en desarrollo

## Funciones

- Perfiles separados en pestañas OpenVPN y WireGuard.
- Importación de archivos `.ovpn` y `.conf`.
- Detección de perfiles WireGuard válidos en `/etc/wireguard/` al iniciar.
- Importación WireGuard a `/etc/wireguard/` o uso de un archivo local sin copiarlo a esa carpeta.
- Nombres, comentarios, favoritos y búsqueda de perfiles.
- Estados de conexión e IP del túnel, con opción para mostrar sólo IPv4.
- Botón **Detener** durante la conexión y **Desconectar** cuando está activa.
- Ventana y columnas redimensionables.
- Una instancia por usuario e integración con la bandeja del sistema.
- Habilitación inicial de WireGuard desde la interfaz, sin editar permisos manualmente.

## Compatibilidad

El paquete `.deb` con Qt/PySide6 incluidos está dirigido a:

| Sistema | Arquitectura |
| --- | --- |
| Linux Mint 22.x | amd64 / x86_64 |
| Ubuntu 24.04 o posterior | amd64 / x86_64 |

Se requiere una sesión gráfica, Python 3.12 o superior y glibc 2.39 o superior. Se ha probado el proyecto en Linux Mint 22.3 y en una VM con Ubuntu 26.04; esto no implica validación en todas las distribuciones o escritorios.

Mint 21 y Ubuntu 22.04 no son compatibles con el paquete actual tal como vienen de fábrica.

Para usar **OpenVPN**, instala **OpenVPN 3 Linux** con sus servicios D-Bus y bindings Python del sistema. El `.deb` lo declara como opcional para permitir usar únicamente WireGuard. OpenVPN 2 no sustituye este requisito.

## Instalar el `.deb`

Desde la carpeta donde tengas el archivo:

```bash
sudo apt install ./vpn-manager_0.1.9_amd64.deb
```

También puedes abrirlo con el instalador gráfico de tu distribución. Después, inicia **VPN Manager** desde el menú de aplicaciones o ejecuta:

```bash
vpn-manager
```

El paquete incluye Qt/PySide6 en una carpeta privada y declara las dependencias del sistema. No necesitas crear un entorno virtual para utilizarlo.

### Habilitar WireGuard

En la primera apertura, pulsa **Autorizar una vez** y autentícate en el diálogo del sistema. También puedes hacerlo desde **Configuración → Habilitar WireGuard**.

La habilitación instala el componente limitado de WireGuard, el permiso persistente de tu cuenta y, cuando corresponde, el ajuste local de AppArmor. Después podrás gestionar WireGuard sin introducir una contraseña administrativa en cada operación. La instalación del paquete y la habilitación de la cuenta son pasos distintos.

La aplicación se ejecuta como usuario normal. Las credenciales que solicite el servidor VPN, como contraseña o MFA, son independientes de esta autorización.

## Uso

### Añadir y organizar perfiles

1. Pulsa **+** y elige **OpenVPN** o **WireGuard**.
2. Selecciona el archivo e indica un nombre, comentario y, si quieres, márcalo como favorito.
3. En WireGuard, elige entre copiar el archivo a `/etc/wireguard/`, seleccionar uno existente o **Usar archivo local (sin copiar)**.
4. Usa el menú **…** del perfil para editar nombre y comentario, cambiar su favorito, consultar la ubicación o quitarlo del gestor.

Los originales se conservan y la importación no sobrescribe archivos existentes. Quitar un perfil del gestor no elimina su configuración: si permanece en `/etc/wireguard/`, volverá a detectarse al iniciar.

### Conectar y consultar el estado

**Conectar** inicia directamente el intento de conexión. Mientras se conecta puedes pulsar **Detener**; al establecerse la conexión, el botón pasa a **Desconectar**.

Los estados se consultan periódicamente. **Configuración → Actualizar estados** permite consultarlos manualmente. En ese mismo apartado puedes activar **Mostrar sólo IPv4 en la columna IP VPN**; la preferencia se conserva entre reinicios.

Arrastra los separadores de los encabezados para ajustar el ancho de las columnas. La columna **IP VPN** muestra `—` cuando no se observa una dirección que cumpla el filtro seleccionado.

### Bandeja y salida

- Un clic en el icono oculta la ventana visible o restaura la oculta o minimizada.
- Con bandeja disponible, la **X** oculta la ventana y la aplicación sigue en segundo plano.
- **Salir**, desde el menú del icono, termina la aplicación. Si hay VPN activas o en proceso, pregunta si quieres desconectarlas: **Sí** desconecta y verifica antes de salir; **No** mantiene el programa abierto.
- Si falla una desconexión o no puede comprobarse el estado, la aplicación permanece abierta.

El icono depende del soporte de bandeja del escritorio. Sin ese soporte, la X cierra la aplicación; desconecta las VPN antes de cerrarla, ya que cerrar la GUI por esa vía conserva los túneles.

## Ejecutar desde el código fuente

Desde la raíz del repositorio, con Python 3.12 o superior:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/vpn-manager
```

En Mint/Ubuntu, si falta el soporte para crear el entorno virtual:

```bash
sudo apt install python3-venv
```

Las herramientas VPN, sus servicios y las bibliotecas gráficas del sistema deben estar disponibles para las funciones que vayas a utilizar.

## Construir el `.deb`

Con el entorno de desarrollo preparado y `dpkg-deb` disponible:

```bash
.venv/bin/python scripts/build-deb.py
```

Se generan estos archivos en `dist/`:

```text
vpn-manager_0.1.9_amd64.deb
vpn-manager_0.1.9_amd64.deb.sha256
```

La versión procede de `pyproject.toml`. El script calcula el tamaño instalado y empaqueta PySide6 Essentials y shiboken6 desde el entorno de construcción, con versiones coincidentes. La construcción no requiere `sudo`.

Para inspeccionar el resultado:

```bash
dpkg-deb --info dist/vpn-manager_0.1.9_amd64.deb
```

Existe una variante ligera con `--qt system`, dirigida a sistemas que proporcionen PySide6 6.8 o superior mediante paquetes de la distribución. Consulta los detalles en la [guía de distribución](docs/distribution.md).

## Pruebas

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -v
```

Las pruebas utilizan herramientas VPN simuladas y archivos temporales. No abren túneles reales. La suite también comprueba sockets locales de instancia única y validaciones con `visudo` y `apparmor_parser`; estas herramientas deben estar disponibles.

## Datos y límites actuales

Los metadatos se guardan en `~/.local/share/vpn-manager/profiles.sqlite3`, o en la ubicación equivalente de `$XDG_DATA_HOME`. SQLite almacena nombres, comentarios, rutas y huellas de los archivos, sin claves privadas ni credenciales VPN.

WireGuard utiliza copias operativas privadas en `/var/lib/vpn-manager/wireguard/`. Se rechazan configuraciones con hooks, `SaveConfig` u opciones no admitidas. Una interfaz WireGuard activa no garantiza que el servidor responda o que exista un handshake reciente.

La aplicación gestiona sus propias conexiones: no adopta automáticamente túneles externos iniciados desde terminal. El soporte OpenVPN para autenticación web/SSO y PKCS#11 está pendiente. Consulta el [backend y sus límites](docs/backend.md) para conocer el comportamiento de permisos, DNS, validación y conservación de copias.

## Documentación

- [Instalación, empaquetado y actualización](docs/distribution.md)
- [Pruebas en otro equipo o VM](docs/testing-vm.md)
- [Backend y permisos](docs/backend.md)
- [Arquitectura](docs/architecture.md)
- [Historial de desarrollo](docs/progress.md)

## Autor

**Luthi**
