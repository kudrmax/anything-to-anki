// Draws an arrow or a frame over an element before a screenshot.
// Inject with the page's evaluate, then call window.__annotate({selector, kind, label}).
(() => {
  const COLOR = '#e5484d'
  const STROKE = 3
  const PAD = 6
  const ARROW_LENGTH = 70
  const ARROW_HEAD = 14
  const LABEL_SIZE = 16
  const OVERLAY_ID = '__annotations'
  const SVG_NS = 'http://www.w3.org/2000/svg'

  const svg = (name, attrs) => {
    const node = document.createElementNS(SVG_NS, name)
    Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, String(value)))
    return node
  }

  const overlay = () => {
    let root = document.getElementById(OVERLAY_ID)
    if (root) return root
    root = svg('svg', { id: OVERLAY_ID, width: '100%', height: '100%' })
    root.style.cssText = 'position:fixed;inset:0;pointer-events:none;z-index:2147483647'
    document.body.appendChild(root)
    return root
  }

  const label = (root, text, x, y) => {
    if (!text) return
    const node = svg('text', {
      x, y, fill: COLOR, 'font-size': LABEL_SIZE, 'font-weight': 600,
      'font-family': 'system-ui, sans-serif', 'paint-order': 'stroke', stroke: '#fff', 'stroke-width': 4,
    })
    node.textContent = text
    root.appendChild(node)
  }

  const frame = (root, box, text) => {
    root.appendChild(svg('rect', {
      x: box.left - PAD, y: box.top - PAD, width: box.width + 2 * PAD, height: box.height + 2 * PAD,
      rx: 6, fill: 'none', stroke: COLOR, 'stroke-width': STROKE,
    }))
    label(root, text, box.left - PAD, box.top - PAD - 8)
  }

  const arrow = (root, box, text) => {
    const tipX = box.left + box.width / 2
    const tipY = box.bottom + PAD
    const tailX = tipX + ARROW_LENGTH * 0.6
    const tailY = tipY + ARROW_LENGTH
    root.appendChild(svg('line', {
      x1: tailX, y1: tailY, x2: tipX, y2: tipY, stroke: COLOR, 'stroke-width': STROKE, 'stroke-linecap': 'round',
    }))
    const angle = Math.atan2(tipY - tailY, tipX - tailX)
    const wing = (offset) => [
      tipX - ARROW_HEAD * Math.cos(angle + offset),
      tipY - ARROW_HEAD * Math.sin(angle + offset),
    ]
    const [ax, ay] = wing(Math.PI / 6)
    const [bx, by] = wing(-Math.PI / 6)
    root.appendChild(svg('polygon', { points: `${tipX},${tipY} ${ax},${ay} ${bx},${by}`, fill: COLOR }))
    label(root, text, tailX + 8, tailY + LABEL_SIZE)
  }

  window.__annotate = ({ selector, kind = 'arrow', label: text }) => {
    const target = document.querySelector(selector)
    if (!target) throw new Error(`annotate: no element for ${selector}`)
    const box = target.getBoundingClientRect()
    const root = overlay()
    if (kind === 'frame') frame(root, box, text)
    else arrow(root, box, text)
  }

  window.__clearAnnotations = () => document.getElementById(OVERLAY_ID)?.remove()
})()
