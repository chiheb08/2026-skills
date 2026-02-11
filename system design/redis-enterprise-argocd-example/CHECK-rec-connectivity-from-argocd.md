# Check REC / rec-services-rigger connectivity from Argo CD (when OpenShift UI is not reachable)

When **OpenShift is not reachable** (e.g. VPN down, cluster unavailable), you can still use **Argo CD** to see part of the picture—**if Argo CD can reach the cluster**. If the cluster is completely down, Argo CD cannot show live status either.

---

## 1. What Argo CD can tell you (when the cluster is reachable)

Argo CD talks to the **Kubernetes/OpenShift API server**. It does **not** run connectivity tests (e.g. from rec-services-rigger to rec:9443). It only shows **resource sync and health** for the application.

### In the Argo CD UI

1. **Open the Redis Enterprise application** (e.g. `redis-enterprise`).
2. Check:
   - **Sync status** — Synced / OutOfSync (compares Git vs cluster).
   - **Health status** — Healthy / Progressing / Degraded / Missing / Unknown.
   - **Resource tree** — Which resources Argo CD sees (REC, REDB; sometimes operator-created resources if they are in the same path or have the right owner references).

3. **What to look for:**
   - **Health = Progressing or Degraded** → REC may not be ready yet; can be consistent with rec-services-rigger not reaching rec:9443 (operator/REC not finished).
   - **Health = Healthy** → REC is reported ready by the operator; connectivity to rec:9443 might still be broken by NetworkPolicy, but the REC resource itself is OK.
   - **Sync = OutOfSync** → Git and cluster differ; avoid auto-sync if you’re debugging operator/REC (see existing REC docs).

4. **Resource details (if shown):**
   - Click the **REC** resource → Argo CD may show the **live manifest** (including `.status`). In **status** you can sometimes see cluster state. That does **not** prove rec-services-rigger can reach rec:9443; it only shows what the operator has written to the REC.

**Summary:** Argo CD tells you **application and resource state**, not “can rec-services-rigger reach service rec”. For that you need cluster access (OpenShift UI or kubectl/oc).

---

## 2. When OpenShift (cluster) is not reachable

- If the **cluster API is unreachable**, Argo CD cannot load live status. The app may show **Unknown** or connection errors.
- In that case there is **no way** to check connectivity (endpoints, NetworkPolicy, pod logs) from Argo CD alone. You have to wait until the cluster is reachable again, then:
  - Use **OpenShift UI** (Networking → Services → rec → Endpoints; Network Policies; Pods → rec-services-rigger → Logs), or
  - Use **kubectl/oc** from a place that can reach the cluster.

---

## 3. What you can do in Argo CD while waiting for OpenShift

1. **Confirm Git is correct** — In Argo CD, open the app and check **Source** (repo, path, revision). Ensure REC/REDB and any NetworkPolicy YAML you use are in that path and committed.
2. **Check ignoreDifferences** — For the REC, ensure `ignoreDifferences` for `.status` is set so Argo CD doesn’t overwrite operator status (see your `application.yaml`).
3. **Decide on auto-sync** — If you’re debugging rec:9443 / services-rigger, consider turning **off** auto-sync for the Redis app so the operator can run without Git overwriting REC status.
4. **When the cluster is back** — Run the connectivity checks (Service rec endpoints, NetworkPolicy ingress/egress, same namespace) from the OpenShift UI or with kubectl/oc as in the main troubleshooting docs.

---

## 4. Quick reference: where connectivity is actually checked

| Check | Where |
|-------|--------|
| Service **rec** has endpoints | OpenShift: Networking → Services → rec → Endpoints. Or: `kubectl get endpoints rec -n <ns>` |
| rec-services-rigger and **rec** in same namespace | OpenShift: Pod and Service details. Or: `kubectl get svc rec -n <ns>` and `kubectl get pod -l name=services-rigger -n <ns>` |
| NetworkPolicy allows ingress to REC pods | OpenShift: Networking → Network Policies. Or: `kubectl get networkpolicy -n <ns>` and inspect YAML |
| rec-services-rigger logs (RS API errors) | OpenShift: Workloads → Pods → rec-services-rigger → Logs. Or: `kubectl logs -n <ns> -l name=services-rigger -f` |
| Argo CD app health / sync | Argo CD UI (or CLI) — only when cluster is reachable; does not test rec:9443 connectivity |

So: **Argo CD** = app/resource status when the cluster is reachable; **OpenShift UI or kubectl/oc** = actual connectivity checks (endpoints, policies, logs). When OpenShift is not reachable, use Argo CD to verify Git and app config, and run the connectivity checks once the cluster is back.
