VIDEO TOOL ENGINE
=================

This is the server half of Video Tool. Put it on the computer that has the graphics card. It
downloads and sets up Ollama (the language AI), ComfyUI (pictures and short clips) and their
models, and offers them to the Video Tool window on any other computer: one address, one code.

If the window and the engine are on the SAME computer you do not need this package. Install
"Video Tool" (the app); its first-run setup does the same job on its own computer.

WINDOWS
    Right-click install-engine.ps1, Run with PowerShell   (or:  powershell -ExecutionPolicy Bypass -File .\install-engine.ps1)
    Add -Service to start the engine at every login.

LINUX / MAC
    ./install-engine.sh            (add --service to start it at boot / login)

DOCKER (Linux with an NVIDIA card and the NVIDIA container toolkit)
    docker compose up -d
    docker compose logs engine      # shows the address and the pairing code

WHAT IT DOWNLOADS (about 30 GB with the picture models; 70 GB with short clips)
    uv + Python 3.11 + the packages, then Ollama and a small language model, ComfyUI with its
    own Python and the right PyTorch for your card, and the picture models. Stop it any time and
    run it again: downloads resume and are checked against pinned checksums.

CONNECT THE WINDOW TO IT
    1. Start the engine. It prints, for example:
         Address: http://192.168.1.20:8790
         Pairing code (works once): a1b2-c3d4-e5f6
    2. On the other computer open Video Tool: Settings, Engines, "Another Video Tool computer".
       Type the address and the code. Language AI and Pictures connect through it as well.
    3. Another code later:  vt engine pair   (run on this computer while the engine runs)

FIREWALL
    The first time the engine starts, Windows asks whether to allow it on the network: allow it on private networks. On Linux open the one port (for example: sudo ufw allow 8790/tcp).

SECURITY
    Ollama and ComfyUI stay on 127.0.0.1 of this computer. Only the engine's port (8790) is
    open, and everything behind it needs the key that pairing hands out. The traffic is not
    encrypted: use it on your own network, or put a tunnel or VPN (Tailscale, Cloudflare Tunnel,
    WireGuard) in front of it for the internet. A lost key: `vt engine` data folder, delete
    engine-hub.json, restart, pair again.

FILES
    data folder   the key, settings, models, ComfyUI    (VT_DATA; default: next to the install)
    run-engine.*  starts the engine
