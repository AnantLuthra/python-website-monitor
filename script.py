import base64
import io
import requests
from rich import print
import smtplib
from dotenv import load_dotenv
import os
import time
from email.message import EmailMessage
import paramiko
import linode_api4
import schedule

load_dotenv()

EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASS")
RECIPIENT = os.getenv("RECIPIENT", EMAIL)
SSH_PRIVATE_KEY_B64 = os.getenv("SSH_PRIVATE_KEY_B64")
SSH_KEY_PASSPHRASE = os.getenv("SSH_KEY_PASSPHRASE")
LINODE_TOKEN = os.getenv("LINODE_TOKEN")
LINODE_HOST = os.getenv("LINODE_HOST")


def load_ssh_private_key():
    """Decode and load the SSH private key configured in the environment.

    Returns:
        paramiko.PKey: The decoded RSA, Ed25519, or ECDSA private key.

    Raises:
        RuntimeError: If the key is missing, invalid, or unsupported.
    """
    if not SSH_PRIVATE_KEY_B64:
        raise RuntimeError("SSH_PRIVATE_KEY_B64 is not set in the .env file")

    try:
        key_text = base64.b64decode(SSH_PRIVATE_KEY_B64).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as error:
        raise RuntimeError("SSH_PRIVATE_KEY_B64 is not valid base64") from error

    for key_type in (paramiko.RSAKey, paramiko.Ed25519Key, paramiko.ECDSAKey):
        try:
            return key_type.from_private_key(
                io.StringIO(key_text),
                password=SSH_KEY_PASSPHRASE,
            )
        except paramiko.SSHException:
            continue

    raise RuntimeError("SSH_PRIVATE_KEY_B64 does not contain a supported private key")


def send_email(EMAIL, PASSWORD, RECIPIENT, error, status_code=None):
    """Send an alert email describing a failed website check.

    Args:
        EMAIL: Gmail address used to send the alert.
        PASSWORD: Password or app password for the sender account.
        RECIPIENT: Email address that receives the alert.
        error: Error description to include in the message.
        status_code: Optional HTTP status code returned by the website.
    """
    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.starttls()
        smtp.login(EMAIL, PASSWORD)

        message = EmailMessage()
        message["Subject"] = "Website monitoring alert"
        message["From"] = EMAIL
        message["To"] = RECIPIENT

        message.set_content(
            f"Website is down.\nStatus code: {status_code}\nError: {error}"
        )

        smtp.send_message(message)
        print(f"[green]Alert email sent to {RECIPIENT}[/green]")


def restart_application(host):
    """Connect to the server over SSH and restarts the application.

    Args:
        host: Hostname or IP address of the server.
    """
    print("[green]Restarting Application![/green]")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(
        hostname=host,
        port=22,
        username="root",
        pkey=load_ssh_private_key(),
        # key_filename='/Users/username/.ssh/id_rsa'
    )

    stdin, stdout, stderr = ssh.exec_command("docker start nginx")
    print(f"Run command terminal output: {stdout.readlines()}")
    ssh.close()
    print("[green]Application Restarted![/green]")

def RestartServer_and_Container():
    """Reboot the Linode instance and start the Nginx container afterward.

    The function waits for the instance to report a running status before
    reconnecting over SSH and launching the container.
    """
    print("Rebooting the server ...")
    # restarting linode server
    client = linode_api4.LinodeClient(LINODE_TOKEN)

    nginx_server = client.load(linode_api4.Instance, 110712029)
    nginx_server.reboot()

    while True:
        nginx_server = client.load(linode_api4.Instance, 110712029)
        if nginx_server.status == "running":
            time.sleep(10)                   #buffer time for rebooting completeness
            break
        time.sleep(5)

    print(f"[green]Linode is running![/green]")

    # Restarting the application
    restart_application(LINODE_HOST)


def monitor_application():
    """Check the website and recover it when the health check fails.

    A non-200 response restarts the existing container. If the server cannot
    be reached, the function sends an alert and reboots the Linode instance.
    """
    try:
        response = requests.get(f"http://{LINODE_HOST}:8080/", timeout=10)

        if response.status_code == 200:
            print("[green]Website is running healthy![/green]")
        else:
            print("[red]Application down right now![/red]")
            send_email(EMAIL, PASSWORD, RECIPIENT, "Unexpected status code", response.status_code)

            # restarting the application
            restart_application(LINODE_HOST)

    except requests.RequestException as e:
        print(f"[red]Application unreachable: {e}[/red]")
        
        send_email(EMAIL, PASSWORD, RECIPIENT, str(e))
        RestartServer_and_Container()


schedule.every(5).seconds.do(monitor_application)

while True:
    schedule.run_pending()