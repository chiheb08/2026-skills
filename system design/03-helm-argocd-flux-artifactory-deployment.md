# Helm, Argo CD, Flux, and JFrog Artifactory — How the Deployment Fits Together

This document explains a typical GitOps deployment setup where:

- **Helm charts** are developed in a repository and pushed to **JFrog Artifactory**.
- A **second repository** (watched by **Argo CD**) contains deployment manifests, including **HelmRelease** resources.
- **Flux** runs in the cluster and installs/upgrades Helm releases from Artifactory when it sees a HelmRelease.

If you are new to this flow (“we use Helm, push to Artifactory, and I see HelmRelease and something about Flux”), this should clarify how the pieces connect.

---

## Table of Contents

1. [Overview](#1-overview)
2. [The Three Layers](#2-the-three-layers)
3. [Step-by-Step Flow](#3-step-by-step-flow)
4. [What Each Piece Does](#4-what-each-piece-does)
5. [Why Argo CD and Flux Together?](#5-why-argocd-and-flux-together)
6. [Quick Reference](#6-quick-reference)
7. [Simple Example: One App, Step by Step (Junior-Friendly)](#7-simple-example-one-app-step-by-step-junior-friendly)

---

## 1. Overview

| Component | Role |
|-----------|------|
| **Helm** | Package format for Kubernetes: templates + values. Defines *what* to deploy and *how* (config). |
| **JFrog Artifactory** | Binary/artifact repository. Stores the **built Helm charts** (e.g. `myapp-1.0.0.tgz`) so the cluster can pull them. |
| **Git repo (chart repo)** | Where you **write** Helm charts (templates + values). You package the chart and push the `.tgz` to Artifactory. |
| **Git repo (Argo CD)** | Where you put **deployment manifests**. Argo CD syncs this repo to the cluster. Some manifests are `HelmRelease` objects. |
| **Argo CD** | GitOps controller. Keeps the cluster in sync with the “Argo CD” Git repo (applies the manifests, including HelmReleases). |
| **Flux** | GitOps/Helm controller **in the cluster**. Watches for `HelmRelease` resources and runs **Helm** to install/upgrade the chart (e.g. from Artifactory). |

So: **Charts live in Artifactory; “which chart and which values” are defined in Git as a HelmRelease; Argo CD applies that from Git; Flux installs the chart from Artifactory.**

---

## 2. The Three Layers

```
  LAYER 1: Chart authoring and storage
  -------------------------------------
  You write Helm charts (templates + values)
       |
  Package: helm package ...
       |
  Push to JFrog Artifactory  -->  Chart stored (e.g. myapp-1.0.0.tgz)

  LAYER 2: Desired state in Git (Argo CD repo)
  ---------------------------------------------
  You add/update a manifest: kind: HelmRelease
  (chart: from Artifactory, version: 1.0.0, values: ...)
       |
  Push to Git  -->  Argo CD repo now has the HelmRelease YAML

  LAYER 3: Cluster (Argo CD + Flux)
  ---------------------------------
  Argo CD syncs Git  -->  Applies the HelmRelease manifest to the cluster
       |
  Flux (Helm controller) sees the HelmRelease
       |
  Flux runs: helm upgrade --install ... using chart from Artifactory
       |
  Your application is deployed/updated in the cluster
```

---

## 3. Step-by-Step Flow

| Step | Who / What | Action |
|------|------------|--------|
| 1 | You / CI | Edit Helm chart (templates + values) in the chart repository. |
| 2 | You / CI | Package the chart: `helm package .` → e.g. `myapp-1.0.0.tgz`. |
| 3 | You / CI | Push the chart to **JFrog Artifactory** (Helm repository). |
| 4 | You / CI | In the **Argo CD repository**, add or update a manifest with `kind: HelmRelease` that references the chart (e.g. from Artifactory), version, and values. |
| 5 | You / CI | Push the Argo CD repo to Git. |
| 6 | **Argo CD** | Watches the Git repo; sees the new/updated HelmRelease; **applies** the HelmRelease YAML to the cluster. |
| 7 | **Flux** | Sees the HelmRelease resource; fetches the chart from Artifactory (via a HelmRepository source); runs **Helm** to install or upgrade the release in the cluster. |

Result: The application defined by the Helm chart runs in the cluster, and future changes go through the same flow (update chart → push to Artifactory; update HelmRelease in Git → Argo CD syncs → Flux upgrades).

---

## 4. What Each Piece Does

### Helm charts (first repository)

- You maintain **templates** (e.g. Deployment, Service, ConfigMap) and **values** (e.g. `values.yaml`).
- You **package** the chart: `helm package .` → `myapp-1.0.0.tgz`.
- You **push** that file to **JFrog Artifactory** (configured as a Helm repository). The chart is now available at a URL with a version.

### JFrog Artifactory

- Stores the **.tgz** Helm charts (and optionally other artifacts).
- Exposes a **Helm repository** (HTTP/HTTPS) that Flux (and Helm) can use. You typically define a **HelmRepository** resource in the cluster that points to this URL (and credentials if needed).

### Second repository (Argo CD)

- This is the repository that **Argo CD** is configured to watch (e.g. “this Git repo is my source of truth for this app or this environment”).
- In this repo you store **Kubernetes manifests** that describe what should run. Some of these manifests have **`kind: HelmRelease`** (a custom resource defined by Flux).

### HelmRelease (Flux custom resource)

- **HelmRelease** is a **Custom Resource** managed by **Flux** (the Helm controller).
- It means: “Install or upgrade this Helm release using this chart (from this Helm repository), this version, and these values.”

Example:

```yaml
apiVersion: helm.toolkit.fluxcd.io/v2beta1
kind: HelmRelease
metadata:
  name: myapp
  namespace: my-namespace
spec:
  chart:
    spec:
      chart: myapp
      version: "1.0.0"
      sourceRef:
        kind: HelmRepository
        name: jfrog-artifactory
        namespace: flux-system
  values:
    replicaCount: 3
    image:
      tag: "v1.2.3"
```

- **Chart source:** The `sourceRef` points to a **HelmRepository** resource (e.g. `jfrog-artifactory`) that points at JFrog Artifactory. So the chart is pulled from Artifactory.
- **Version and values:** Come from this Git file (and thus from the Argo CD repo). So “what to deploy” is versioned in Git; “how” (templates) is in the chart in Artifactory.

### Argo CD

- **Role:** Keep the cluster state in sync with the Git repo (the Argo CD repo).
- It **applies** the YAML files from that repo, including the **HelmRelease** manifest. It does **not** run Helm itself; it only ensures the HelmRelease resource exists (or is updated) in the cluster.

### Flux (in the cluster)

- **Role:** Watch **HelmRelease** resources and run **Helm** to install/upgrade the corresponding release.
- When a HelmRelease is created or updated, the Flux Helm controller:
  - Resolves the chart from the HelmRepository (Artifactory),
  - Runs the equivalent of `helm upgrade --install` with the chart and the values from the HelmRelease,
  - So the actual Deployment, Service, etc. in the cluster are created/updated by **Flux**, not by Argo CD rendering the chart.

So: **Argo CD = “apply the HelmRelease from Git”; Flux = “run Helm using that HelmRelease and the chart in Artifactory”.**

---

## 5. Why Argo CD and Flux Together?

- **Argo CD** is the “Git sync” engine: the source of truth is **Git**; Argo CD applies the manifests (including HelmReleases) from the Argo CD repo to the cluster.
- **Flux** provides the **Helm controller**: it knows how to talk to Helm repositories (e.g. Artifactory) and how to run `helm upgrade --install` when it sees a HelmRelease.

So:

- **Git (Argo CD repo)** = where you declare *which* Helm release, *which* version, and *which* values.
- **Artifactory** = where the actual chart packages live.
- **Argo CD** = keeps the cluster in sync with Git (applies the HelmRelease).
- **Flux** = turns HelmReleases into real Helm releases in the cluster by pulling the chart from Artifactory and running Helm.

You could use only Argo CD with native Helm support (Argo CD can also pull Helm charts from a repo). In this setup, the choice is: **Argo CD for Git sync**, **Flux for Helm from Artifactory**, and the “contract” between them is the **HelmRelease** manifest in the Git repo.

---

## 6. Quick Reference

| Term | Meaning in this setup |
|------|------------------------|
| **Helm chart repo** | Repository where you **write** Helm charts (templates + values). |
| **JFrog Artifactory** | Where you **push** the built chart (`.tgz`). It is the Helm repository the cluster uses. |
| **Argo CD repo** | Git repository that contains **deployment manifests**; Argo CD syncs this repo to the cluster. |
| **HelmRelease** | A manifest in that Git repo that says: “Install/upgrade this Helm chart from Artifactory, with this version and these values.” It is a **Flux** custom resource. |
| **Argo CD** | Syncs the Git repo (including the HelmRelease YAML) to the cluster. |
| **Flux** | In the cluster; watches HelmReleases and runs **Helm** to install/upgrade the chart from Artifactory. |

**One sentence:** Charts are built and stored in Artifactory; “which chart and which values” are defined in Git as a HelmRelease; Argo CD applies that from Git; Flux installs the chart from Artifactory into the cluster.

---

## 7. Simple Example: One App, Step by Step (Junior-Friendly)

This section uses a **very simple example**: one small app called **hello-app** (e.g. a tiny web server that says "Hello"). Each file and each step is explained so you can follow along even if you are new to Helm, Git, or Kubernetes.

### 7.1 What we are going to do

We will: (1) create a Helm chart for hello-app in a **chart repo**, (2) package it and push it to **Artifactory**, (3) add a **HelmRelease** in the **Argo CD repo** that says "deploy hello-app from Artifactory with these settings", (4) push to Git so **Argo CD** applies it and **Flux** installs the app in the cluster.

### 7.2 Repositories we use (simple names)

| Repo name (example) | What it contains | Who uses it |
|---------------------|------------------|-------------|
| **chart-repo** | Helm chart for hello-app (templates + values) | You / CI: edit chart, package, then push the .tgz to Artifactory |
| **deploy-repo** | YAML files: HelmRepository, HelmRelease | Argo CD: syncs these files to the cluster |
| **Artifactory** | Not a Git repo; stores the built chart file (e.g. hello-app-1.0.0.tgz) | Flux: pulls the chart from here when it sees a HelmRelease |

### 7.3 Step 1: Create the Helm chart (in chart-repo)

A Helm chart is a folder with a fixed structure. Below is the **minimum** you need.

**Folder structure:**

```
chart-repo/hello-app/
  Chart.yaml          # Name and version of the chart
  values.yaml         # Default config (replicas, image, port)
  templates/
    deployment.yaml   # "Run these containers"
    service.yaml      # "Expose this app on a port"
```

**File 1: `Chart.yaml`**

```yaml
apiVersion: v2
name: hello-app
description: A simple hello app
version: 1.0.0
appVersion: "1.0"
```

- **name:** The chart name. You use this in the HelmRelease later (e.g. chart: hello-app).
- **version:** Chart version. When you run `helm package .`, the file will be hello-app-1.0.0.tgz. You refer to this version in the HelmRelease.

**File 2: `values.yaml`**

```yaml
replicaCount: 1
image:
  repository: myregistry.io/hello-app
  tag: "1.0"
  pullPolicy: IfNotPresent
service:
  port: 80
```

- **replicaCount:** Number of pods (copies) of the app. You can override this in the HelmRelease (e.g. set 3 in Git).
- **image:** Which container image to run. **repository** = image name; **tag** = version.
- **service.port:** Port on which the app is exposed.

**File 3: `templates/deployment.yaml`**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Release.Name }}
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      app: {{ .Release.Name }}
  template:
    metadata:
      labels:
        app: {{ .Release.Name }}
    spec:
      containers:
        - name: hello-app
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          ports:
            - containerPort: {{ .Values.service.port }}
```

- **{{ .Release.Name }}:** The name of the Helm release (e.g. hello-app).
- **{{ .Values.replicaCount }}:** Replaced by replicaCount from values (1 by default, or what you set in the HelmRelease).
- **{{ .Values.image.repository }}:{{ .Values.image.tag }}:** Replaced by the image name and tag.

**File 4: `templates/service.yaml`**

```yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ .Release.Name }}
spec:
  ports:
    - port: {{ .Values.service.port }}
      targetPort: {{ .Values.service.port }}
  selector:
    app: {{ .Release.Name }}
```

- **selector:** "Send traffic to pods with this label." Here: pods created by the Deployment above.

After these four files, you have a **complete (minimal) Helm chart** for hello-app.

### 7.4 Step 2: Package the chart and push to Artifactory

1. Go into the chart folder: `cd chart-repo/hello-app`
2. Package: `helm package .` → creates **hello-app-1.0.0.tgz**
3. Push that file to **JFrog Artifactory** (your team has the URL and credentials). Example: `curl -u user:token -T hello-app-1.0.0.tgz "https://artifactory.mycompany.com/helm-repo/"`

**Result:** The chart is stored in Artifactory. Flux will download it using the HelmRepository URL.

### 7.5 Step 3: Tell the cluster where Artifactory is (HelmRepository)

Create a **HelmRepository** in the **deploy-repo** so Flux knows "when I need a chart from Artifactory, use this URL."

**File in deploy-repo: `helm-repository.yaml`**

```yaml
apiVersion: source.toolkit.fluxcd.io/v1
kind: HelmRepository
metadata:
  name: jfrog-artifactory
  namespace: flux-system
spec:
  url: https://artifactory.mycompany.com/helm-repo
  interval: 1h
  secretRef:
    name: artifactory-credentials
```

- **kind: HelmRepository:** Flux resource = "a Helm repo (place where .tgz charts are stored)".
- **metadata.name: jfrog-artifactory:** Name you use in the HelmRelease (sourceRef.name).
- **spec.url:** Base URL of your Helm repo in Artifactory.
- **spec.secretRef:** If Artifactory requires login, credentials are in a Secret named artifactory-credentials.

**Result:** The cluster has a "pointer" to Artifactory. When a HelmRelease says "get the chart from jfrog-artifactory", Flux uses this URL.

### 7.6 Step 4: Ask the cluster to deploy hello-app (HelmRelease)

Add a **HelmRelease** in the deploy-repo: "Install hello-app using chart hello-app version 1.0.0 from jfrog-artifactory, with these values."

**File in deploy-repo: `hello-app-release.yaml`**

```yaml
apiVersion: helm.toolkit.fluxcd.io/v2beta1
kind: HelmRelease
metadata:
  name: hello-app
  namespace: default
spec:
  chart:
    spec:
      chart: hello-app
      version: "1.0.0"
      sourceRef:
        kind: HelmRepository
        name: jfrog-artifactory
        namespace: flux-system
  values:
    replicaCount: 2
    image:
      tag: "1.0"
```

**Explanation:**

- **kind: HelmRelease:** Flux resource = "install or upgrade this Helm release".
- **metadata.name: hello-app:** Release name. Deployment and Service will be named hello-app.
- **spec.chart.spec.chart: hello-app:** Chart name (must match Chart.yaml). Flux looks for hello-app-1.0.0.tgz.
- **spec.chart.spec.version: "1.0.0":** Chart version (must match Chart.yaml).
- **spec.chart.spec.sourceRef:** Where to get the chart. **name: jfrog-artifactory** = use the HelmRepository we created in Step 3 (Artifactory).
- **spec.values:** Overrides. Here **replicaCount: 2** (2 pods) and **image.tag: "1.0"**. Rest comes from the chart defaults.

**Result:** You have told the cluster (via Git): "Deploy hello-app from Artifactory, version 1.0.0, with 2 replicas." Argo CD will apply this YAML; Flux will see the HelmRelease and run Helm to install the chart.

### 7.7 Step 5: Push the deploy-repo to Git

Commit and push `helm-repository.yaml` and `hello-app-release.yaml` to the deploy-repo (the one Argo CD watches).

**What happens next (automatically):**

1. **Argo CD** sees the new/updated files and applies them. The cluster now has a HelmRepository and a HelmRelease.
2. **Flux** sees the HelmRelease "hello-app". It downloads hello-app-1.0.0.tgz from Artifactory, runs Helm, and creates the Deployment and Service.
3. **Kubernetes** runs 2 pods and the Service. hello-app is running in the cluster.

### 7.8 Summary of the example

| Step | Where | What you do | Result |
|------|--------|-------------|--------|
| 1 | chart-repo | Create Chart.yaml, values.yaml, templates/deployment.yaml, templates/service.yaml | You have a Helm chart for hello-app. |
| 2 | Laptop / CI | helm package . and push .tgz to Artifactory | Chart is stored in Artifactory. |
| 3 | deploy-repo | Add HelmRepository YAML (name, URL, credentials ref) | Cluster knows how to reach Artifactory. |
| 4 | deploy-repo | Add HelmRelease YAML (chart name, version, sourceRef, values) | You declare "deploy hello-app from Artifactory with these values". |
| 5 | deploy-repo | Push to Git | Argo CD applies the YAML; Flux installs the chart; hello-app runs. |

**To change the chart (e.g. fix a template):** Bump chart version, package again, push to Artifactory, then in deploy-repo change the HelmRelease version and push to Git. Flux will upgrade the release.

**To change only values (e.g. replicaCount from 2 to 3):** Edit the HelmRelease in the deploy-repo and push to Git. No need to repackage the chart.

---

## References

- [Helm](https://helm.sh/)
- [Argo CD](https://argo-cd.readthedocs.io/)
- [Flux Helm controller](https://fluxcd.io/flux/components/helm/) and [HelmRelease](https://fluxcd.io/flux/components/helm/helmreleases/)
- [JFrog Artifactory](https://jfrog.com/artifactory/)
