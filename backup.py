"""
Crear un script en Python que utilice Netmiko para conectarse a cada uno de
los routers y extraer la configuración con el comando:
o show running-config
2. Automatizar la toma de backups:
o Generar un archivo .txt por cada backup, incluyendo en el nombre del
archivo la fecha y hora del respaldo.
o Guardar cada backup en una carpeta separada por nombre del
dispositivo.
3. Comparar configuraciones:
o Si el nuevo backup es diferente al anterior, reemplazar el archivo.
o Si no hay cambios, conservar el archivo previo sin hacer modificaciones.
4. Integración con GitHub:
o Automatizar el proceso para que, cada vez que se guarde un backup
nuevo, se suba al repositorio en GitHub.
o Incluir en el commit message la fecha y hora del backup.

"""
from netmiko import ConnectHandler
import os
from datetime import datetime
import subprocess

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

for node in nodes:
    # Conexión al router
    connection = ConnectHandler(**node)
    output = connection.send_command("show running-config")
    connection.disconnect()

    # Crear carpeta para el dispositivo si no existe
    device_folder = f"backups/{node['host']}"
    os.makedirs(device_folder, exist_ok=True)

    # Nombre del archivo con fecha y hora
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"{device_folder}/backup_{timestamp}.txt"

    # Guardar el backup en un archivo temporal
    with open(backup_file, "w") as f:
        f.write(output)

    # Verificar si hay un backup previo
    previous_backups = sorted(
        [f for f in os.listdir(device_folder) if f.startswith("backup_")],
        reverse=True,
    )

    if len(previous_backups) > 1:
        previous_backup_file = os.path.join(device_folder, previous_backups[1])
        with open(previous_backup_file, "r") as f:
            previous_output = f.read()

        # Comparar configuraciones
        if output == previous_output:
            print(f"No changes detected for {node['host']}. Keeping previous backup.")
            os.remove(backup_file)  # Eliminar el nuevo backup si no hay cambios
        else:
            print(f"Changes detected for {node['host']}. Backup updated.")
            # sube el nuevo backup a GitHub
            subprocess.run(["git", "add", backup_file])
            commit_message = f"Backup for {node['host']} at {timestamp}"
            subprocess.run(["git", "commit", "-m", commit_message])
            subprocess.run(["git", "push"])
