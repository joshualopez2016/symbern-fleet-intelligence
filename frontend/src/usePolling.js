import { useEffect, useRef, useState, useCallback } from 'react'

// Calls `fn` immediately and then every `intervalMs`. Pauses while the browser
// tab is hidden (no point polling a dashboard nobody is looking at) and resumes
// on focus. Returns { data, error, loading, refresh }.
export function usePolling(fn, intervalMs, deps = []) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const savedFn = useRef(fn)
  savedFn.current = fn

  const run = useCallback(async () => {
    try {
      const result = await savedFn.current()
      setData(result)
      setError(null)
    } catch (e) {
      setError(e.message || String(e))
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  useEffect(() => {
    let timer = null
    const tick = () => {
      if (!document.hidden) run()
    }
    run()
    timer = setInterval(tick, intervalMs)
    const onVisible = () => {
      if (!document.hidden) run()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisible)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run, intervalMs])

  return { data, error, loading, refresh: run }
}
