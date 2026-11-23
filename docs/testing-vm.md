# Probar en otro equipo o una máquina virtual

El ZIP contiene código y pruebas, sin entorno virtual, perfiles, claves ni la base de datos personal. Es una distribución de fuentes, todavía no un instalador .deb. La autorización real y los túneles necesitan una prueba manual; las pruebas automatizadas simulan esas operaciones.

## Preparar Linux

Para una primera prueba, usa una instalación de escritorio similar al equipo de desarrollo (Linux Mint 22.x), con Python 3.12 o superior. En una VM, inicia una sesión gráfica y toma una instantánea antes de autorizar la aplicación. Puedes empezar con el adaptador de red NAT; el servidor VPN debe ser accesible desde la VM.

Usa una cuenta normal con capacidad de autenticarse como administrador. Para comprobar la experiencia de un usuario nuevo, esa cuenta no debe tener una regla general NOPASSWD: ALL. No ejecutes la GUI con sudo.

Instala OpenVPN 3 siguiendo la [guía oficial](https://openvpn.net/community-docs/openvpn-client-for-linux/) para tu distribución y WireGuard desde los paquetes del sistema. También se necesitan Python venv/pip, sudo/visudo, pkexec, un agente gráfico de autenticación y el comando ip. El asistente informa los componentes faltantes. Los perfiles WireGuard con DNS pueden necesitar resolvconf; consulta las dependencias de wg-quick en tu distribución.

Comprueba las herramientas sin abrir conexiones:

```bash
python3 --version
command -v openvpn3 wg wg-quick ip sudo visudo pkexec
/usr/bin/python3 -I -c 'import dbus, openvpn3; print("Bindings OpenVPN 3 disponibles")'
```

## Copiar e instalar

Copia vpn-manager-0.1.0.zip al destino y descomprímelo. No copies el entorno .venv del equipo original: se crea de nuevo. Desde una terminal en la carpeta descomprimida:

```bash
cd vpn-manager-0.1.0
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/vpn-manager
```

La instalación con pip necesita acceso a los paquetes de Python. Si Qt informa de una biblioteca gráfica ausente, instala la dependencia del sistema que indique el error. Las pruebas no habilitan permisos ni abren VPN reales.

## Prueba manual

1. En el primer inicio, pulsa **Autorizar una vez** y autentícate en el diálogo del sistema. Debe confirmar que WireGuard quedó habilitado. También puedes acceder desde **Configuración → Habilitar WireGuard**. Este paso instala el componente y su permiso limitado; no conecta una VPN.
2. Cierra y vuelve a abrir la aplicación. Comprueba que reconoce el permiso. Repite después de reiniciar Linux: no debe pedir otra contraseña administrativa para usar WireGuard.
3. Transfiere por separado perfiles de prueba válidos y sus certificados necesarios. Pulsa **+**, elige el protocolo e importa el archivo. Comprueba comentario, favorito y persistencia al reiniciar la GUI.
4. Conecta primero una VPN y comprueba **Conectando → Conectado**, el botón **Desconectar** y la IP del túnel. Prueba acceso a un recurso conocido de esa VPN. En WireGuard, una interfaz activa no garantiza que el servidor responda.
5. Desconecta y verifica que se retira el túnel. Repite con el otro protocolo. Si una conexión tarda, prueba **Detener** y espera a que confirme la desconexión. Las credenciales de OpenVPN pueden pedirse aunque la autorización administrativa ya esté guardada.

Cerrar la ventana conserva las conexiones activas: desconéctalas antes de finalizar la prueba. En una VM, los cambios de rutas y DNS se realizan dentro del sistema invitado. Restaura la instantánea para repetir desde cero la habilitación y eliminar también los archivos administrativos instalados.

Si falla, anota distribución, versión de Python, protocolo, paso y mensaje de error. No compartas claves privadas, contraseñas ni archivos de configuración completos. Los perfiles con hooks, SaveConfig u opciones no admitidas se rechazan en esta versión; consulta [backend y límites](backend.md).

## Diagnóstico de fallos WireGuard

El broker de revisión 2 distingue errores conocidos de resolvconf, resolución del servidor, permisos, kernel, conflictos de rutas y herramientas de firewall sin mostrar salida sensible. Para actualizar una instalación anterior, instala el ZIP nuevo, reinicia la GUI y entra en Configuración → Habilitar WireGuard → Autorizar una vez. Esta actualización del componente requiere autorización; el uso posterior conserva el permiso persistente.

Antes de instalar paquetes, comprueba en la VM:

```bash
cat /etc/os-release
uname -r
command -v resolvconf
```

Si el perfil tiene DNS y resolvconf no está disponible, falta el soporte usado por wg-quick. Instala el proveedor apropiado para la distribución; no elimines DNS del perfil como solución automática.
