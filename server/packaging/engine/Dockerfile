# Video Tool Engine in a container (Linux with an NVIDIA card + the NVIDIA container toolkit).
#
#   docker build -t video-tool-engine .      (from the unpacked engine package: the folder that holds this file, pyproject.toml, uv.lock and vt/)
#   docker run -d --gpus all -p 8790:8790 -v vt-engine:/data video-tool-engine
#   docker logs <container>                  # the address and the pairing code
#
# The image holds the program and Python only. Ollama, ComfyUI and the models are downloaded into the /data volume on first start, so
# they survive updates of the image and are shared by every container that mounts the volume.
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONIOENCODING=utf-8 \
    PYTHONUNBUFFERED=1 \
    VT_DATA=/data \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    PATH=/opt/venv/bin:/root/.local/bin:$PATH

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl git zstd libgl1 libglib2.0-0 ffmpeg \
 && rm -rf /var/lib/apt/lists/* \
 && curl -LsSf https://astral.sh/uv/install.sh | UV_INSTALL_DIR=/usr/local/bin UV_NO_MODIFY_PATH=1 sh

WORKDIR /app
COPY pyproject.toml uv.lock ./
# the locked packages first, so a code-only change does not download PyTorch again
RUN uv sync --frozen --no-dev --no-install-project --python 3.11
COPY vt ./vt
COPY assets ./assets
RUN uv sync --frozen --no-dev --python 3.11 \
 && mkdir -p /data
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

VOLUME /data
EXPOSE 8790
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 CMD curl -fsS http://127.0.0.1:8790/.well-known/vt-engine || exit 1
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["engine", "run"]
