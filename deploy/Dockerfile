# Optional: containerize an exported Godot headless server (dev_plan_1.md §4.6, 进阶方案).
#
# Build AFTER exporting the dedicated server, e.g.:
#   godot --headless --path out/snake-server --export-release "Linux Server" build/
#   docker build -t gamelink-server .
#   docker run -p 7000:7000/udp gamelink-server
#
# On a Windows host this runs via WSL2/Docker Desktop (Linux containers).
FROM ubuntu:22.04

RUN apt-get update \
    && apt-get install -y --no-install-recommends libfontconfig1 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /server
COPY ./build/ /server/

EXPOSE 7000/udp
ENTRYPOINT ["/server/gamelink-server.x86_64", "--headless", "--server"]
