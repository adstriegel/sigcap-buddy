import logging
import shlex
import subprocess


def run_cmd(cmd, logging_prefix="Running command", log_result=True,
            timeout_s=None):
    logging.info("%s: %s.", logging_prefix, cmd)
    args = shlex.split(cmd)
    try:
        result = subprocess.check_output(
            args, timeout=timeout_s).decode("utf-8")
        if (log_result):
            logging.debug(result)
        return result
    except subprocess.CalledProcessError as e:
        logging.warning("%s error: %s\n%s", logging_prefix, e,
                        e.output, exc_info=1)
        return ""
