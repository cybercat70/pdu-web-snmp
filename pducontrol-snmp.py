#!/usr/bin/env python3

from flask import Flask, render_template, jsonify, request
import yaml
import subprocess
from vault import get_vault_credentials

app = Flask(__name__)

CONFIG_PATH = "/etc/pdu-web-snmp/pdu_devices.yaml"

creds = get_vault_credentials()


def load_config():
  with open(CONFIG_PATH,"r") as config_file:
    data = yaml.safe_load(config_file)
  return set(data.values())


def get_outlets_status(oid):
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
  ALLOWED_OUTLETS = load_config()

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
        "controllable": outlet_index in ALLOWED_OUTLETS
      }
    )
    outlet_index += 1

  return outlets


def outlets_management(outlet_id, action):
  match action:
    case "on":
      op_code = "1"
    case "off":
      op_code = "2"

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
  return render_template("rack.html")


@app.route("/status")
def status():
  return jsonify(get_pdu_status())


@app.route("/control", methods=["POST"])
def control():
  data = request.json
  outlet_id = data["id"]
  action = data["action"]
  outlets_management(outlet_id, action)

  return jsonify({
    "ok": True,
    "id": outlet_id,
    "state": action.upper(),
  })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
