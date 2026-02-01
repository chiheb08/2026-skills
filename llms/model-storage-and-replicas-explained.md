# Model Storage and Replicas in Kubernetes — Explained in Detail

This document clarifies two things that often cause confusion when running vLLM (or any LLM) on Kubernetes/OpenShift:

1. **Where do the models live?** Do we download them once and store them in a PV/PVC?
2. **What does “2 replicas of 7B” mean?** One copy of the model in storage, or multiple copies? How do replicas relate to that?

---

## Table of Contents

1. [PV and PVC in One Paragraph](#1-pv-and-pvc-in-one-paragraph)
2. [Where Are the Models Stored? (One Time)](#2-where-are-the-models-stored-one-time)
3. [How Does a vLLM Pod Use the Model?](#3-how-does-a-vllm-pod-use-the-model)
4. [What Does “2 Replicas of 7B” Mean Exactly?](#4-what-does-2-replicas-of-7b-mean-exactly)
5. [One Model in Storage, Multiple Instances in Memory](#5-one-model-in-storage-multiple-instances-in-memory)
6. [Summary Diagram](#6-summary-diagram)
7. [Practical Options (Shared PVC vs Image)](#7-practical-options-shared-pvc-vs-image)
8. [References](#8-references)

---

## 1. PV and PVC in One Paragraph

- **PV (Persistent Volume)**  
  A piece of storage that the cluster knows about (e.g. a disk, NFS share, or cloud disk). It has a fixed size and access mode (ReadWriteOnce, ReadOnlyMany, ReadWriteMany). The cluster admin (or a provisioner) creates PVs.

- **PVC (Persistent Volume Claim)**  
  A “request” for storage by a workload. You say “I need 500 Gi, ReadWriteMany.” Kubernetes binds the PVC to a suitable PV (or dynamically provisions one). Pods then **mount** the PVC as a directory inside the container. Whatever is written to that directory is stored on the PV and survives pod restarts and rescheduling.

So: **you store data (e.g. model files) on a PV; pods access it by mounting a PVC that is bound to that PV.**  
Yes — in the typical setup, you **download/copy the model once** into that storage (PV/PVC), and then **multiple pods can use that same storage** (if the volume supports multiple readers, e.g. ReadWriteMany or ReadOnlyMany).

---

## 2. Where Are the Models Stored? (One Time)

You are correct: **we download (or copy) the model once and store it in durable storage.** In Kubernetes, that storage is usually exposed as a **PV**, and workloads use it via a **PVC**.

- **One-time setup:**  
  You download the model (e.g. from Hugging Face or an internal registry) and put the files into the volume that backs the PVC. That can be done by:
  - A one-off Job that mounts the PVC, runs `huggingface-cli download` (or similar), and writes into the mounted path, or
  - Copying from another server/NFS into that volume, or
  - Using an init container that pulls the model on first use (then it’s effectively “stored” on that volume after the first run).

- **Result:**  
  The model files (weights, config, tokenizer, etc.) sit on the **PV**. The **PVC** is just the “handle” that pods use to mount that same storage. So:
  - **One copy of the model on disk** (in the PV).
  - **No need to re-download per pod** — each pod mounts the same PVC (or a copy of it, depending on access mode) and reads the same files.

So your mental model is right: **download once → store in PV (used via PVC) → many pods can read from it** (when the volume supports multiple readers).

---

## 3. How Does a vLLM Pod Use the Model?

A vLLM **pod** is one running instance of the vLLM server (one process, usually one GPU).

Rough flow:

1. **Startup:**  
   The pod starts and mounts the PVC (or reads from a path that was populated from the PVC/image). So the container sees a **directory** (e.g. `/models/llama-2-7b`) containing the model files.

2. **Load into GPU memory (VRAM):**  
   vLLM **reads** the model files from disk and **loads the weights into the GPU’s VRAM**. This happens **inside that pod, in that GPU’s memory**. So:
   - **On disk (PV/PVC):** one copy of the model (shared or per-pod, see below).
   - **In each pod:** vLLM loads that model from disk into **that pod’s GPU VRAM**. So each running pod has its **own in-memory copy** of the model for inference.

3. **Serving:**  
   Once loaded, vLLM serves requests using the model in VRAM. It does **not** re-read the full model from disk for each request; disk is used only at startup (and optionally for cache, etc.).

So: **storage (PV/PVC) = long-term place for the model files; each pod loads from that (or from a copy) into its own GPU memory once at startup.**

---

## 4. What Does “2 Replicas of 7B” Mean Exactly?

**“2 replicas of 7B”** means: **two separate vLLM instances (two pods), each serving the same 7B model.**

- **Replica** = another copy of the **same service** (same app, same model), not another copy of the model **on disk**.
- So:
  - **Model on storage:** typically **one** copy of the 7B model (e.g. on one PVC-backed PV, or inside one image).
  - **Running instances:** **two** vLLM pods (two replicas). Each pod has its own GPU, loads the 7B model (from the shared storage or from the same image) into its **own** VRAM, and serves requests independently.

So:

- We **load/save/download the model once** in our storage (PV/PVC or image).
- We **create more than one instance** of the vLLM **process** (replicas). Each instance mounts (or has a copy of) that same model and loads it into its own GPU memory.

That’s exactly what you said: **one copy in storage, multiple instances (replicas) using it.**

---

## 5. One Model in Storage, Multiple Instances in Memory

| Where            | What you have                          | Count |
|------------------|----------------------------------------|-------|
| **Storage (PV/PVC)** | One set of model files (e.g. Llama 2 7B) | **1** (one copy on disk) |
| **Pods (replicas)**  | Multiple vLLM processes                | **2** (for “2 replicas”) |
| **GPU VRAM (per pod)** | Each pod loads the model into its GPU | **2** in-memory copies (one per pod) |

- **Disk:** 1 copy of the model (saves space, one place to update).
- **Pods:** 2 (or N) replicas = 2 (or N) independent vLLM servers.
- **VRAM:** Each of those pods has its own GPU and its own copy of the model **in that GPU’s memory** for the duration of the pod’s life.

So: **one model in storage, multiple instances (replicas) in memory.**

---

## 6. Summary Diagram

```
                    ┌─────────────────────────────────────────────────────────┐
                    │  STORAGE (once)                                          │
                    │  ┌─────────────────────────────────────────────────────┐ │
                    │  │  PV (Persistent Volume)                              │ │
                    │  │  e.g. NFS / storage class provisioned disk            │ │
                    │  │  ┌─────────────────────────────────────────────┐   │ │
                    │  │  │  /models/llama-2-7b/                        │   │ │
                    │  │  │  (model weights, config, tokenizer — 1 copy) │   │ │
                    │  │  └─────────────────────────────────────────────┘   │ │
                    │  └─────────────────────────────────────────────────────┘ │
                    │  ↑                                                       │
                    │  PVC (Persistent Volume Claim) — "request" for that PV   │
                    │  e.g. 500Gi, ReadWriteMany or ReadOnlyMany               │
                    └──────────────────────────┬──────────────────────────────┘
                                               │
                     Both pods mount the SAME PVC (read-only or read-write)
                                               │
                    ┌──────────────────────────┴──────────────────────────────┐
                    │  RUNNING INSTANCES (replicas)                             │
                    │                                                            │
                    │  Pod 1 (replica 1)              Pod 2 (replica 2)          │
                    │  ┌─────────────────────┐      ┌─────────────────────┐    │
                    │  │ vLLM process         │      │ vLLM process         │    │
                    │  │ mount: PVC → /models │      │ mount: PVC → /models │    │
                    │  │ load model → GPU 1   │      │ load model → GPU 2   │    │
                    │  │ (VRAM copy 1)        │      │ (VRAM copy 2)        │    │
                    │  │ serve requests       │      │ serve requests       │    │
                    │  └─────────────────────┘      └─────────────────────┘    │
                    │           │                              │                │
                    │       GPU 1 (H200)                   GPU 2 (H200)         │
                    └───────────┼──────────────────────────────┼────────────────┘
                                │                              │
                                └──────────────┬───────────────┘
                                               │
                                    LiteLLM (or load balancer)
                                    sends requests to both pods
                                    → "2 replicas of 7B"
```

- **Top:** One copy of the model on a PV, used via a PVC.
- **Bottom:** Two pods (two replicas). Each mounts the same PVC, loads the model into its own GPU’s VRAM, and serves. So: **one model in storage, two instances (replicas) in memory.**

---

## 7. Practical Options (Shared PVC vs Image)

Two common ways to get “one copy of the model, many replicas”:

### Option A: Shared PVC (ReadOnlyMany or ReadWriteMany)

- **One** PVC bound to a PV (e.g. NFS or a storage class that supports RWX/ROX).
- **One-time:** A Job (or manual step) downloads the model into that PVC (e.g. into `/models/llama-2-7b`).
- **All vLLM pods** for that model mount the **same** PVC (read-only) at e.g. `/models/llama-2-7b`.
- Each pod **reads** the same files from disk at startup and loads them into its **own** GPU VRAM.
- **Result:** One copy on disk, N replicas in memory. Saves disk space and avoids re-downloading per pod.

### Option B: Model Baked into Container Image

- Build an image that **contains** the model files (e.g. in `/app/models/llama-2-7b`). So the “storage” is the image layer.
- Each vLLM pod runs from that image; each pod has its **own** copy of the files **inside** its container filesystem (so technically N copies on disk across nodes, but no separate PV/PVC).
- Each pod still loads the model from its local filesystem into **its** GPU VRAM.
- **Result:** Same idea — one “logical” copy of the model (in the image), N running instances (replicas), each with the model in VRAM. No PVC needed; simpler if your cluster doesn’t have a good shared storage.

### Option C: Init Container That Downloads Once per Pod (Not Ideal for Many Replicas)

- Each pod has an init container that downloads the model into an **emptyDir** or a **pod-local** volume. Then the main container loads from there.
- That means **each pod** re-downloads (or copies) the model once when it starts. So you’re not “storing once in a PV” — you’re storing once **per pod** on local/ephemeral storage. For many replicas, this wastes bandwidth and time; shared PVC or image is usually better.

**Recommendation for “one copy in storage, many replicas”:** Use **Option A (shared PVC)** or **Option B (image)**. Your understanding — **download/store once, create more than one instance (replica)** — is correct; Option A or B is how we do it in Kubernetes.

---

## 8. References

- [Infrastructure sizing (700–1500 users)](./infrastructure-sizing-700-1500-users.md) — replicas and GPU counts
- [vLLM deployment](https://docs.vllm.ai/en/stable/) — how vLLM loads models
- Kubernetes [Volumes](https://kubernetes.io/docs/concepts/storage/volumes/), [PV](https://kubernetes.io/docs/concepts/storage/persistent-volumes/), [PVC](https://kubernetes.io/docs/concepts/storage/persistent-volumes/#persistentvolumeclaims)

---

## Short Answers to Your Questions

| Question | Answer |
|----------|--------|
| Do we download models and store them in a PV or PVC? | **Yes.** We download/copy the model **once** and store it in storage that is exposed to the cluster as a **PV**; workloads use it via a **PVC**. |
| What does “2 replicas of 7B” mean? | **Two** separate vLLM **pods** (two instances), each serving the **same** 7B model. Each pod loads that model (from shared PVC or from the same image) into **its own** GPU VRAM. |
| Do we load/save the model once and then create more than one instance with replicas? | **Yes.** One copy of the model in storage (PV/PVC or image). Replicas = multiple **running instances** (pods), each with the model in its **own** GPU memory. |
