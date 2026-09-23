"""Consulta routers Cisco y genera tablas de interfaces y subredes.

El script obtiene las IP configuradas desde el running-config, consulta el
estado operativo de cada interfaz y presenta los resultados con Rich.
"""

from netmiko import ConnectHandler
from ipaddress import IPv4Network
from rich.console import Console
from rich.table import Table

# Datos de conexión de los routers que se van a consultar.
route_one = {
        "device_type": "cisco_ios",
        "host": "1.1.1.1",
        "username": "cisco",
        "password": "cisco",
        }
router_two = {
        "device_type": "cisco_ios",
        "host": "2.2.2.2",
        "username": "cisco",
        "password": "cisco",
        }
router_three = {
        "device_type": "cisco_ios",
        "host": "3.3.3.3",
        "username": "cisco",
        "password": "cisco",
        }
nodes = [route_one, router_two, router_three]
console = Console()
router_outputs = []


def get_interface_addresses(output):
    """Extrae interfaz, IP y máscara de las secciones del running-config."""
    addresses = []
    current_interface = None

    for line in output.splitlines():
        line_parts = line.strip().split()

        # Una nueva sección comienza con el comando "interface".
        if line.startswith("interface "):
            current_interface = line_parts[1]

        # Las líneas "ip address" pertenecen a la interfaz actual.
        elif current_interface and line_parts[:2] == ["ip", "address"]:
            if len(line_parts) >= 4 and line_parts[2] != "dhcp":
                addresses.append(
                    (current_interface, line_parts[2], line_parts[3])
                )

    return addresses


def get_interface_statuses(output):
    """Crea un mapa interfaz -> estado usando la salida de TextFSM."""
    return {
        interface["interface"]: interface.get("status", "unknown").lower()
        for interface in output
    }


def get_usable_addresses(network):
    """Devuelve el número de direcciones utilizables de una red IPv4."""
    # /31 y /32 tienen reglas especiales para redes punto a punto y hosts.
    if network.prefixlen == 32:
        return 1
    if network.prefixlen == 31:
        return 2
    return network.num_addresses - 2


# Consulta cada router y conserva sus direcciones y estados por separado.
for router_number, node in enumerate(nodes, start=1):
    router_id = f"R{router_number}"
    host = node["host"]
    console.print(f"Connecting to {router_id} ({host})")
    try:
        net_connect = ConnectHandler(**node)
        net_connect.enable()

        # El running-config contiene la IP y la máscara exacta configurada.
        output = net_connect.send_command("show running-config")

        # TextFSM convierte la salida en registros para consultar el estado.
        status_output = net_connect.send_command(
            "show ip interface brief", use_textfsm=True
        )
        router_outputs.append(
            (
                router_id,
                get_interface_addresses(output),
                get_interface_statuses(status_output),
            )
        )
        net_connect.disconnect()
    except Exception as e:
        console.print(f"[red]Failed to connect to {router_id} ({host}): {e}[/red]")

# Primera tabla: todas las interfaces con una IP configurada.
table = Table(title="Router Interfaces")
table.add_column("Router", style="cyan", no_wrap=True)
table.add_column("Interface", style="green")
table.add_column("IP Address", style="yellow")
table.add_column("Mask", style="magenta")

subnet_inventory = {}
warnings = []

# Agrupa las interfaces por red y detecta interfaces configuradas pero caídas.
for router_id, addresses, statuses in router_outputs:
    for interface_name, ip_address, mask in addresses:
        table.add_row(router_id, interface_name, ip_address, mask)

        # strict=False calcula la red aunque la IP no sea la dirección de red.
        network = IPv4Network(f"{ip_address}/{mask}", strict=False)
        subnet = subnet_inventory.setdefault(
            network,
            {"addresses": set(), "interfaces": []},
        )
        subnet["addresses"].add(ip_address)
        subnet["interfaces"].append(f"{router_id}:{interface_name}")

        status = statuses.get(interface_name, "unknown")
        if status in {"administratively down", "down"}:
            warnings.append((router_id, interface_name, ip_address, status))

console.print(table)

# Segunda tabla: capacidad y utilización de cada segmento encontrado.
inventory_table = Table(title="Subnet Inventory")
inventory_table.add_column("Network", style="cyan")
inventory_table.add_column("Mask", style="magenta")
inventory_table.add_column("Usable", justify="right")
inventory_table.add_column("Assigned", justify="right")
inventory_table.add_column("Free", style="green", justify="right")
inventory_table.add_column("Interfaces", style="yellow")

for network, subnet in sorted(subnet_inventory.items(), key=lambda item: int(item[0].network_address)):
    usable_addresses = get_usable_addresses(network)
    assigned_addresses = len(subnet["addresses"])

    # Las direcciones libres son las utilizables que aún no están asignadas.
    inventory_table.add_row(
        str(network.network_address),
        str(network.netmask),
        str(usable_addresses),
        str(assigned_addresses),
        str(max(usable_addresses - assigned_addresses, 0)),
        ", ".join(subnet["interfaces"]),
    )

console.print(inventory_table)

# Tercera salida: advertencias para interfaces con IP pero sin servicio.
if warnings:
    warning_table = Table(title="Interface Warnings")
    warning_table.add_column("Router", style="cyan")
    warning_table.add_column("Interface", style="yellow")
    warning_table.add_column("IP Address", style="magenta")
    warning_table.add_column("Status", style="red")

    for warning in warnings:
        warning_table.add_row(*warning)

    console.print(warning_table)
else:
    console.print("[green]No configured interfaces are down.[/green]")