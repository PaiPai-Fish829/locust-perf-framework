import html2canvas from 'html2canvas'

export function fileStamp(): string {
  return new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
}

export function downloadDataUrl(dataUrl: string, filename: string) {
  const a = document.createElement('a')
  a.href = dataUrl
  a.download = filename
  a.click()
}

export async function exportDomPng(
  element: HTMLElement | null,
  filename: string,
): Promise<boolean> {
  if (!element) return false
  const canvas = await html2canvas(element, {
    backgroundColor: '#ffffff',
    scale: 2,
    logging: false,
    useCORS: true,
  })
  downloadDataUrl(canvas.toDataURL('image/png'), filename)
  return true
}
