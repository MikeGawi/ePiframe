import atexit
import os
import signal
import sys
import time


class Daemon:
    # Based on a generic daemon class.
    # https://www.jejik.com/articles/2007/02/a_simple_unix_linux_daemon_in_python/
    # Usage: subclass the daemon class and override the run() method.

    def __init__(self, pid_file: str, path: str):
        self.pid_file = pid_file
        self.path = path

    def daemonize(self, debug: bool):
        try:
            pid = os.fork()
            if pid > 0:
                # exit first parent
                sys.exit(0)
        except OSError as error:
            sys.stderr.write(f"fork #1 failed: {error}\n")
            sys.exit(1)

        # decouple from parent environment
        os.chdir(self.path)
        os.setsid()
        os.umask(0)

        # do second fork
        try:
            pid = os.fork()
            if pid > 0:
                # exit from second parent
                sys.exit(0)
        except OSError as error:
            sys.stderr.write(f"fork #2 failed: {error}\n")
            sys.exit(1)

        if not debug:
            # redirect standard file descriptors
            sys.stdout.flush()
            sys.stderr.flush()
            signal_input = open(os.devnull, "r")
            signal_output = open(os.devnull, "a+")
            signal_error = open(os.devnull, "a+")

            os.dup2(signal_input.fileno(), sys.stdin.fileno())
            os.dup2(signal_output.fileno(), sys.stdout.fileno())
            os.dup2(signal_error.fileno(), sys.stderr.fileno())

        # write pidfile
        atexit.register(self.delete_pid)

        pid = str(os.getpid())
        with open(self.pid_file, "w+") as file_pid:
            file_pid.write(pid + "\n")

    def delete_pid(self):
        os.remove(self.pid_file)

    def start(self, args: str = None, debug: bool = False):
        # Start the daemon
        self.daemonize(debug)
        self.run(args)

    def stop(self):
        # Get the pid from the pidfile
        try:
            with open(self.pid_file, "r") as file_pid:
                pid = int(file_pid.read().strip())
        except IOError:
            pid = None

        if not pid:
            message = "pidfile {0} does not exist. " + "Daemon not running?\n"
            sys.stderr.write(message.format(self.pid_file))
            return  # not an error in a restart

        # Try killing the daemon process
        try:
            while 1:
                os.kill(pid, signal.SIGTERM)
                time.sleep(0.1)
        except OSError as error:
            exception = str(error.args)
            if exception.find("No such process") > 0:
                if os.path.exists(self.pid_file):
                    os.remove(self.pid_file)
            else:
                print(str(error.args))
                sys.exit(1)

    def restart(self):
        self.stop()
        self.start()

    # You should override this method when you subclass Daemon.
    # It will be called after the process has been daemonized by
    # start() or restart().
    def run(self, args: str = None):
        pass
