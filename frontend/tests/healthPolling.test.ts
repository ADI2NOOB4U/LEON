import assert from 'node:assert/strict'
import { test } from 'node:test'
import { createHealthPoller, type HealthConnectionState } from '../src/api/healthPoller.ts'
import type { HealthStatus } from '../src/types/api.ts'

const healthyResponse: HealthStatus = {
  status: 'online',
  service: 'LEON',
  version: '0.1.0',
}

const wait = (milliseconds: number) => new Promise((resolve) => setTimeout(resolve, milliseconds))
const waitFor = async (condition: () => boolean, timeoutMs = 1000) => {
  const deadline = Date.now() + timeoutMs
  while (!condition()) {
    if (Date.now() >= deadline) throw new Error('Timed out waiting for poller state')
    await wait(5)
  }
}

test('poller awaits each request and schedules the next check afterward', async () => {
  const resolveRequests: Array<(health: HealthStatus) => void> = []
  let requests = 0
  const stop = createHealthPoller({
    check: () => {
      requests += 1
      return new Promise((resolve) => resolveRequests.push(resolve))
    },
    onChange: () => undefined,
    intervalMs: 10,
    timeoutMs: 1000,
  }).start()

  await waitFor(() => requests === 1)
  await wait(30)
  assert.equal(requests, 1)
  resolveRequests[0](healthyResponse)
  await waitFor(() => requests === 2)
  assert.equal(requests, 2)
  stop()
  resolveRequests[1](healthyResponse)
})

test('cleanup aborts the active request and prevents future checks', async () => {
  let requests = 0
  let aborted = false
  const stop = createHealthPoller({
    check: (signal) => {
      requests += 1
      return new Promise((_resolve, reject) => {
        signal.addEventListener('abort', () => {
          aborted = true
          reject(new Error('aborted'))
        }, { once: true })
      })
    },
    onChange: () => undefined,
    intervalMs: 10,
    timeoutMs: 1000,
  }).start()

  await waitFor(() => requests === 1)
  stop()
  await wait(25)
  assert.equal(aborted, true)
  assert.equal(requests, 1)
})

test('timeout aborts the request, retries, and eventually reports online', async () => {
  const states: HealthConnectionState[] = []
  let requests = 0
  const stop = createHealthPoller({
    check: (signal) => {
      requests += 1
      if (requests === 1) {
        return new Promise((_resolve, reject) => {
          signal.addEventListener('abort', () => reject(new Error('aborted')), { once: true })
        })
      }
      return Promise.resolve(healthyResponse)
    },
    onChange: (state) => states.push(state),
    intervalMs: 5,
    timeoutMs: 10,
  }).start()

  await waitFor(() => states.at(-1) === 'online')
  stop()
  assert.ok(requests >= 2)
  assert.equal(states.at(-1), 'online')
})

test('transient failure keeps the current connection until the threshold', async () => {
  const states: HealthConnectionState[] = []
  let requests = 0
  const stop = createHealthPoller({
    check: async () => {
      requests += 1
      if (requests === 2) throw new Error('transient')
      return healthyResponse
    },
    onChange: (state) => states.push(state),
    intervalMs: 5,
  }).start()

  await waitFor(() => requests >= 3)
  stop()
  assert.equal(states[0], 'online')
  assert.equal(states[1], 'online')
  assert.equal(states.at(-1), 'online')
})

test('three consecutive failures are required before going offline', async () => {
  const states: HealthConnectionState[] = []
  let requests = 0
  const stop = createHealthPoller({
    check: async () => {
      requests += 1
      throw new Error('unavailable')
    },
    onChange: (state) => states.push(state),
    intervalMs: 5,
  }).start()

  await waitFor(() => states.length >= 3)
  stop()
  assert.ok(requests >= 3)
  assert.deepEqual(states.slice(0, 3), ['connecting', 'connecting', 'offline'])
})

test('restart after unmount aborts the old poller without multiplying requests', async () => {
  let activeRequests = 0
  let maxActiveRequests = 0
  const createCheck = () => (signal: AbortSignal) => new Promise<HealthStatus>((_resolve, reject) => {
    activeRequests += 1
    maxActiveRequests = Math.max(maxActiveRequests, activeRequests)
    signal.addEventListener('abort', () => {
      activeRequests -= 1
      reject(new Error('aborted'))
    }, { once: true })
  })
  const options = { check: createCheck(), onChange: () => undefined, intervalMs: 10, timeoutMs: 1000 }
  const stopFirst = createHealthPoller(options).start()

  await waitFor(() => activeRequests === 1)
  stopFirst()
  const stopSecond = createHealthPoller({ ...options, check: createCheck() }).start()
  await waitFor(() => activeRequests === 1)
  assert.equal(maxActiveRequests, 1)
  stopSecond()
})