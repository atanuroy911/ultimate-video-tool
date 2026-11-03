# Ultimate Video Tool Server

The processing product lives here: Python API/pipeline in `vt/`, processing assets in `assets/` and `design/`, the headless render worker in `renderer/`, the native management window in `desktop/`, and headless installation resources in `packaging/`.

The server does not contain or serve the video editor. Its browser landing page and native window manage the processing server, client approval, engines and model locations. Editing is done by the separately installed client.

From the repository root:

```powershell
./scripts/dev-install.ps1 -Role server
```

```sh
bash scripts/dev-install.sh --role server
```

The development scripts isolate data and environments from production installs. They default to CPU Python dependencies; existing ComfyUI/Ollama can continue using their GPUs. Source updates use Git fast-forward only and preserve local changes. Model/engine installation remains an explicit server-management action.

Build the native server installer with `npm --prefix server/desktop run dist`. Build a headless processing archive with `python scripts/make_engine_package.py --full`. Neither build reads `client/`.
