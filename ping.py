from datetime import datetime
import jc
import logging
import re
import utils


def get_gateway_ip(iface):
    logging.info(f"Fetching gateway IP of {iface}.")
    re_gateway = re.compile(rf"default via (\d+\.\d+\.\d+\.\d+) dev {iface}")

    result = utils.run_cmd(
        "ip route",
        "Fetching gateway IP")

    re_results = re_gateway.findall(result)
    if (len(re_results) > 0):
        return re_results[0]
    else:
        return ""


def process_ping_results(results):
    parsed = jc.parse("ping", results)
    for entry in parsed["responses"]:
        entry["timestamp"] = datetime.fromtimestamp(
            entry["timestamp"]).astimezone().isoformat()

    return parsed


def ping(iface, ping_target, ping_count):
    gateway = get_gateway_ip(iface)
    if (not gateway):
        logging.warning("Cannot find gateway!")
        return

    logging.info("Running ping to target %s and gateway %s.",
                 ping_target, gateway)

    output = list()
    results = utils.run_cmd(
        f"ping {ping_target} -Dc {ping_count}",
        f"Running ping to {ping_target}")
    output.append(process_ping_results(results))
    results = utils.run_cmd(
        f"ping {gateway} -Dc {ping_count}",
        f"Running ping to {gateway}")
    output.append(process_ping_results(results))

    return output


def ping_async(iface, ping_target):
    gateway = get_gateway_ip(iface)
    if (not gateway):
        logging.warning("Cannot find gateway!")
        return

    logging.info("Running asynchronous ping to target %s and gateway %s.",
                 ping_target, gateway)
    # return utils.run_cmd_async(
    #     "date -Ins; sudo iw dev {} link; done".format(iface),
    #     "Continuouly get Wi-Fi link")


def resolve_ping_async(iface, extra):
    logging.info("Resolving ping.")
