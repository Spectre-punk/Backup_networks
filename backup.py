import os
import subprocess
from datetime import datetime
from netmiko import ConnectHandler

route_one = {
    "device_type": "cisco_ios",
    "host": "1.1.1.1",
    "username": "cisco",
    "password": "cisco",
    "secret": "cisco",
}
router_two = {
    "device_type": "cisco_ios",
    "host": "2.2.2.2",
    "username": "cisco",
    "password": "cisco",
    "secret": "cisco",
}
router_three = {
    "device_type": "cisco_ios",
    "host": "3.3.3.3",
    "username": "cisco",
    "password": "cisco",
    "secret": "cisco",
}
nodes = [route_one, router_two, router_three]


def sanitize_config(config_text):
    """Elimina marcas de tiempo dinámicas de Cisco para comparaciones precisas."""
    ignored_keywords = [
        "Last configuration change at",
        "NVRAM config last updated at",
        "Current configuration :",
    ]
    cleaned_lines = [
        line
        for line in config_text.splitlines()
        if not any(keyword in line for keyword in ignored_keywords)
    ]
    return "\n".join(cleaned_lines)


for node in nodes:
    host = node["host"]
    print(f"\n--- Procesando {host} ---")

    try:
        connection = ConnectHandler(**node)
        connection.enable()
        raw_output = connection.send_command("show running-config")
        connection.disconnect()
    except Exception as error:
        print(f"Error al conectar con {host}: {error}")
        continue

    # Carpeta por dispositivo
    device_folder = f"backups/{host}"
    os.makedirs(device_folder, exist_ok=True)

    # Identificar si ya existe un archivo previo
    archivos_existentes = sorted(
        [f for f in os.listdir(device_folder) if f.startswith("backup_")]
    )

    clean_current = sanitize_config(raw_output)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_backup_filename = f"backup_{timestamp}.txt"
    new_backup_path = os.path.join(device_folder, new_backup_filename)

    if archivos_existentes:
        # Tomar el archivo previo existente
        old_filename = archivos_existentes[-1]
        old_backup_path = os.path.join(device_folder, old_filename)

        with open(old_backup_path, "r") as f:
            clean_previous = sanitize_config(f.read())

        # Comparar las configuraciones limpias
        if clean_current == clean_previous:
            print(f"Sin cambios detectados en {host}. Conservando respaldo previo.")
            continue
        else:
            print(f"Cambios detectados en {host}. Reemplazando respaldo...")
            # Reemplazar: eliminar el archivo anterior y Git lo detecta
            os.remove(old_backup_path)
            subprocess.run(["git", "rm", old_backup_path], check=False)

    # Escribir el nuevo respaldo
    with open(new_backup_path, "w") as f:
        f.write(raw_output)

    # Subir a GitHub
    try:
        subprocess.run(["git", "add", device_folder], check=True)
        commit_message = f"Backup actualizado para {host} al {timestamp}"
        subprocess.run(["git", "commit", "-m", commit_message], check=True)
        subprocess.run(["git", "push"], check=True)
        print(f"Backup de {host} sincronizado exitosamente con GitHub.")
    except subprocess.CalledProcessError as git_err:
        print(f"Error al sincronizar con Git para {host}: {git_err}")