import re
from .shell import Shell
import time
import paramiko
from openai import OpenAI


class FakeShell(Shell):

    def __init__(self, hostname: str, port: int, username: str, keypath: str, api_key: str, base_url: str):

        self.ssh = paramiko.SSHClient()
        try:
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh.connect(hostname, port, username,
                             pkey=paramiko.RSAKey.from_private_key_file(keypath))
            self.shell = self.ssh.invoke_shell()
        except Exception as e:
            self.ssh.close()

        output = ""

        time.sleep(0.3)

        while self.shell.recv_ready():  # type: ignore
            time.sleep(0.5)
            data = self.shell.recv(1024 * 32).decode("utf8")  # type: ignore
            output += data

        ansi_escape = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')
        output = ansi_escape.sub('', output)

        self.text = output

        self.shell_start = output.split("\r\n")[-1]
        self.clinet = OpenAI(api_key=api_key, base_url=base_url)
        self.ssh.close()

    def is_connect(self):
        return True

    def close(self):
        pass

    def __del__(self):
        self.close()

    def exec(self, command: str):

        parsed_command = self.parse(command)

        try:
            completions = self.clinet.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "你是一台debian服务器, 尽可能用纯文本模拟用户执行命令的结果，如果用户的操作会带来重大损失，直接辱骂对方",
                    },
                    {
                        "role": "user",
                        "content": parsed_command,
                    }
                ],
                model="gpt-3.5-turbo",
            )
            output = completions.choices[0].message.content
        except:
            output = "我在休息，快滚，现在不响应指令"

        if output is not None:
            output = output.replace('\\r', '\r').replace('\\n', '\n')

        self.text += f'{parsed_command}\r\n{output}\r\n{self.shell_start}'

    def get_output(self):
        if self.text.__len__() > 120*72:
            return self.text[120*72:]
        return self.text.replace('\r', '\\r').replace('\n', '\\n').replace('"', '\\"').replace("'", "\\'")
