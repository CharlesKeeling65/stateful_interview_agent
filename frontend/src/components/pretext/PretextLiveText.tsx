import { useEffect, useRef } from 'react'

type PretextLiveTextProps = {
  className?: string
  text: string
}

export function PretextLiveText({ className, text }: PretextLiveTextProps) {
  const ref = useRef<HTMLSpanElement | null>(null)

  useEffect(() => {
    if (ref.current && ref.current.textContent !== text) {
      ref.current.textContent = text
    }
  }, [text])

  return <span ref={ref} className={className}>{text}</span>
}
