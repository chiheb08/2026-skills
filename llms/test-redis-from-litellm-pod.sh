#!/bin/bash
# Quick script to test Redis connectivity from LiteLLM pod
# Handles both REDIS_HOST/REDIS_PORT format and tcp:// format in REDIS_PORT

echo "=== Testing Redis connectivity from LiteLLM pod ==="
echo ""

# Check REDIS_HOST
echo "REDIS_HOST: ${REDIS_HOST:-<not set>}"
echo "REDIS_PORT: ${REDIS_PORT:-<not set>}"
echo ""

# Determine format and extract connection details
if [[ "$REDIS_PORT" == tcp://* ]]; then
    echo "Detected tcp:// format in REDIS_PORT"
    REDIS_CONN=$(echo $REDIS_PORT | sed 's|tcp://||')
    REDIS_IP=$(echo $REDIS_CONN | cut -d: -f1)
    REDIS_PORT_NUM=$(echo $REDIS_CONN | cut -d: -f2)
    echo "Extracted IP: $REDIS_IP"
    echo "Extracted Port: $REDIS_PORT_NUM"
    REDIS_TARGET_HOST=$REDIS_IP
    REDIS_TARGET_PORT=$REDIS_PORT_NUM
elif [ -n "$REDIS_HOST" ] && [ -n "$REDIS_PORT" ]; then
    echo "Using separate REDIS_HOST and REDIS_PORT"
    REDIS_TARGET_HOST=$REDIS_HOST
    REDIS_TARGET_PORT=$REDIS_PORT
else
    echo "ERROR: Cannot determine Redis connection details"
    exit 1
fi

echo ""
echo "=== Testing TCP connectivity ==="

# Test 1: Using nc (netcat)
if command -v nc &> /dev/null; then
    echo "Test 1: nc -zv $REDIS_TARGET_HOST $REDIS_TARGET_PORT"
    if nc -zv $REDIS_TARGET_HOST $REDIS_TARGET_PORT 2>&1; then
        echo "✅ TCP connection successful"
    else
        echo "❌ TCP connection failed"
    fi
else
    echo "⚠️  nc (netcat) not found, skipping..."
fi

echo ""

# Test 2: Using timeout + /dev/tcp
echo "Test 2: timeout + /dev/tcp"
if timeout 3 bash -c "echo >/dev/tcp/$REDIS_TARGET_HOST/$REDIS_TARGET_PORT" 2>/dev/null; then
    echo "✅ TCP connection successful"
else
    echo "❌ TCP connection failed"
fi

echo ""

# Test 3: Redis PING (if redis-cli available)
if command -v redis-cli &> /dev/null; then
    echo "=== Testing Redis PING ==="
    if [ -n "$REDIS_PASSWORD" ]; then
        echo "Test 3: redis-cli PING (with password)"
        if redis-cli -h $REDIS_TARGET_HOST -p $REDIS_TARGET_PORT -a "$REDIS_PASSWORD" PING 2>&1 | grep -q PONG; then
            echo "✅ Redis PING successful (PONG received)"
        else
            echo "❌ Redis PING failed"
        fi
    else
        echo "Test 3: redis-cli PING (no password)"
        if redis-cli -h $REDIS_TARGET_HOST -p $REDIS_TARGET_PORT PING 2>&1 | grep -q PONG; then
            echo "✅ Redis PING successful (PONG received)"
        else
            echo "❌ Redis PING failed (might need password)"
        fi
    fi
else
    echo "⚠️  redis-cli not found, skipping Redis PING test"
fi

echo ""
echo "=== Summary ==="
echo "Target: $REDIS_TARGET_HOST:$REDIS_TARGET_PORT"
echo "If all tests show ✅, Redis is reachable from LiteLLM pod"
