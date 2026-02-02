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

## References

- [Helm](https://helm.sh/)
- [Argo CD](https://argo-cd.readthedocs.io/)
- [Flux Helm controller](https://fluxcd.io/flux/components/helm/) and [HelmRelease](https://fluxcd.io/flux/components/helm/helmreleases/)
- [JFrog Artifactory](https://jfrog.com/artifactory/)
