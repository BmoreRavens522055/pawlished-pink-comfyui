"""Standard JupyterLab, RunPod-supplied token, same-origin browser security."""

import os

c = get_config()  # noqa: F821 -- provided by Jupyter
c.ServerApp.ip = "0.0.0.0"
c.ServerApp.port = int(os.environ.get("PP_JUPYTER_PORT", "8888"))
c.ServerApp.port_retries = 0
c.ServerApp.open_browser = False
c.ServerApp.allow_root = True
c.ServerApp.root_dir = os.environ.get("PP_WORKSPACE", "/workspace")
c.ServerApp.default_url = "/lab"
c.ServerApp.allow_remote_access = True
c.ServerApp.trust_xheaders = True
c.ServerApp.allow_origin = ""
c.ServerApp.disable_check_xsrf = False
c.IdentityProvider.token = os.environ["JUPYTER_PASSWORD"]
c.ServerApp.terminado_settings = {"shell_command": ["/bin/bash"]}
c.FileContentsManager.delete_to_trash = False
# Uploads, terminals and notebooks do not need probing arbitrary host language servers.
c.LanguageServerManager.autodetect = False
