# SPDX-License-Identifier: MIT

# Durable go_router image — single persistent process (the SSE hub is in-memory,
# so it must NOT be split across serverless instances; one long-running
# container is required).
FROM golang:1.23-alpine AS build
WORKDIR /src
COPY go.mod ./
COPY . .
RUN CGO_ENABLED=0 go build -o /out/go_router .

FROM gcr.io/distroless/static-debian12
COPY --from=build /out/go_router /go_router
# Binds to $PORT if set (Fly/Railway inject it), else :8080.
ENV PORT=8080
EXPOSE 8080
ENTRYPOINT ["/go_router", "serve"]
