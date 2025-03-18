import time
import paramiko
from .shell import Shell

class SSHShell(Shell):
    def __init__(self, hostname: str, port: int, username: str, keypath: str):
        self.text = ''

        self.ssh = paramiko.SSHClient()
        try:
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh.connect(hostname, port, username,pkey=paramiko.RSAKey.from_private_key_file(keypath))
            self.shell = self.ssh.invoke_shell()
        except Exception as e:
            self.ssh.close()

    def is_connect(self):
        if not self.ssh:
            return False
        transport = self.ssh.get_transport()
        if transport is not None and transport.is_active():
            return True
        return False

    def close(self):
        if self.ssh:
            self.ssh.close()

    def __del__(self):
        self.close()

    def exec(self, command: str):
        parsed_command = self.parse(command)
        self.shell.send(parsed_command.encode())  # type: ignore
        self.on_receive()

    def on_receive(self, size: int = 32 * 1024, encoding: str = "utf8"):
        time.sleep(1)
        output = ""
        while self.shell.recv_ready():  # type: ignore
            data = self.shell.recv(size).decode(encoding)  # type: ignore
            output += data
        self.text += output

    def get_output(self):
        if self.text.__len__() > 120*72:
            return self.text[120*72:]
        return self.text.replace('\r', '\\r').replace('\n', '\\n').replace('"', '\\"').replace("'", "\\'")