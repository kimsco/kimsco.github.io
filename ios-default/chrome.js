/* Default iOS status bars are opaque: match the visible screen rather than
   restoring black-translucent, which reintroduces the device's blur. */
(() => {
  const root = document.documentElement;
  const meta = document.querySelector('meta[name="theme-color"]');
  let frame = 0;
  function sync() {
    frame = 0;
    const light = root.classList.contains('light-mode-on');
    let color = light ? '#ffffff' : '#000000';
    if (!document.getElementById('bootSplash')) {
      const top = document.elementFromPoint(innerWidth / 2, 1);
      const panel = top?.closest('.settings-panel, #navDrawer');
      if (panel) {
        const style = getComputedStyle(panel);
        if (style.backgroundImage.includes('radial-gradient')) {
          // Composite the gradient's top-centre colour over its base surface.
          // Menu's glow originates at the left; settings' glow is centred.
          color = panel.id === 'navDrawer'
            ? (light ? '#f0eaeb' : '#2d0f12')
            : (light ? '#eadcde' : '#54161b');
        } else if (style.backgroundColor !== 'rgba(0, 0, 0, 0)') {
          color = style.backgroundColor;
        }
      }
    }
    if (meta && meta.content !== color) meta.content = color;
    if (root.style.getPropertyValue('--native-status-color') !== color)
      root.style.setProperty('--native-status-color', color);
  }
  function schedule() { if (!frame) frame = requestAnimationFrame(sync); }
  const observer = new MutationObserver(schedule);
  observer.observe(root, {attributes: true, attributeFilter: ['class']});
  document.querySelectorAll('.settings-overlay, #navDrawerOverlay').forEach(el =>
    observer.observe(el, {attributes: true, attributeFilter: ['class']}));
  // Match after slide/swipe completion too, including returning to the home view.
  document.addEventListener('transitionend', schedule, true);
  document.addEventListener('touchend', schedule, {passive: true});
  document.addEventListener('visibilitychange', schedule);
  const splash = document.getElementById('bootSplash');
  if (splash?.parentElement) observer.observe(splash.parentElement, {childList: true});
  schedule();
})();
