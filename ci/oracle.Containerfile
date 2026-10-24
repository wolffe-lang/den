FROM docker.io/library/ubuntu:24.04@sha256:534baea6a22c03a63003dbc8dbe78fe34bc0d7e595d9a9dc9834884ff530eb55
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends build-essential cargo rustc binutils clang lld ca-certificates curl git gnupg python3 gettext libssl-dev libcurl4-openssl-dev libexpat1-dev zlib1g-dev perl libz-dev time xz-utils openssl && rm -rf /var/lib/apt/lists/*
ENV LC_ALL=C CARGO_INCREMENTAL=0
WORKDIR /work/den
