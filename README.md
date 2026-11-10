# Website Monitoring and Recovery

A Python script that monitors an Nginx website running on a Linode instance.
When the health check fails, it sends an email alert and attempts to recover
the application over SSH. If the server cannot be reached, it reboots the
Linode instance and waits for it to become available again.

## Features

- Checks the website on a configurable schedule. It currently runs every five
  seconds for testing; production deployments should use an interval of
  fifteen minutes or more, depending on application needs.
- Sends email alerts for unreachable websites or unexpected HTTP status codes.
- Starts the existing Nginx Docker container over SSH when the website is
  unhealthy.
- Reboots the Linode instance when the server cannot be reached.
- Supports SSH authentication with a base64-encoded private-key value stored
  in `.env`.
- Includes an optional commented `key_filename` configuration for users who
  already have an `id_rsa` file in their `.ssh` directory.

## Requirements

- Python 3.10+
- A running Linode instance with SSH access for the configured user.
- Docker installed on the Linode instance.
- An Nginx container running on port `8080`.
- A Gmail account with an app password if two-factor authentication is enabled.
- A Linode personal access token with permission to reboot the instance.

## Linode and Docker setup

Create or use a Linode instance and install Docker on it. Then start the
Nginx container with:

```bash
docker run -d --name nginx -p 8080:80 nginx
```

The monitored application must be reachable through the Linode instance on
port `8080`. The script connects over SSH as `root` by default, so ensure SSH
access and the selected private key are configured correctly.

### Configure the Linode instance ID

The Linode instance ID is currently hard-coded in
`RestartServer_and_Container()`:

```python
nginx_server = client.load(linode_api4.Instance, 110712029)
```

Replace `110712029` with the ID of your own Linode instance. The instance ID
is different from the public IP address configured in `LINODE_HOST`.

## Installation

Create and activate a virtual environment:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
```

Install the dependencies:

```powershell
pip install requests rich python-dotenv paramiko linode-api4 schedule
```

## Configuration

Create a `.env` file in the project directory. Never commit this file.

```env
EMAIL=sender@example.com
PASS=your_gmail_app_password
RECIPIENT=recipient@example.com

LINODE_TOKEN=your_linode_api_token
LINODE_HOST=203.0.113.10

# Private key value, encoded as one base64 line.
SSH_PRIVATE_KEY_B64=your_base64_encoded_private_key
SSH_KEY_PASSPHRASE=
```

### Base64 private-key configuration

If the private key is stored in WSL, encode it there:

```bash
base64 -w 0 ~/.ssh/id_rsa
```

Copy the result into `SSH_PRIVATE_KEY_B64`. If the key is not
passphrase-protected, leave `SSH_KEY_PASSPHRASE` empty.

### Using an existing `id_rsa` file

If your private key already exists in your `.ssh` directory and you want
Paramiko to read it directly, update the `ssh.connect()` call in
`restart_application()`:

1. Comment out the active `pkey` argument:

   ```python
   # pkey=load_ssh_private_key(),
   ```

2. Uncomment the `key_filename` argument and replace the example path with
   your actual key path:

   ```python
   key_filename="C:\\Users\\your-name\\.ssh\\id_rsa",
   ```

   On Linux or WSL, use a path such as:

   ```python
   key_filename="/home/your-name/.ssh/id_rsa",
   ```

Use only one authentication option at a time: either `pkey` or
`key_filename`. If `key_filename` is used, the private key does not need to be
copied into `.env`.

## Running

```powershell
python script.py
```

The script runs continuously. The current five-second interval is intended for
testing and demonstration. For production, change the schedule to fifteen
minutes or another interval appropriate for the application:

```python
schedule.every(15).minutes.do(monitor_application)
```

Stop the script with `Ctrl+C`.

## Security notes

- Add `.env` to `.gitignore`.
- Never commit private keys, base64-encoded keys, passwords, or API tokens.
- Use a Gmail app password rather than your normal Gmail password.
- Prefer a dedicated, least-privileged SSH user instead of `root` where possible.
- `AutoAddPolicy` accepts unknown SSH host keys automatically. For production
  use, verify and manage the server host key explicitly.

## Current limitations

- The Linode instance ID is currently hard-coded in `script.py`.
- The SSH username and monitored port are currently hard-coded.
- A normal Linode reboot usually keeps the same public IP; the configured
  `LINODE_HOST` is therefore reused after recovery.
