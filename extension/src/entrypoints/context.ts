export default defineContentScript({
  matches: ['<all_urls>'],
  // Run as early as possible to intercept shadow root creation
  runAt: 'document_start',
  main() {
    const patch = `(
      function() {
        const original = Element.prototype.attachShadow;
        Element.prototype.attachShadow = function(init) {
          if (init && init.mode === 'closed') {
            const newInit = Object.assign({}, init, { mode: 'open' });
            return original.call(this, newInit);
          }
          return original.call(this, init);
        };
      }
    )();`;
    const script = document.createElement('script');
    script.textContent = patch;
    (document.documentElement || document.head).appendChild(script);
    script.remove();
  },
});
