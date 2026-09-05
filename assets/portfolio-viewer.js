(() => {
  const links = [...document.querySelectorAll('.folio-flow .folio__open')];
  const dialog = document.querySelector('#portfolio-viewer');
  if (!links.length || !dialog || typeof dialog.showModal !== 'function') return;

  const image = dialog.querySelector('.portfolio-viewer__image');
  const stage = dialog.querySelector('.portfolio-viewer__stage');
  const caption = dialog.querySelector('#portfolio-viewer-caption');
  const counter = dialog.querySelector('.portfolio-viewer__counter');
  const zoom = dialog.querySelector('[data-viewer-zoom]');
  const previous = dialog.querySelector('[data-viewer-previous]');
  const next = dialog.querySelector('[data-viewer-next]');
  const close = dialog.querySelector('[data-viewer-close]');
  let current = 0;
  let opener = null;
  let zoomed = false;
  let resumeScroll = false;

  function setZoom(value) {
    zoomed = value;
    dialog.classList.toggle('is-zoomed', value);
    zoom.textContent = value ? 'Fit to screen' : 'Zoom in';
    zoom.setAttribute('aria-pressed', String(value));
    image.setAttribute('aria-label', value ? 'Zoom out' : 'Zoom in');
    stage.scrollTo(0, 0);
  }

  function show(index) {
    current = index;
    const link = links[index];
    const source = link.querySelector('img');
    setZoom(false);
    image.src = link.href;
    image.alt = source.alt;
    image.width = Number(source.getAttribute('width'));
    image.height = Number(source.getAttribute('height'));
    image.style.setProperty('--photo-width', `${source.getAttribute('width')}px`);
    image.style.setProperty('--photo-ratio', `${source.getAttribute('width')} / ${source.getAttribute('height')}`);
    caption.textContent = link.closest('figure').querySelector('figcaption').textContent;
    counter.textContent = `${index + 1} / ${links.length}`;
    previous.disabled = index === 0;
    next.disabled = index === links.length - 1;
  }

  links.forEach((link, index) => {
    link.addEventListener('click', (event) => {
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      opener = link;
      show(index);
      const lenis = window.PROROK_LENIS;
      resumeScroll = Boolean(lenis && !lenis.isStopped);
      lenis?.stop();
      document.documentElement.classList.add('portfolio-viewer-open');
      dialog.showModal();
      close.focus({ preventScroll: true });
    });
  });

  previous.addEventListener('click', () => { if (current > 0) show(current - 1); });
  next.addEventListener('click', () => { if (current < links.length - 1) show(current + 1); });
  close.addEventListener('click', () => dialog.close());
  zoom.addEventListener('click', () => setZoom(!zoomed));
  image.addEventListener('click', () => setZoom(!zoomed));
  image.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      setZoom(!zoomed);
    }
  });
  dialog.addEventListener('keydown', (event) => {
    if (zoomed) return; // Arrow keys pan the image when zoomed.
    if (event.key === 'ArrowLeft' && current > 0) {
      event.preventDefault();
      show(current - 1);
    }
    if (event.key === 'ArrowRight' && current < links.length - 1) {
      event.preventDefault();
      show(current + 1);
    }
  });
  dialog.addEventListener('click', (event) => {
    if (event.target === dialog || event.target === stage) dialog.close();
  });
  dialog.addEventListener('close', () => {
    document.documentElement.classList.remove('portfolio-viewer-open');
    setZoom(false);
    if (resumeScroll) window.PROROK_LENIS?.start();
    opener?.focus({ preventScroll: true });
  });
})();
