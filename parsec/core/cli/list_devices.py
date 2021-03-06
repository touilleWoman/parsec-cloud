import os
import click
from pathlib import Path

from parsec.core.config import get_default_config_dir
from parsec.core.devices_manager import list_available_devices


@click.command()
@click.option("--config-dir", type=click.Path(exists=True, file_okay=False))
def list_devices(config_dir):
    config_dir = Path(config_dir) if config_dir else get_default_config_dir(os.environ)
    devices = list_available_devices(config_dir)
    num_devices_display = click.style(str(len(devices)), fg="green")
    click.echo(f"Found {num_devices_display} device(s):")
    for org, device, cipher in devices:
        device_display = click.style(f"{org}:{device}", fg="yellow")
        click.echo(f"{device_display} (cipher: {cipher})")
