# ComfyUI big-disk boot audit

Checked on 2026-10-27, after the redundant root model weights were removed.

- `/mnt/bigdata` is `/dev/sdb2`, ext4, mounted by the UUID entry in `/etc/fstab`. `findmnt --verify` reported zero parse errors and zero errors. The entry has `nofail` and a 10-second device timeout: the machine may still boot when the disk is absent.
- ComfyUI is enabled at boot. Before this change, its effective unit had no requirement on `mnt-bigdata.mount`, even though its Python interpreter, model paths, input/output, and user data were on that disk.
- Installed the versioned [`20-bigdata-boot.conf`](../../../assets/comfy/systemd/20-bigdata-boot.conf) under `/etc/systemd/system/comfyui.service.d/`. `systemctl daemon-reload` showed `mnt-bigdata.mount` in both `Requires` and `After`, and the two big-disk paths in `RequiresMountsFor`.
- Restarted only `comfyui.service` successfully. The API then reported ComfyUI 0.42.5 and PyTorch 2.12.1+cu126. Live model choices still included LTX 2.3, Wan 2.2, and Z-Image. The disk remained mounted; `/` was 62% used and `/mnt/bigdata` 81% used.

This verifies the persistent systemd and mount configuration plus a service restart. **The whole server was not rebooted**; unrelated services were left running. If the big disk is unavailable during a future boot, ComfyUI will not start against the root directory. A full reboot test would confirm the complete boot path, but would interrupt the other services on this machine.
