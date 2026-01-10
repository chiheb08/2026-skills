# System Design Fundamentals: Communication Patterns

> A beginner-friendly guide to understanding core communication concepts in system design.

---

## Table of Contents
1. [The Pipe (Pipeline Pattern)](#1-the-pipe-pipeline-pattern)
2. [Polling](#2-polling)
3. [Bidirectional WebSocket](#3-bidirectional-websocket)
4. [Throttling](#4-throttling)
5. [Request-Response (HTTP / RPC)](#5-request-response-http--rpc)
6. [Publish-Subscribe (Pub/Sub)](#6-publish-subscribe-pubsub)
7. [Message Queue (Work Queue)](#7-message-queue-work-queue)
8. [Webhooks](#8-webhooks)
9. [Server-Sent Events (SSE)](#9-server-sent-events-sse)
10. [Event Streaming (Log-Based)](#10-event-streaming-log-based)
11. [Quick Comparison](#quick-comparison-table)

---

## 1. The Pipe (Pipeline Pattern)

### What is it?
A **pipe** is like a water pipe in your house - data flows through it from one place to another. In computing, it's a way to connect the output of one process directly to the input of another.

### Real-World Analogy
Think of a factory assembly line:
- Station 1 makes the car frame -> passes it to Station 2
- Station 2 adds the engine -> passes it to Station 3
- Station 3 paints the car -> passes it to Station 4

Each station does ONE job and passes the result to the next.

### In Code (Example)
```bash
# Unix/Linux pipe example
cat file.txt | grep "error" | sort | uniq
```

Here's what happens step by step:
1. `cat file.txt` - reads the file (outputs text)
2. `|` - the PIPE sends that output to...
3. `grep "error"` - filters only lines with "error"
4. `|` - sends those filtered lines to...
5. `sort` - sorts them alphabetically
6. `|` - sends sorted lines to...
7. `uniq` - removes duplicates

### When to Use Pipes
- Processing data in stages
- When each step is independent
- Streaming data transformations
- Building modular, reusable components

### Key Benefits
- **Modularity**: Each stage does one thing well
- **Reusability**: Stages can be reused in different pipelines
- **Testability**: Each stage can be tested independently

### Real-World Examples
- **Unix/Linux tooling**: `cat | grep | sort | uniq` style data processing in terminals and scripts
- **Media processing**: `ffmpeg` pipelines that decode -> filter -> encode video/audio
- **Data engineering**: ETL/ELT pipelines (extract -> transform -> load) in analytics stacks
- **Stream processing frameworks**: Apache Beam / Spark jobs built as stage-by-stage transformations

---

## 2. Polling

### What is it?
**Polling** is when a client repeatedly asks a server "Do you have new data for me?" at regular intervals. It's like constantly refreshing your email inbox.

### Real-World Analogy
Imagine you're waiting for a package:
- **Polling approach**: You call the delivery company every 5 minutes asking "Is my package here yet?"
- You keep calling until they say "Yes, it arrived!"

### How It Works
```
Client                          Server
  |                               |
  |---"Any new messages?"-------->|
  |<--------"No, nothing"---------|
  |                               |
  |   (wait 5 seconds...)         |
  |                               |
  |---"Any new messages?"-------->|
  |<--------"No, nothing"---------|
  |                               |
  |   (wait 5 seconds...)         |
  |                               |
  |---"Any new messages?"-------->|
  |<--"Yes! Here's a message"-----|
```

### Types of Polling

| Type | Description | Pros | Cons |
|------|-------------|------|------|
| **Short Polling** | Ask frequently (every few seconds), get immediate response | Simple, predictable | Wastes bandwidth, delayed updates |
| **Long Polling** | Ask once, server holds the connection until it has data | More efficient, faster updates | More complex, connection timeouts |

### Short Polling Example
```python
import time
import requests

while True:
    response = requests.get("https://api.example.com/messages")
    if response.json().get("new_messages"):
        print("New message received!")
        break
    time.sleep(5)  # Wait 5 seconds before asking again
```

### Long Polling Example
```python
import requests

# Server holds this request until there's new data
# or timeout occurs (e.g., 30 seconds)
response = requests.get(
    "https://api.example.com/messages",
    params={"wait": True, "timeout": 30}
)
```

### Pros & Cons of Polling
**Pros:**
- Simple to implement
- Works everywhere (no special protocol needed)
- Compatible with all browsers and firewalls

**Cons:**
- Wastes resources (many unnecessary requests when there's no new data)
- Delays in getting updates (depends on polling interval)
- Not truly real-time

### Real-World Examples
- **Email clients**: periodic inbox refresh (especially older/legacy setups)
- **Monitoring dashboards**: CPU/memory charts that refresh every N seconds
- **Analytics/reporting UIs**: “refresh” loops for batch-updated data (hourly/daily)
- **Long polling for near-real-time**: classic web chat/notifications before WebSockets became common

---

## 3. Bidirectional WebSocket

### What is it?
A **WebSocket** is a persistent, two-way communication channel between client and server. **Bidirectional** means BOTH sides can send messages anytime - no need to wait for the other to ask.

### Real-World Analogy
Think of a **phone call**:
- Once connected, BOTH people can talk whenever they want
- You don't need to hang up and call again to send a new message
- The connection stays open until someone hangs up

Compare this to **sending letters** (like traditional HTTP):
- You send a letter, wait for a response
- Want to say something else? Send another letter
- Very slow and inefficient for conversations

### How It Works
```
Client                          Server
  |                               |
  |===== Connection Opened =======|  (initial handshake)
  |                               |
  |---"Hello!"------------------>|  (client sends message)
  |<--"Hi there!"----------------|  (server responds)
  |<--"Breaking news: ..."-------|  (server can push anytime!)
  |---"Thanks!"----------------->|  (client responds)
  |<--"Score update: 2-1"--------|  (server pushes again)
  |                               |
  |===== Connection Stays Open ===|
```

### WebSocket vs HTTP

| Feature | HTTP | WebSocket |
|---------|------|-----------|
| Connection | New connection per request | Persistent connection |
| Direction | Client asks, server responds | Both can send anytime |
| Overhead | Headers sent every time | Minimal after handshake |
| Real-time | No (need polling) | Yes |

### JavaScript WebSocket Example
```javascript
// Client-side WebSocket
const socket = new WebSocket('wss://example.com/chat');

// Connection opened
socket.onopen = function(event) {
    console.log('Connected to server!');
    socket.send('Hello Server!');
};

// Listen for messages from server
socket.onmessage = function(event) {
    console.log('Message from server:', event.data);
};

// Handle errors
socket.onerror = function(error) {
    console.log('WebSocket Error:', error);
};

// Connection closed
socket.onclose = function(event) {
    console.log('Disconnected from server');
};
```

### Use Cases
- **Chat applications** (WhatsApp Web, Slack, Discord)
- **Live sports scores and updates**
- **Stock market / cryptocurrency price tickers**
- **Multiplayer online games**
- **Collaborative tools** (Google Docs, Figma)
- **Live notifications**

### Real-World Examples
- **WhatsApp Web / Slack / Discord**: interactive chat with typing indicators and presence
- **Google Docs / Figma**: real-time collaboration and cursor/selection updates
- **Trading apps**: streaming quotes and order book deltas with low latency

### Pros & Cons
**Pros:**
- True real-time communication
- Efficient (no repeated handshakes or headers)
- Low latency
- Server can push data without client asking

**Cons:**
- More complex to implement
- Requires persistent connections (uses server memory)
- May have issues with some firewalls/proxies
- Need to handle reconnection logic

---

## 4. Throttling

### What is it?
**Throttling** is limiting how often something can happen within a time period. It's a protective mechanism that says "You can only do X thing Y times per Z seconds."

### Real-World Analogy

**Example 1: Nightclub with a bouncer**
- The club can only fit 100 people
- Once it's full, the bouncer says "Wait, someone has to leave first"
- This prevents overcrowding and keeps everyone safe

**Example 2: Water faucet**
- You can turn it on full blast, but there's a maximum flow rate
- This prevents pipes from bursting due to pressure

**Example 3: Speed limit on highway**
- You CAN drive at 200 km/h, but the limit is 120 km/h
- This keeps everyone safe and traffic flowing smoothly

### How It Works
```
Without Throttling:
  Request 1 -----> Server [Process] OK
  Request 2 -----> Server [Process] OK
  Request 3 -----> Server [Process] OK
  Request 4 -----> Server [Process] OK
  Request 5 -----> Server [OVERLOADED!]
  Request 6 -----> Server [CRASH!]

With Throttling (max 3 requests per second):
  Request 1 -----> Server [Process] OK
  Request 2 -----> Server [Process] OK
  Request 3 -----> Server [Process] OK
  Request 4 -----> Server [429: Too Many Requests - Wait!]
  Request 5 -----> Server [429: Too Many Requests - Wait!]
  
  (after 1 second...)
  
  Request 4 -----> Server [Process] OK
  Request 5 -----> Server [Process] OK
```

### Common Throttling Strategies

| Strategy | How It Works | Best For |
|----------|--------------|----------|
| **Fixed Window** | Count requests in fixed time slots (e.g., per minute) | Simple rate limiting |
| **Sliding Window** | Track requests in a moving time window | Smoother limiting |
| **Token Bucket** | Tokens added over time, each request costs a token | Burst-friendly |
| **Leaky Bucket** | Requests processed at a fixed rate, excess queued | Consistent output rate |

### Token Bucket Example (Simplified)
```python
class TokenBucket:
    def __init__(self, capacity, refill_rate):
        self.capacity = capacity      # Max tokens
        self.tokens = capacity         # Current tokens
        self.refill_rate = refill_rate # Tokens added per second
        self.last_refill = time.time()
    
    def allow_request(self):
        # Refill tokens based on time passed
        now = time.time()
        tokens_to_add = (now - self.last_refill) * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now
        
        # Check if we have a token
        if self.tokens >= 1:
            self.tokens -= 1
            return True  # Request allowed
        return False     # Request denied (throttled)
```

### Use Cases
- **API protection**: Prevent abuse (e.g., max 100 requests per minute per user)
- **Login security**: Block brute-force attacks (e.g., max 5 login attempts per hour)
- **Email sending**: Prevent spam (e.g., max 100 emails per hour)
- **Social media**: Twitter/X limits tweets per hour
- **Search engines**: Limit crawling rate to not overload websites

### Real-World Examples
- **Public APIs**: GitHub / Stripe / Google APIs enforce rate limits and return HTTP 429
- **Auth endpoints**: login + OTP verification often have strict per-user/per-IP throttles
- **Abuse prevention**: signups, password resets, and “send invite” flows are commonly throttled

### Throttling vs Rate Limiting
They're often used interchangeably, but there's a subtle difference:

| Aspect | Throttling | Rate Limiting |
|--------|------------|---------------|
| Behavior | Slows down or queues excess requests | Rejects excess requests immediately |
| User Experience | Smoother, requests eventually processed | Harder rejection, user must retry |
| Implementation | More complex (needs queue) | Simpler |

### HTTP Response for Throttled Requests
```http
HTTP/1.1 429 Too Many Requests
Retry-After: 60
Content-Type: application/json

{
    "error": "Rate limit exceeded",
    "message": "You have made too many requests. Please wait 60 seconds.",
    "retry_after": 60
}
```

---

## 5. Request-Response (HTTP / RPC)

### What is it?
The client sends a **request**, the server processes it, then returns a **response**. This is the default model of HTTP APIs and many RPC systems.

### Real-World Analogy
Ordering at a restaurant:
- You place an order (request)
- The kitchen prepares it (processing)
- The waiter brings your meal (response)

### How It Works
```
Client                          Server
  |                               |
  |--- Request (GET /items) ----->|
  |                               |  (process)
  |<--- Response (200 + JSON) ----|
```

### Use Cases
- Fetching data (profiles, feeds, search results)
- Submitting commands (checkout, create order, update settings)
- Internal service-to-service calls (REST, gRPC, JSON-RPC)

### Real-World Examples
- **Most web/mobile apps**: REST/GraphQL APIs for feeds, profiles, and actions (like, comment, purchase)
- **Payments**: Stripe-like APIs (create customer, create payment intent, confirm payment)
- **Microservices**: internal RPC between services (commonly gRPC) for low-latency calls

### Pros & Cons
**Pros:**
- Simple mental model, easy to debug
- Strong fit for CRUD-style APIs
- Works well with caching (CDNs, HTTP caches)

**Cons:**
- Can be chatty at scale (many small calls)
- Tight coupling in time (server must be up now)
- Tail latency compounds across many downstream calls

---

## 6. Publish-Subscribe (Pub/Sub)

### What is it?
Producers **publish events** to a topic, and subscribers **receive** those events asynchronously. Producers don’t need to know who the subscribers are.

### Real-World Analogy
Following a newsletter:
- The author publishes new issues
- Everyone subscribed receives them

### How It Works
```
Producer ---> [ Topic / Event Bus ] ---> Subscriber A
                              \-----> Subscriber B
                              \-----> Subscriber C
```

### Use Cases
- Domain events (UserSignedUp, PaymentCaptured, OrderShipped)
- Fan-out notifications (email, push, SMS)
- Decoupling microservices (reduce direct synchronous dependencies)

### Real-World Examples
- **Notification fan-out**: one “OrderShipped” event triggers email + push + analytics
- **Microservices**: publish domain events so many teams/services can react without tight coupling
- **Infra**: cloud messaging buses/topics (e.g., AWS SNS / Google Pub/Sub / NATS)

### Pros & Cons
**Pros:**
- Loose coupling (publisher doesn’t depend on consumers)
- Easy fan-out to many consumers
- Improves resilience by removing synchronous chains

**Cons:**
- Harder tracing/debugging (distributed async flows)
- Delivery semantics matter (at-most-once / at-least-once / exactly-once*)
- Ordering is not always guaranteed (depends on system/partitioning)

---

## 7. Message Queue (Work Queue)

### What is it?
A queue stores **jobs/tasks**. Producers enqueue work, and worker(s) consume and process messages. Typically each message is handled by **one** consumer.

### Real-World Analogy
A deli ticket system:
- You take a ticket (enqueue work)
- The next available clerk serves the next ticket (consumer)

### How It Works
```
Producer ---> [ Queue ] ---> Worker 1
                    \-----> Worker 2
                    \-----> Worker 3
```

### Use Cases
- Background processing (image resizing, video transcoding)
- Email sending, report generation, web crawling
- Smoothing spikes (buffering bursts of traffic)

### Real-World Examples
- **E-commerce**: order placed -> enqueue fulfillment, invoicing, and confirmation tasks
- **Media platforms**: upload -> enqueue transcoding + thumbnail generation
- **Email/SMS providers**: sending pipelines are queued to smooth spikes and manage retries

### Pros & Cons
**Pros:**
- Absorbs load spikes (buffering)
- Retries can be managed centrally
- Scales by adding consumers

**Cons:**
- Needs idempotent workers (retries can re-run tasks)
- Poison messages require dead-letter queues (DLQ) or quarantining
- Adds operational components (broker, monitoring, backlogs)

---

## 8. Webhooks

### What is it?
A server sends an HTTP callback to another server when an event happens. It’s like “push notifications” but server-to-server over HTTP.

### Real-World Analogy
A doorbell:
- Someone presses the button (event)
- The bell rings at your house (callback)

### How It Works
```
Provider (A) --POST /webhook--> Consumer (B)
           (event payload + signature)
```

### Best Practices (Important)
- Verify signatures (HMAC) to prevent spoofing
- Use retries with exponential backoff
- Make handlers idempotent (duplicate deliveries happen)
- Respond quickly (enqueue work; don’t do heavy processing inline)

### Use Cases
- Payment providers (payment succeeded/failed)
- Git hosting (push events, PR events)
- CRM integrations (lead created)

### Real-World Examples
- **Stripe**: payment and subscription lifecycle webhooks to your backend
- **GitHub**: push/PR events to CI systems and internal automations
- **Shopify**: order/fulfillment webhooks to third-party apps
- **Slack/Discord**: incoming webhooks to post messages into channels

---

## 9. Server-Sent Events (SSE)

### What is it?
SSE is a **one-way** streaming channel: server -> client over HTTP. The client opens a connection and the server continuously sends events.

### Real-World Analogy
Listening to a live radio broadcast:
- You tune in once
- Updates keep coming without you asking again

### How It Works
```
Client ----(HTTP connect)----> Server
Client <--- event: ... ------- Server
Client <--- event: ... ------- Server
```

### When SSE is a great fit
- Live dashboards, notifications, progress updates
- “Mostly server push” experiences without full WebSocket complexity

### Real-World Examples
- **Streaming AI responses**: many AI APIs stream tokens/events to clients using SSE
- **Live build/log viewers**: CI dashboards that stream job output as it runs
- **Dashboards**: operational views that stream metrics/alerts to the browser

### Pros & Cons
**Pros:**
- Simple (built on HTTP), works well with proxies/CDNs in many setups
- Automatic reconnection is supported by the browser EventSource API

**Cons:**
- One-way only (client -> server needs normal HTTP requests)
- Not ideal for high-frequency bidirectional traffic (use WebSockets)

---

## 10. Event Streaming (Log-Based)

### What is it?
Events are appended to an **ordered log** (stream). Consumers read at their own pace and track their position (offset). Unlike a work queue, multiple consumer groups can independently read the same stream and **replay** events.

### Real-World Analogy
A newspaper archive:
- New editions are appended every day
- Different readers can start today, or go back and reread older issues

### How It Works
```
Producers ---> [ Stream / Log (append-only) ] ---> Consumer Group A (offsets)
                                         \-----> Consumer Group B (offsets)
```

### Use Cases
- Analytics pipelines, clickstreams, audit logs
- Event-driven architectures needing replay (rebuild a read model)
- Data integration between systems (CDC, outbox pattern pipelines)

### Real-World Examples
- **Apache Kafka at scale**: widely used for event streaming (e.g., LinkedIn, Netflix, Uber)
- **Clickstream analytics**: append user events and replay/reprocess to build new metrics
- **Audit + compliance**: immutable-ish event history to answer “who did what and when”

### Pros & Cons
**Pros:**
- Replayability (powerful for debugging and reprocessing)
- High throughput, scalable fan-out via consumer groups

**Cons:**
- Requires schema/versioning discipline (events live “forever”)
- Exactly-once processing is hard end-to-end (often aim for at-least-once + idempotency)

---

## Quick Comparison Table

| Concept | Direction | Connection Type | Best For |
|---------|-----------|-----------------|----------|
| **Pipe** | One-way flow | Chained processes | Data transformation, ETL |
| **Request-Response** | Client -> Server -> Client | Short-lived | CRUD APIs, queries/commands |
| **Polling** | Client -> Server (repeatedly) | Short-lived | Simple updates, compatibility |
| **SSE** | Server -> Client (one-way) | Persistent | Live updates, dashboards |
| **WebSocket** | Both ways (bidirectional) | Persistent | Real-time apps, chat, games |
| **Webhooks** | Server -> Server (event-driven) | Short-lived | Integrations between services |
| **Pub/Sub** | Producer -> Many consumers | Brokered | Fan-out events, decoupling |
| **Message Queue** | Producer -> One consumer | Brokered | Background jobs, buffering spikes |
| **Event Streaming** | Producer -> Many consumers (replayable) | Brokered log | Analytics, audit, event-driven systems |
| **Throttling** | N/A (control mechanism) | N/A | Protection, fair usage, stability |

---

## When to Use What?

### Choose Polling when:
- You need simple implementation
- Updates are not time-critical
- You need maximum compatibility
- Server doesn't support WebSockets

### Choose Request-Response when:
- Your interaction is naturally query/command based (CRUD)
- You want simple debuggability and standard tooling
- You can tolerate synchronous dependency and latency

### Choose SSE when:
- You mainly need server -> client updates
- You want “near real-time” without full bidirectional complexity
- Your UI needs a stream of updates (dashboards, progress, notifications)

### Choose WebSocket when:
- You need real-time updates
- Both client and server need to send data frequently
- Low latency is crucial
- Building chat, games, or collaborative tools

### Choose Webhooks when:
- You’re integrating two backend systems (provider -> consumer)
- The consumer can expose an endpoint and handle retries/idempotency

### Choose Pub/Sub when:
- Multiple components must react to the same event
- You want to decouple producers from consumers
- You want fan-out without N direct calls

### Choose a Message Queue when:
- You need background work processing with competing consumers
- You want buffering to smooth traffic spikes
- You want centralized retries/DLQ for tasks

### Choose Event Streaming when:
- You need replayable history (audit/analytics/reprocessing)
- Multiple consumer groups need the same events independently
- You care about high throughput and scalable fan-out over time

### Use Throttling when:
- Protecting APIs from abuse
- Ensuring fair resource usage
- Preventing system overload
- Implementing security measures (login attempts)

---

## Further Reading
- [WebSocket Protocol (RFC 6455)](https://tools.ietf.org/html/rfc6455)
- [HTTP 429 Status Code](https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/429)
- [Rate Limiting Algorithms](https://en.wikipedia.org/wiki/Rate_limiting)

---

*Last updated: December 2025*

