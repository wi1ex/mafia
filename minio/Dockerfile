FROM golang:1.24-bookworm AS builder

WORKDIR /src
RUN git clone --depth 1 --branch RELEASE.2025-07-18T21-56-31Z https://github.com/minio/minio.git . \
    && test "$(git rev-parse HEAD)" = "4021d8c8e2ef026aeda624c25ff3fffdbd112b09"
RUN CGO_ENABLED=0 go build -trimpath \
    -ldflags "$(go run buildscripts/gen-ldflags.go)" \
    -o /out/minio .

FROM debian:bookworm-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /out/minio /usr/local/bin/minio
COPY --from=builder /src/LICENSE /usr/share/licenses/minio/LICENSE
EXPOSE 9000
VOLUME ["/data"]
ENTRYPOINT ["/usr/local/bin/minio"]
CMD ["server", "/data"]
