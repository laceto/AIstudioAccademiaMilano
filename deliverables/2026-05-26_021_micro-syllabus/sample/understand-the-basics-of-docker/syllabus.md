# 7-Day Micro-Syllabus

**Goal:** Understand the basics of Docker  
**Daily time budget:** 15 minutes

---

## Day 1 — Why Docker exists

### The 5-Minute Core Concept

Before Docker, 'works on my machine' was the default failure mode: a Python app ran locally because of a specific Python version, system library, and env var set that didn't exist on the server. Docker packages an application plus its entire userspace (libraries, binaries, config) into an image. A container is a running instance of that image, isolated from the host but sharing the host kernel. The image is the recipe, the container is the dish. That's the whole mental model — everything else is plumbing.

### The Drill (15 min)

Install Docker Desktop, then run `docker run --rm hello-world`. Read the output line by line and identify which line came from the Docker daemon vs. the container itself. (10 min install + 5 min reading the output.)

### Why It Matters

Without grasping image-vs-container, every later command will feel like magic incantations.

---

## Day 2 — Containers vs VMs

### The 5-Minute Core Concept

A VM ships a full guest OS — kernel, init system, the works — on top of a hypervisor, so booting one takes seconds to minutes and consumes hundreds of MB to GBs of RAM. A container shares the host's kernel and only packages userspace, so it starts in milliseconds and a small image is tens of MB. The trade-off: VMs give you stronger isolation and can run a different OS family; containers give you density and speed but you're stuck on the host kernel's ABI.

### The Drill (15 min)

Run `docker run --rm alpine sh -c 'uname -a'` and compare the kernel string to the output of `uname -a` on your host. They will match. Spend the remaining time writing two sentences in your own notes about why they match. (15 min total.)

### Why It Matters

Knowing when a container is the wrong answer (cross-kernel workloads) keeps you out of dead ends.

---

## Day 3 — Images, layers, and the Dockerfile

### The 5-Minute Core Concept

A Docker image is a stack of read-only layers, one per instruction in a Dockerfile. Each layer is a diff over the one below it. The base layer is usually a slim OS like alpine or debian-slim. The cache key for a layer is the instruction text plus the context it reads (files via COPY). Reorder a Dockerfile so the slowest-to-change layer (e.g. dependency install) sits above the fastest-changing one (e.g. source code) and rebuilds become nearly instant.

### The Drill (15 min)

Write a 6-line Dockerfile for a Python script: FROM python:3.12-slim, WORKDIR, COPY requirements.txt, RUN pip install, COPY ., CMD. Build it twice and time the second build with `time docker build .`. (15 min.)

### Why It Matters

Layer-aware Dockerfiles are the difference between a 2-second rebuild and a 2-minute one.

---

## Day 4 — Volumes and bind mounts

### The 5-Minute Core Concept

Containers are ephemeral — anything written inside the container disappears when it's removed. To persist or share data, you mount storage from the host. A bind mount maps a host path directly into the container, ideal for live-reloading source code in dev. A named volume is a Docker-managed directory that survives container removal, ideal for databases and anything you don't want to manage manually. Use bind mounts for dev iteration, named volumes for state you care about in production.

### The Drill (15 min)

Run `docker run --rm -v $(pwd):/app -w /app python:3.12-slim python -c 'open("hi.txt","w").write("yo")'` and confirm `hi.txt` exists on the host afterwards. (15 min.)

### Why It Matters

Mounting wrong is the #1 cause of data loss for beginners; getting it right is muscle memory worth building.

---

## Day 5 — Networking and port publishing

### The 5-Minute Core Concept

Each container gets its own network namespace with its own loopback. The host can't reach a container's port 8000 unless you publish it with -p HOSTPORT:CONTAINERPORT. Two containers on the same user-defined bridge network can reach each other by container name as DNS — this is how a web container talks to a postgres container without hardcoding IPs. The default bridge network does NOT give you name-based DNS; always create a named network for multi-container setups.

### The Drill (15 min)

Run `docker run --rm -p 8080:80 nginx`. Open http://localhost:8080 in a browser, see the welcome page. In another terminal, run `docker ps` and note the PORTS column. (10 min.)

### Why It Matters

Most 'I can't connect to my container' problems are one of three things; today's drill makes you fluent in all three.

---

## Day 6 — docker compose — the developer's daily driver

### The 5-Minute Core Concept

compose.yaml declares multiple containers as services with networks and volumes in one file. `docker compose up` brings the whole stack online; `docker compose down` tears it down. Services on the same compose project share a default user-defined network, so they get name-based DNS for free. This is what 95% of local development actually looks like — you almost never run raw `docker run` in real projects.

### The Drill (15 min)

Write a compose.yaml with two services: a web (use nginx) and a redis. Run `docker compose up -d`, then `docker compose exec web ping -c 1 redis`. The ping succeeds because of name-based DNS. (15 min.)

### Why It Matters

compose is the gateway from toy single-container demos to real multi-service development.

---

## Day 7 — Ship it — image size, .dockerignore, multi-stage builds

### The 5-Minute Core Concept

Production images should be small, reproducible, and free of build tools. A .dockerignore file keeps `node_modules`, `.git`, secrets, and tests out of the build context. A multi-stage build uses one image to compile (with full toolchain) and copies only the final binary or asset into a slim runtime image. The result is a 50MB production image instead of an 800MB one, with a smaller attack surface and faster pulls in CI.

### The Drill (15 min)

Take yesterday's compose.yaml's web service, add a .dockerignore, and rewrite the Dockerfile as a multi-stage build. Compare image sizes with `docker images`. (15 min.)

### Why It Matters

This is the day your Docker work starts looking like something you'd actually ship to production.
