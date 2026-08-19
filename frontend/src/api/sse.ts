/**
 * Minimal SSE parser over `fetch` so we can send auth headers and POST bodies.
 * Emits events with `event:` / `data:` lines, returns an AbortController for cancellation.
 */
export interface SseHandlers {
  onEvent: (event: string, data: any) => void
  onError?: (err: Error) => void
  onClose?: () => void
}

export function streamSSE(
  url: string,
  init: Omit<RequestInit, 'body'> & { body?: any },
  handlers: SseHandlers,
): AbortController {
  const ctrl = new AbortController()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'text/event-stream',
    ...(init.headers as Record<string, string> | undefined),
  }

  ;(async () => {
    try {
      const resp = await fetch(url, {
        method: init.method ?? 'POST',
        headers,
        body: init.body ? JSON.stringify(init.body) : undefined,
        signal: ctrl.signal,
      })
      if (!resp.ok || !resp.body) {
        const text = await resp.text().catch(() => '')
        throw new Error(`SSE ${resp.status}: ${text || resp.statusText}`)
      }

      const reader = resp.body.getReader()
      const decoder = new TextDecoder('utf-8')
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n')
        let idx: number
        while ((idx = buffer.indexOf('\n\n')) >= 0) {
          const chunk = buffer.slice(0, idx)
          buffer = buffer.slice(idx + 2)
          let event = 'message'
          const dataLines: string[] = []
          for (const line of chunk.split('\n')) {
            if (line.startsWith('event:')) event = line.slice(6).trim()
            else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
          }
          if (!dataLines.length) continue
          const raw = dataLines.join('\n')
          let parsed: any = raw
          try {
            parsed = JSON.parse(raw)
          } catch {
            /* keep as string */
          }
          handlers.onEvent(event, parsed)
        }
      }
      handlers.onClose?.()
    } catch (e: any) {
      if (e.name === 'AbortError') {
        handlers.onClose?.()
        return
      }
      handlers.onError?.(e)
    }
  })()

  return ctrl
}
