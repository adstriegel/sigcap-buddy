import logging
import shlex
import subprocess


def run_cmd(cmd, logging_prefix="Running command", log_result=True,
            timeout_s=None):
    logging.info("%s: %s.", logging_prefix, cmd)
    args = shlex.split(cmd)
    try:
        result = subprocess.check_output(
            args, timeout=timeout_s, stderr=subprocess.PIPE).decode("utf-8")
        if (log_result):
            logging.debug(result)
        return result
    except subprocess.CalledProcessError as e:
        logging.warning("%s error: %s\nOutput: %s", logging_prefix, e,
                        e.stderr.decode("utf-8"), exc_info=1)
        return ""
    except Exception as e:
        logging.warning("%s error: %s", logging_prefix, e, exc_info=1)
        return ""


def run_cmd_async(cmd, logging_prefix="Running async command"):
    # Sanitize command, only allow certain symbols if it's in "sleep 1;"
    sanitized = cmd.replace("sleep 1;", "")
    if (";" in sanitized
            or "|" in sanitized
            or ">" in sanitized
            or "&" in sanitized):
        raise Exception("Symbols not allowed in cmd!")

    logging.info("%s: %s.", logging_prefix, cmd)
    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True)


def resolve_cmd_async(proc, logging_prefix="Resolving async command",
                      log_result=True, timeout_s=None):
    try:
        out, err = proc.communicate(timeout=timeout_s)
        if (proc.returncode == 0):
            result = out.decode("utf-8")
            if (log_result):
                logging.debug(result)
            return result
        else:
            logging.warning("%s error:\n%s", logging_prefix,
                            err.decode("utf-8"))
            return ""
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
        logging.warning("%s error:\n%s", logging_prefix,
                        err.decode("utf-8"))
        return ""
    except Exception as e:
        logging.warning("%s error: %s", logging_prefix, e, exc_info=1)
        return ""
