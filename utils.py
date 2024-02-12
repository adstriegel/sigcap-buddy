import logging
import subprocess


def sanitize(cmd):
    # Sanitize command, only allow certain symbols if it's in "sleep 1;"
    # TODO: also replace "sleep n;"
    sanitized = cmd.replace("sleep 1;", "")
    sanitized = sanitized.replace("while true; do", "")
    sanitized = sanitized.replace("date -Ins;", "")
    sanitized = sanitized.replace("; done", "")
    if (";" in sanitized
            or "|" in sanitized
            or ">" in sanitized
            or "&" in sanitized):
        raise Exception("Symbols not allowed in cmd!")


def run_cmd(cmd, logging_prefix="Running command", log_result=True,
            timeout_s=None):
    sanitize(cmd)
    logging.info("%s: %s.", logging_prefix, cmd)
    result = subprocess.run(
        cmd,
        timeout=timeout_s,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True)
    if (result.returncode == 0 or not result.stderr):
        output = result.stdout.decode("utf-8")
        if (log_result):
            logging.debug(output)
        return output
    else:
        logging.warning("%s error:\n%s", logging_prefix,
                        result.stderr.decode("utf-8"))
        return ""


def run_cmd_async(cmd, logging_prefix="Running async command"):
    sanitize(cmd)

    logging.info("%s: %s.", logging_prefix, cmd)
    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True)


def resolve_cmd_async(proc, logging_prefix="Resolving async command",
                      log_result=True, timeout_s=None, kill=False):
    try:
        if kill:
            proc.kill()
        out, err = proc.communicate(timeout=timeout_s)
        if (proc.returncode == 0 or (kill and not err)):
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
