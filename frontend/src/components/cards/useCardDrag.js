import { useEffect, useRef } from 'react';

export default function useCardDrag(onDrop) {
  const drag = useRef(null);
  const suppressClick = useRef(false);

  function clear() {
    const current = drag.current;
    if (!current) return;
    current.target?.classList.remove('drop-hover');
    current.element.classList.remove('dragging');
    current.element.style.removeProperty('transform');
    drag.current = null;
  }

  useEffect(() => clear, []);

  return {
    onPointerDown(event) {
      suppressClick.current = false;
      if (!onDrop || event.button !== 0 || !event.isPrimary) return;
      const element = event.currentTarget;
      element.setPointerCapture(event.pointerId);
      drag.current = {
        element,
        pointer: event.pointerId,
        x: event.clientX,
        y: event.clientY,
        active: false,
        table: element.closest('.my-table'),
      };
    },
    onPointerMove(event) {
      const current = drag.current;
      if (!current || event.pointerId !== current.pointer) return;
      const x = event.clientX - current.x;
      const y = event.clientY - current.y;
      if (!current.active && Math.hypot(x, y) < 6) return;
      current.active = true;
      current.element.classList.add('dragging');
      current.element.style.transform = `translate(${x}px, ${y}px) rotate(3deg) scale(1.08)`;
      const target = document
        .elementFromPoint(event.clientX, event.clientY)
        ?.closest('[data-drop-row]');
      current.target?.classList.remove('drop-hover');
      current.target =
        target && current.table?.contains(target) ? target : null;
      current.target?.classList.add('drop-hover');
    },
    onPointerUp(event) {
      const current = drag.current;
      if (!current || event.pointerId !== current.pointer) return;
      const row = current.target?.dataset.dropRow;
      suppressClick.current = current.active;
      const active = current.active;
      clear();
      if (event.currentTarget.hasPointerCapture(event.pointerId)) {
        event.currentTarget.releasePointerCapture(event.pointerId);
      }
      if (active && row && onDrop) onDrop(row);
    },
    onPointerCancel() {
      suppressClick.current = !!drag.current?.active;
      clear();
    },
    onLostPointerCapture: clear,
    onClickCapture(event) {
      if (suppressClick.current) {
        event.preventDefault();
        event.stopPropagation();
        suppressClick.current = false;
      }
    },
  };
}
