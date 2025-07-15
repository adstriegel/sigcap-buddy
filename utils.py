import logging
import os
import subprocess
import signal


def hex_to_bssid(input_string):
    input_len = len(input_string)
    if (input_len != 12):
        logging.warning(f"{input_string} is possibly not a BSSID")
    return ":".join(input_string[i:i+2] for i in range(0, input_len, 2)).upper()


def freq_str_to_mhz(freq_str):
    number, unit = freq_str.split(' ')
    if (unit.lower() == 'ghz'):
        return int(float(number) * 1e3)
    elif (unit.lower() == 'mhz'):
        return int(float(number))
    elif (unit.lower() == 'khz'):
        return int(float(number) / 1e3)
    elif (unit.lower() == 'hz'):
        return int(float(number) / 1e6)
    else:
        logging.warning(f"Unknown unit {unit} !")
        return 0


def freq_str_cmp(freq_str, cmp_str):
    freq = freq_str_to_mhz(freq_str)
    if (cmp_str == "2.4ghz"):
        return freq < 2500
    elif (cmp_str == "5ghz"):
        return freq > 5160 and freq < 5925
    elif (cmp_str == "6ghz"):
        return freq > 5925
    else:
        logging.warning(f"Unknown comparison string {cmp_str} !")
        return False


def sanitize(cmd):
    # Sanitize command, only allow certain symbols if it's in "sleep 1;"
    # TODO: also replace "sleep n;"
    sanitized = cmd.replace("sleep 1;", "")
    sanitized = sanitized.replace("while true; do", "")
    sanitized = sanitized.replace("date -Ins;", "")
    sanitized = sanitized.replace("; done", "")
    sanitized = sanitized.replace("git fetch &&", "")
    sanitized = sanitized.replace(
        ("wget -q -O - https://raw.githubusercontent.com/adstriegel/"
         "sigcap-buddy/main/pi-setup.sh | "),
        "")
    if (" ;" in sanitized
            or " |" in sanitized
            or " >" in sanitized
            or " <" in sanitized
            or " &" in sanitized
            or "; " in sanitized
            or "| " in sanitized
            or "> " in sanitized
            or "< " in sanitized
            or "& " in sanitized):
        logging.error("Unaccepted symbols on command: %s", cmd)
        raise Exception("Symbols not allowed in cmd!")


def run_cmd(cmd, logging_prefix="Running command", log_result=True,
            timeout_s=None, raw_out=False):
    sanitize(cmd)
    logging.info("%s: %s.", logging_prefix, cmd)

    try:
        result = subprocess.run(
            cmd,
            timeout=timeout_s,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True)
        if (raw_out):
            return {
                "returncode": result.returncode,
                "stdout": result.stdout.decode("utf-8"),
                "stderr": result.stderr.decode("utf-8")
            }
        elif (result.returncode == 0 or not result.stderr):
            output = result.stdout.decode("utf-8")
            if (log_result):
                logging.debug(output)
            return output
        else:
            logging.warning("%s error:\n%s", logging_prefix,
                            result.stderr.decode("utf-8"))
            return ""
    except subprocess.TimeoutExpired as e:
        logging.warning("%s error: %s", logging_prefix, e)
        if (raw_out):
            return {
                "returncode": 1,
                "stdout": "",
                "stderr": str(e)
            }
        else:
            return ""
    except Exception as e:
        logging.warning("%s error: %s", logging_prefix, e, exc_info=1)
        if (raw_out):
            return {
                "returncode": 1,
                "stdout": "",
                "stderr": str(e)
            }
        else:
            return ""


def run_cmd_async(cmd, logging_prefix="Running async command"):
    sanitize(cmd)

    logging.info("%s: %s.", logging_prefix, cmd)
    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=os.setsid,
        shell=True)


def resolve_cmd_async(proc, logging_prefix="Resolving async command",
                      log_result=True, timeout_s=None, kill=False,
                      raw_out=False):
    logging.info("%s.", logging_prefix)
    try:
        if kill:
            os.killpg(os.getpgid(proc.pid), signal.SIGINT)
            logging.debug("Process terminated.")

        out, err = proc.communicate(timeout=timeout_s)
        if (raw_out):
            return {
                "returncode": proc.returncode,
                "stdout": out.decode("utf-8"),
                "stderr": err.decode("utf-8")
            }
        elif (proc.returncode == 0 or (kill and not err)):
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
        if (raw_out):
            return {
                "returncode": 1,
                "stdout": "",
                "stderr": str(e)
            }
        else:
            return ""
    except Exception as e:
        logging.warning("%s error: %s", logging_prefix, e, exc_info=1)
        if (raw_out):
            return {
                "returncode": 1,
                "stdout": "",
                "stderr": str(e)
            }
        else:
            return ""
