#!/usr/bin/env python3
'''Retrieves credentials from HashiCorp Vault using AppRole authentication.'''

import sys
import os
import hvac


def get_vault_credentials():
  '''
  Returns the Vault-stored secrets for the PDU SNMPv3 management.

  Parameters
  ----------
  None

  Returns
  -------
  A dict with named credentials.

  Any Vault or .env file problem terminates the process.
  '''

  conf_vars = {}

  for var in ("VAULT_ADDR", "CA_CERT", "VAULT_ROLE", "ID"):
    var_value = os.getenv(var)

    if not var_value:
      print (f"[Fatal] {var} not set in .env, exiting.")
      sys.exit(1)

    conf_vars[var] = var_value

  client = hvac.Client(url=conf_vars["VAULT_ADDR"], verify = conf_vars["CA_CERT"])

  if client.sys.is_sealed():
    print(f"[Fatal] Vault is sealed, unseal it first.")
    sys.exit(1)

  ''' AppRole auth '''
  try:
    client.auth.approle.login(role_id = conf_vars["VAULT_ROLE"], secret_id = conf_vars["ID"])

  except hvac.exceptions.InvalidRequest:
    print(f"[Fatal] Invalid or expired Secret ID!")
    sys.exit(1)

  except hvac.exceptions.Forbidden:
    print(f"[Fatal] Role is not allowed to authenticate.")
    sys.exit(1)

  except hvac.exceptions.VaultDown:
    print(f"[Fatal] Vault is unavailable.")
    sys.exit(1)

  ''' Check if we authenticated '''
  if not client.is_authenticated():
    print (f"[Fatal] Vault authentication failed.")
    sys.exit(1)

  ''' For KV v2 mount_point is mandatory '''
  secret = client.secrets.kv.v2.read_secret_version(path="pdu-web", mount_point="lab", raise_on_deleted_version=True)
  data = secret["data"]["data"]
  pdu_host = data["host"]
  snmp_user = data["snmp_user"]
  snmp_password = data["snmp_password"]

  return {
    "pdu_host": pdu_host,
    "snmp_user": snmp_user, 
    "snmp_password": snmp_password,
  }
