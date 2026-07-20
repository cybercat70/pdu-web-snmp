#!/usr/bin/env python3

from flask import Flask, render_template, jsonify, request
import yaml
import subprocess
from vault import get_vault_credentials

app = Flask(__name__)

CONFIG_PATH = "/etc/pdu-web-snmp/pdu_devices.yaml"
MAX_OUTLETS = 16

creds = get_vault_credentials()


def load_config():
  '''
  Loads the outlet configuration from the YAML file.

  Parameters
  ----------
  None

  Returns
  -------
  set[int]
    A set containing outlet IDs that are allowed to be controlled.

  Any file access or YAML parsing error propagates to the caller.
  '''

  with open(CONFIG_PATH,"r") as config_file:
    data = yaml.safe_load(config_file)
  return set(data.values())


def get_outlets_status(oid):
  '''
  Queries the PDU via SNMP and returns values for the specified OID.

  Parameters
  ----------
  oid : str
    SNMP object identifier to retrieve.

  Returns
  -------
  list[str]
    A list containing one value for each returned SNMP object.

  Any SNMP command failure raises subprocess.CalledProcessError.
  '''

  snmp_query_base = [
    "snmpwalk",
    "-v3",
    "-Oqv",
    "-l", "authNoPriv",
    "-u", creds["snmp_user"],
    "-a", "MD5",
    "-A", creds["snmp_password"],
    creds["pdu_host"],
  ]

  snmp_query = snmp_query_base + [oid]

  result = subprocess.run(
    snmp_query,
    capture_output=True,
    text=True,
    check=True,
  )

  return result.stdout.splitlines()


def get_pdu_status():
  '''
  Retrieves the current status of all PDU outlets.

  Parameters
  ----------
  None

  Returns
  -------
  list[dict]
    A list of dictionaries describing each outlet. Every dictionary
    contains the following keys:

    - id (int)
    - name (str)
    - state (str)
    - controllable (bool)

  Any configuration or SNMP error propagates to the caller.
  '''

  allowed_outlets = load_config()

  outlets = []

  oid = "PowerNet-MIB::rPDUOutletControlOutletName"
  outlet_names = get_outlets_status(oid)

  oid = "PowerNet-MIB::rPDUOutletStatusOutletState"
  outlet_states = get_outlets_status(oid)

  outlet_index = 1

  for outlet_name in outlet_names:
    outlets.append(
      {
        "id": outlet_index,
        "name": outlet_name.strip('"'),
        "state": outlet_states[outlet_index - 1].replace("outletStatus", "").upper(),
        "controllable": outlet_index in allowed_outlets
      }
    )
    outlet_index += 1

  return outlets


def outlets_management(outlet_id, action):
  '''
  Changes the power state of the specified outlet.

  Parameters
  ----------
  outlet_id : int
    Index number of the PDU outlet to control.
  action : str

  Returns
  -------
  list[str]
    The SNMP command output split into individual lines.

  Raises
  ------
  ValueError
    If the requested action is not supported.

  subprocess.CalledProcessError
    If the SNMP command fails.
  '''

  commands = {
    "on": "1",
    "off": "2",
  }

  try:
    op_code = commands[action]
  except KeyError:
    raise ValueError("Invalid action")

  snmp_query = [
    "snmpset",
    "-v3",
    "-l", "authNoPriv",
    "-u", creds["snmp_user"],
    "-a", "MD5",
    "-A", creds["snmp_password"],
    creds["pdu_host"],
    f"PowerNet-MIB::rPDUOutletControlOutletCommand.{outlet_id}",
    "i",
    op_code,
  ]

  result = subprocess.run(
    snmp_query,
    capture_output=True,
    text=True,
    check=True,
  )

  return result.stdout.splitlines()


@app.route("/")
def index():
  '''
  Serves the main web interface.

  Returns
  -------
  Response
    The rendered rack.html template.
  '''

  return render_template("rack.html")


@app.route("/status")
def status():
  '''
  Returns the current PDU outlet status.

  Returns
  -------
  Response
    A JSON response containing the status of all outlets or an error
    message if the SNMP query fails.
  '''

  try:
    pdu_status = get_pdu_status()
    return jsonify(pdu_status)
  except:
    return jsonify({"error": "snmp operation fails"}), 503


@app.route("/control", methods=["POST"])
def control():
  '''
  Handles outlet power control requests.

  The request body must contain a JSON object with the outlet ID and
  the requested action.

  Returns
  -------
  Response
    A JSON response indicating whether the operation succeeded or
    describing the validation or SNMP error.
  '''

  data = request.get_json()

  if not data:
    return jsonify({"error": "empty request"}), 400

  outlet_id = data["id"]
  action = data["action"]

  if not isinstance(outlet_id, int):
    return jsonify({"error": "outlet id must be integer"}), 400

  if outlet_id < 1 or outlet_id > MAX_OUTLETS:
    return jsonify({"error": "outlet id must be between 1 and 16"}), 400

  if action not in ("on", "off"):
    return jsonify({"error": "invalid action"}), 400

  allowed_outlets = load_config()

  if outlet_id not in allowed_outlets:
    return jsonify({"error": "outlet control forbidden"}), 403

  try:
    outlets_management(outlet_id, action)
  except subprocess.CalledProcessError as e:
    return jsonify({
      "error": "SNMP command failed",
      "details": e.stderr
    }), 502

  return jsonify({
    "ok": True,
    "id": outlet_id,
    "state": action.upper(),
  })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
