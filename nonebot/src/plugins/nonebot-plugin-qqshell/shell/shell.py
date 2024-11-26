from abc import abstractmethod


class Shell:
    @abstractmethod
    def is_connect(self):
        pass

    @abstractmethod
    def close(self):
        pass

    def __del__(self):
        self.close()

    @abstractmethod
    def exec(self, command: str):
        pass

    @abstractmethod
    def get_output(self):
        pass

    @staticmethod
    def parse(command: str):
        map_dict = {
            "#esc": "\x1b",
            "#ctrlc": "\x03",
            "#ctrld": "\x04",
            "#ctrlz": "\x1a",
            "#ctrll": "\x0c",
            "#enter": "\r"
        }

        for key, value in map_dict.items():
            command = command.replace(key, value)

        if command.endswith("#direct"):
            command = command[:-7]
        else:
            command = f'{command}\r'

        return command
